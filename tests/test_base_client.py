"""Tests for economic.clients.base_client (FR-21) — all offline, httpx mocked."""

from __future__ import annotations

import pytest

from kinostate.economic.clients import base_client
from kinostate.economic.clients.base_client import BaseAnchorError, send_hash_transaction

_TEST_PRIVATE_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
_FAKE_TX_HASH = "0x" + "ab" * 32


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def _mock_post_factory(responses_by_method: dict[str, dict]):
    def _mock_post(url, json, timeout):
        return _FakeResponse(responses_by_method[json["method"]])

    return _mock_post


def test_send_hash_transaction_returns_tx_hash(monkeypatch):
    monkeypatch.setenv("BASE_WALLET_PRIVATE_KEY", _TEST_PRIVATE_KEY)
    monkeypatch.setattr(
        base_client.httpx,
        "post",
        _mock_post_factory(
            {
                "eth_getTransactionCount": {"result": "0x1"},
                "eth_gasPrice": {"result": "0x3b9aca00"},
                "eth_sendRawTransaction": {"result": _FAKE_TX_HASH},
            }
        ),
    )

    tx_hash = send_hash_transaction("aa" * 32)

    assert tx_hash == _FAKE_TX_HASH


def test_send_hash_transaction_requires_private_key(monkeypatch):
    monkeypatch.delenv("BASE_WALLET_PRIVATE_KEY", raising=False)

    with pytest.raises(BaseAnchorError, match="BASE_WALLET_PRIVATE_KEY"):
        send_hash_transaction("aa" * 32)


def test_rpc_error_field_raises(monkeypatch):
    monkeypatch.setenv("BASE_WALLET_PRIVATE_KEY", _TEST_PRIVATE_KEY)
    monkeypatch.setattr(
        base_client.httpx,
        "post",
        _mock_post_factory({"eth_getTransactionCount": {"error": {"message": "boom"}}}),
    )

    with pytest.raises(BaseAnchorError, match="boom"):
        send_hash_transaction("aa" * 32)
