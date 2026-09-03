"""Tests for economic.clients.virtuals_client (FR-23) — all offline, SDK classes mocked.

ACPContractClientV2 and VirtualsACP both make real on-chain/network calls
at construction time in the real SDK, so they must never run for real here.
"""

from __future__ import annotations

import pytest

from kinostate.economic.clients import virtuals_client
from kinostate.economic.clients.virtuals_client import VirtualsAcpError, build_client

_ENV = {
    "VIRTUALS_WALLET_PRIVATE_KEY": "0xabc123",
    "VIRTUALS_AGENT_WALLET_ADDRESS": "0xAgentWallet",
    "VIRTUALS_ENTITY_ID": "42",
}


def _set_env(monkeypatch, overrides=None):
    for key, value in {**_ENV, **(overrides or {})}.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_build_client_constructs_with_expected_args(monkeypatch):
    _set_env(monkeypatch)
    captured = {}

    class _FakeContractClient:
        pass

    def _fake_contract_client_cls(agent_wallet_address, private_key, entity_id, config):
        captured["agent_wallet_address"] = agent_wallet_address
        captured["private_key"] = private_key
        captured["entity_id"] = entity_id
        captured["config"] = config
        return _FakeContractClient()

    def _fake_virtuals_acp(acp_contract_clients, skip_socket_connection):
        captured["acp_contract_clients"] = acp_contract_clients
        captured["skip_socket_connection"] = skip_socket_connection
        return "the-client"

    monkeypatch.setattr(virtuals_client, "ACPContractClientV2", _fake_contract_client_cls)
    monkeypatch.setattr(virtuals_client, "VirtualsACP", _fake_virtuals_acp)

    result = build_client()

    assert result == "the-client"
    assert captured["agent_wallet_address"] == "0xAgentWallet"
    assert captured["private_key"] == "0xabc123"
    assert captured["entity_id"] == 42
    assert captured["config"] is virtuals_client.BASE_SEPOLIA_CONFIG_V2
    assert captured["skip_socket_connection"] is True


@pytest.mark.parametrize(
    "missing_var",
    ["VIRTUALS_WALLET_PRIVATE_KEY", "VIRTUALS_AGENT_WALLET_ADDRESS", "VIRTUALS_ENTITY_ID"],
)
def test_build_client_requires_all_env_vars(monkeypatch, missing_var):
    _set_env(monkeypatch, {missing_var: None})

    with pytest.raises(VirtualsAcpError, match=missing_var):
        build_client()


def test_build_client_wraps_sdk_errors(monkeypatch):
    _set_env(monkeypatch)

    def _raise(*args, **kwargs):
        raise RuntimeError("agent account is not deployed on-chain")

    monkeypatch.setattr(virtuals_client, "ACPContractClientV2", _raise)

    with pytest.raises(VirtualsAcpError, match="not deployed on-chain"):
        build_client()
