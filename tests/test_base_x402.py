"""Tests for economic.base_x402's real anchor_provenance wiring (FR-21)."""

from __future__ import annotations

from kinostate.economic import base_x402


def test_anchor_provenance_uses_real_client(monkeypatch):
    monkeypatch.setattr(base_x402, "send_hash_transaction", lambda content_hash: "0xfaketxhash")

    result = base_x402.anchor_provenance("mock://seedance/abc", {"prompt": "a test shot"})

    assert result["anchored"] is True
    assert result["tx_hash"] == "0xfaketxhash"
    assert len(result["content_hash"]) == 64  # sha256 hex digest
    assert "mock" not in result


def test_meter_call_still_stubbed():
    result = base_x402.meter_call("seedance", 0.5)

    assert result["mock"] is True
    assert result["authorized"] is True
