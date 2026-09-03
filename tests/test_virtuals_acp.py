"""Tests for economic.virtuals_acp's real register_provider wiring (FR-23)."""

from __future__ import annotations

import pytest

from kinostate.economic import virtuals_acp
from kinostate.economic.clients.virtuals_client import VirtualsAcpError


class _FakeContractClient:
    entity_id = 42
    agent_wallet_address = "0xAgentWallet"


class _FakeClient:
    contract_clients = [_FakeContractClient()]


def test_register_provider_returns_real_connection_info(monkeypatch):
    monkeypatch.setattr(virtuals_acp, "build_client", lambda: _FakeClient())

    result = virtuals_acp.register_provider("acme")

    assert result["registered"] is True
    assert result["entity_id"] == 42
    assert result["wallet_address"] == "0xAgentWallet"
    assert result["job_schema"]["brand_id"] == "str"
    assert "mock" not in result


def test_register_provider_propagates_connection_errors(monkeypatch):
    def _raise():
        raise VirtualsAcpError("missing required env var(s): VIRTUALS_WALLET_PRIVATE_KEY")

    monkeypatch.setattr(virtuals_acp, "build_client", _raise)

    with pytest.raises(VirtualsAcpError, match="VIRTUALS_WALLET_PRIVATE_KEY"):
        virtuals_acp.register_provider("acme")


def test_grant_access_still_stubbed():
    result = virtuals_acp.grant_access("acme", ["palette"], "other-agent")

    assert result["mock"] is True
    assert result["escrow_settled"] is False
