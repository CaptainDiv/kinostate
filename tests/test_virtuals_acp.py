"""Tests for economic.virtuals_acp's real register_provider, access-request,
and evaluator wiring (FR-23..25)."""

from __future__ import annotations

import pytest

from kinostate.economic import virtuals_acp
from kinostate.economic.clients.virtuals_client import VirtualsAcpError
from kinostate.memory.tenant_store import BrandMemory
from kinostate.verification.visual_similarity import VisualSimilarityError


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


class _FakeJob:
    id = "job-1"
    client_address = "0xRequester"

    def __init__(self, service_requirement=None, deliverable=None):
        self.service_requirement = service_requirement
        self.deliverable = deliverable
        self.accepted = False
        self.rejected_reason = None
        self.delivered = None
        self.evaluation = None

    def accept(self, reason=None):
        self.accepted = True

    def reject(self, reason=None):
        self.rejected_reason = reason

    def deliver(self, deliverable):
        self.delivered = deliverable

    def evaluate(self, passed, reasoning):
        self.evaluation = (passed, reasoning)


def _open_memory(tmp_path) -> BrandMemory:
    return BrandMemory.open("acme", memory_dir=tmp_path / "brands")


def test_handle_access_request_delivers_eligible_reference_tier(tmp_path):
    memory = _open_memory(tmp_path)
    memory.set_reference("palette", {"palette_hex": ["#111111"]})
    job = _FakeJob(service_requirement={"tier": "reference", "key": "palette"})

    virtuals_acp.handle_access_request(memory, job)

    assert job.accepted is True
    assert job.delivered == {"data": {"palette_hex": ["#111111"]}}
    events = memory.read_events(limit=10)
    assert any(e["extra"].get("tier") == "reference" for e in events)


def test_handle_access_request_rejects_ineligible_tier(tmp_path):
    memory = _open_memory(tmp_path)
    job = _FakeJob(service_requirement={"tier": "hot", "key": "session"})

    virtuals_acp.handle_access_request(memory, job)

    assert job.accepted is False
    assert job.delivered is None
    assert "not eligible" in job.rejected_reason


def test_handle_access_request_rejects_missing_data(tmp_path):
    memory = _open_memory(tmp_path)
    job = _FakeJob(service_requirement={"tier": "reference", "key": "nonexistent"})

    virtuals_acp.handle_access_request(memory, job)

    assert job.accepted is False
    assert job.delivered is None


def test_evaluate_brand_consistency_passes(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_entity(
        "character",
        "aria",
        {"canonical_reference_asset": "https://img.example/aria.png", "confidence": {}},
    )
    monkeypatch.setattr(
        virtuals_acp, "check_visual_consistency", lambda ref, video: (True, 0.9, "similarity 0.9")
    )
    job = _FakeJob(deliverable={"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"})

    virtuals_acp.evaluate_brand_consistency(memory, job)

    assert job.evaluation == (True, "similarity 0.9")


def test_evaluate_brand_consistency_fails_without_reference(tmp_path):
    memory = _open_memory(tmp_path)
    memory.set_entity("character", "aria", {"confidence": {}})
    job = _FakeJob(deliverable={"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"})

    virtuals_acp.evaluate_brand_consistency(memory, job)

    assert job.evaluation[0] is False
    assert "no canonical_reference_asset" in job.evaluation[1]


def test_evaluate_brand_consistency_handles_check_failure(tmp_path, monkeypatch):
    memory = _open_memory(tmp_path)
    memory.set_entity(
        "character",
        "aria",
        {"canonical_reference_asset": "https://img.example/aria.png", "confidence": {}},
    )

    def _raise(ref, video):
        raise VisualSimilarityError("could not download video")

    monkeypatch.setattr(virtuals_acp, "check_visual_consistency", _raise)
    job = _FakeJob(deliverable={"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"})

    virtuals_acp.evaluate_brand_consistency(memory, job)

    assert job.evaluation[0] is False
    assert "could not download video" in job.evaluation[1]
