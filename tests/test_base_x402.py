"""Tests for economic.base_x402's real anchor_provenance + meter_call wiring (FR-19..22)."""

from __future__ import annotations

from kinostate.economic import base_x402
from kinostate.memory.tenant_store import BrandMemory


def test_anchor_provenance_uses_real_client(monkeypatch):
    monkeypatch.setattr(base_x402, "send_hash_transaction", lambda content_hash: "0xfaketxhash")

    result = base_x402.anchor_provenance("mock://seedance/abc", {"prompt": "a test shot"})

    assert result["anchored"] is True
    assert result["tx_hash"] == "0xfaketxhash"
    assert len(result["content_hash"]) == 64  # sha256 hex digest
    assert "mock" not in result


def _open_memory(tmp_path) -> BrandMemory:
    return BrandMemory.open("acme", memory_dir=tmp_path / "brands")


def test_meter_call_rejects_over_budget(tmp_path):
    memory = _open_memory(tmp_path)
    memory.set_state("spending_policy", {"budget_ceiling_usdc": 0.01})

    result = base_x402.meter_call(memory, 0.05)

    assert result["authorized"] is False
    assert "budget ceiling" in result["reason"]


def test_meter_call_returns_payment_required_when_unpaid(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    monkeypatch.setattr(base_x402, "build_payment_requirements", lambda price: [_FakeRequirement()])
    monkeypatch.setattr(base_x402, "encode_payment_required", lambda reqs: "encoded-header-value")

    result = base_x402.meter_call(memory, 0.05)

    assert result["authorized"] is False
    assert result["payment_required"] == [{"scheme": "exact"}]
    assert result["payment_required_header"] == "encoded-header-value"


def test_meter_call_authorizes_valid_payment(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    monkeypatch.setattr(base_x402, "build_payment_requirements", lambda price: [_FakeRequirement()])
    monkeypatch.setattr(base_x402, "verify_and_settle", lambda payload, reqs: (True, "0xtxhash", None))

    result = base_x402.meter_call(memory, 0.05, payment_payload="some-header")

    assert result == {"authorized": True, "cost_usdc": 0.05, "tx_hash": "0xtxhash"}


def test_meter_call_rejects_invalid_payment(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    monkeypatch.setattr(base_x402, "build_payment_requirements", lambda price: [_FakeRequirement()])
    monkeypatch.setattr(base_x402, "verify_and_settle", lambda payload, reqs: (False, None, "bad signature"))

    result = base_x402.meter_call(memory, 0.05, payment_payload="some-header")

    assert result == {"authorized": False, "reason": "bad signature"}


def test_record_cost_writes_journal_event(tmp_path):
    memory = _open_memory(tmp_path)

    base_x402.record_cost(memory, "gen-1", {"authorized": True, "cost_usdc": 0.05, "tx_hash": "0xtxhash"})

    events = memory.read_events(limit=10)
    assert any(e["extra"].get("generation_id") == "gen-1" and e["extra"].get("authorized") is True for e in events)


class _FakeRequirement:
    def model_dump(self):
        return {"scheme": "exact"}
