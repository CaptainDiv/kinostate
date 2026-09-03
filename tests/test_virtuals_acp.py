"""Tests for economic.virtuals_acp's real register_provider, access-request,
and evaluator wiring on ACP v2 (FR-23..25)."""

from __future__ import annotations

from kinostate.economic import virtuals_acp
from kinostate.memory.tenant_store import BrandMemory


def _open_memory(tmp_path) -> BrandMemory:
    return BrandMemory.open("acme", memory_dir=tmp_path / "brands")


def test_register_provider_returns_real_identity(monkeypatch):
    monkeypatch.setattr(virtuals_acp, "whoami", lambda: {"agentId": "kinostate-1", "address": "0xAgent"})

    result = virtuals_acp.register_provider("acme")

    assert result["registered"] is True
    assert result["agent"] == {"agentId": "kinostate-1", "address": "0xAgent"}
    assert result["job_schema"]["brand_id"] == "str"


def test_handle_access_request_delivers_eligible_reference_tier(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_reference("palette", {"palette_hex": ["#111111"]})

    accepted = {}
    delivered = {}
    monkeypatch.setattr(virtuals_acp, "accept_job", lambda job_id, price: accepted.setdefault("job_id", job_id))
    monkeypatch.setattr(
        virtuals_acp, "submit_deliverable", lambda job_id, deliverable: delivered.setdefault("deliverable", deliverable)
    )
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not reject")))

    event = {"job_id": "job-1", "requirement": {"tier": "reference", "key": "palette"}}
    virtuals_acp.handle_access_request(memory, event)

    assert accepted["job_id"] == "job-1"
    assert "palette_hex" in delivered["deliverable"]
    events = memory.read_events(limit=10)
    assert any(e["extra"].get("tier") == "reference" for e in events)


def test_handle_access_request_rejects_ineligible_tier(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    rejected = {}
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda job_id, reason: rejected.update(job_id=job_id, reason=reason))
    monkeypatch.setattr(virtuals_acp, "accept_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not accept")))

    event = {"job_id": "job-1", "requirement": {"tier": "hot", "key": "session"}}
    virtuals_acp.handle_access_request(memory, event)

    assert rejected["job_id"] == "job-1"
    assert "not eligible" in rejected["reason"]


def test_handle_access_request_rejects_missing_data(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    rejected = {}
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda job_id, reason: rejected.update(job_id=job_id, reason=reason))

    event = {"job_id": "job-1", "requirement": {"tier": "reference", "key": "nonexistent"}}
    virtuals_acp.handle_access_request(memory, event)

    assert rejected["job_id"] == "job-1"


def test_evaluate_brand_consistency_completes_on_pass(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_entity(
        "character",
        "aria",
        {"canonical_reference_asset": "https://img.example/aria.png", "confidence": {}},
    )
    monkeypatch.setattr(
        virtuals_acp, "check_visual_consistency", lambda ref, video: (True, 0.9, "similarity 0.9")
    )
    completed = {}
    monkeypatch.setattr(virtuals_acp, "complete_job", lambda job_id, reason: completed.update(job_id=job_id, reason=reason))
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not reject")))

    event = {"job_id": "job-1", "deliverable": {"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"}}
    virtuals_acp.evaluate_brand_consistency(memory, event)

    assert completed == {"job_id": "job-1", "reason": "similarity 0.9"}


def test_evaluate_brand_consistency_rejects_without_reference(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_entity("character", "aria", {"confidence": {}})
    rejected = {}
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda job_id, reason: rejected.update(job_id=job_id, reason=reason))

    event = {"job_id": "job-1", "deliverable": {"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"}}
    virtuals_acp.evaluate_brand_consistency(memory, event)

    assert "no canonical_reference_asset" in rejected["reason"]


def test_evaluate_brand_consistency_rejects_on_check_failure(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_entity(
        "character",
        "aria",
        {"canonical_reference_asset": "https://img.example/aria.png", "confidence": {}},
    )

    from kinostate.verification.visual_similarity import VisualSimilarityError

    def _raise(ref, video):
        raise VisualSimilarityError("could not download video")

    monkeypatch.setattr(virtuals_acp, "check_visual_consistency", _raise)
    rejected = {}
    monkeypatch.setattr(virtuals_acp, "reject_job", lambda job_id, reason: rejected.update(job_id=job_id, reason=reason))

    event = {"job_id": "job-1", "deliverable": {"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"}}
    virtuals_acp.evaluate_brand_consistency(memory, event)

    assert "could not download video" in rejected["reason"]
