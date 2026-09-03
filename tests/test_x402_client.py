"""Tests for economic.clients.x402_client (FR-19) — all offline, facilitator mocked."""

from __future__ import annotations

import pytest

from kinostate.economic.clients import x402_client
from kinostate.economic.clients.x402_client import (
    X402Error,
    build_payment_requirements,
    encode_payment_required,
    verify_and_settle,
)


class _FakeRequirements:
    def model_dump(self):
        return {"scheme": "exact", "network": x402_client.NETWORK}


class _FakeServer:
    def __init__(self, verify_ok=True, settle_ok=True):
        self._verify_ok = verify_ok
        self._settle_ok = settle_ok

    def register(self, network, scheme):
        pass

    def build_payment_requirements(self, config):
        return [_FakeRequirements()]

    def create_payment_required_response(self, requirements):
        return "fake-payment-required-object"

    def verify_payment(self, payload, requirements):
        return type("V", (), {"is_valid": self._verify_ok, "invalid_reason": "bad signature"})()

    def settle_payment(self, payload, requirements):
        return type("S", (), {"success": self._settle_ok, "error_reason": "settlement failed", "transaction": "0xtxhash"})()


def test_build_payment_requirements_requires_pay_to(monkeypatch):
    monkeypatch.delenv("KINOSTATE_X402_PAY_TO_ADDRESS", raising=False)

    with pytest.raises(X402Error, match="KINOSTATE_X402_PAY_TO_ADDRESS"):
        build_payment_requirements(0.05)


def test_build_payment_requirements_returns_real_shape(monkeypatch):
    monkeypatch.setenv("KINOSTATE_X402_PAY_TO_ADDRESS", "0xPayTo")
    monkeypatch.setattr(x402_client, "_build_server", lambda: _FakeServer())

    requirements = build_payment_requirements(0.05)

    assert len(requirements) == 1
    assert requirements[0].model_dump()["scheme"] == "exact"


def test_encode_payment_required_returns_header_string(monkeypatch):
    monkeypatch.setattr(x402_client, "_build_server", lambda: _FakeServer())
    monkeypatch.setattr(x402_client, "encode_payment_required_header", lambda payment_required: f"encoded:{payment_required}")

    header = encode_payment_required([_FakeRequirements()])

    assert header == "encoded:fake-payment-required-object"


def test_verify_and_settle_success(monkeypatch):
    monkeypatch.setattr(x402_client, "decode_payment_signature_header", lambda header: "decoded-payload")
    monkeypatch.setattr(x402_client, "_build_server", lambda: _FakeServer(verify_ok=True, settle_ok=True))

    verified, tx_hash, error = verify_and_settle("some-header", [_FakeRequirements()])

    assert verified is True
    assert tx_hash == "0xtxhash"
    assert error is None


def test_verify_and_settle_invalid_payment(monkeypatch):
    monkeypatch.setattr(x402_client, "decode_payment_signature_header", lambda header: "decoded-payload")
    monkeypatch.setattr(x402_client, "_build_server", lambda: _FakeServer(verify_ok=False))

    verified, tx_hash, error = verify_and_settle("some-header", [_FakeRequirements()])

    assert verified is False
    assert tx_hash is None
    assert error == "bad signature"


def test_verify_and_settle_bad_header_decode(monkeypatch):
    def _raise(header):
        raise ValueError("malformed header")

    monkeypatch.setattr(x402_client, "decode_payment_signature_header", _raise)

    verified, tx_hash, error = verify_and_settle("garbage", [_FakeRequirements()])

    assert verified is False
    assert "malformed header" in error
