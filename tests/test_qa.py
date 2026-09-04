"""Tests for verification.qa's real character-match integration (FR-15..17).

The real visual check itself is covered in test_visual_similarity.py; here
`check_visual_consistency` is monkeypatched so these stay fast/offline and
focus on qa.py's own orchestration: the mock-output skip, the
missing-reference failure, and the rejected-entity short-circuit.
"""

from __future__ import annotations

from kinostate.memory.tenant_store import BrandMemory
from kinostate.verification import qa as qa_module
from kinostate.verification.qa import run_qa


def _seed_memory(
    tmp_path,
    *,
    canonical_reference_asset="https://img.example/aria.png",
    additional_reference_images=None,
    approval_status="approved",
):
    memory = BrandMemory.open("acme", memory_dir=tmp_path / "brands")
    memory.set_reference("palette", {"palette_hex": ["#111111"]})
    memory.set_entity(
        "character",
        "aria",
        {
            "kind": "character",
            "description": "test",
            "canonical_reference_asset": canonical_reference_asset,
            "additional_reference_images": additional_reference_images or [],
            "approval_status": approval_status,
            "confidence": {},
        },
    )
    return memory


def test_run_qa_skips_character_match_for_mock_output(tmp_path):
    memory = _seed_memory(tmp_path)

    result = run_qa(memory, "aria", "runway", "gen-1", "mock://runway/abc123")

    assert result.passed is True
    assert any("mocked output" in line for line in result.reasoning)


def test_run_qa_fails_when_no_reference_asset_on_file(tmp_path):
    memory = _seed_memory(tmp_path, canonical_reference_asset=None)

    result = run_qa(memory, "aria", "seedance", "gen-2", "https://cdn.fal/real.mp4")

    assert result.passed is False
    assert any("no canonical_reference_asset" in line for line in result.reasoning)


def test_run_qa_uses_real_visual_check_for_real_output(tmp_path, monkeypatch):
    memory = _seed_memory(tmp_path)
    monkeypatch.setattr(
        qa_module,
        "check_visual_consistency",
        lambda reference, video, **kwargs: (True, 0.9, "visual similarity: 0.900 >= threshold 0.75"),
    )

    result = run_qa(memory, "aria", "seedance", "gen-3", "https://cdn.fal/real.mp4")

    assert result.passed is True
    assert any("0.900" in line for line in result.reasoning)


def test_run_qa_fails_when_real_visual_check_fails(tmp_path, monkeypatch):
    memory = _seed_memory(tmp_path)
    monkeypatch.setattr(
        qa_module,
        "check_visual_consistency",
        lambda reference, video, **kwargs: (False, 0.4, "visual similarity: 0.400 < threshold 0.75"),
    )

    result = run_qa(memory, "aria", "seedance", "gen-4", "https://cdn.fal/real.mp4")

    assert result.passed is False


def test_run_qa_passes_all_reference_images_to_visual_check(tmp_path, monkeypatch):
    memory = _seed_memory(tmp_path, additional_reference_images=["https://img.example/aria-side.png"])
    captured = {}

    def _fake_check(reference_assets, video, **kwargs):
        captured["reference_assets"] = reference_assets
        return True, 0.9, "similarity 0.9"

    monkeypatch.setattr(qa_module, "check_visual_consistency", _fake_check)

    run_qa(memory, "aria", "seedance", "gen-6", "https://cdn.fal/real.mp4")

    assert captured["reference_assets"] == ["https://img.example/aria.png", "https://img.example/aria-side.png"]


def test_run_qa_rejected_entity_short_circuits_before_visual_check(tmp_path, monkeypatch):
    memory = _seed_memory(tmp_path, approval_status="rejected")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("check_visual_consistency should not run for a rejected entity")

    monkeypatch.setattr(qa_module, "check_visual_consistency", _should_not_be_called)

    result = run_qa(memory, "aria", "seedance", "gen-5", "https://cdn.fal/real.mp4")

    assert result.passed is False
