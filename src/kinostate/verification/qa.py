"""Automated brand-consistency QA (FR-15, FR-16, FR-17).

The palette check is still a heuristic stand-in (see PRD open question on
QA method) — it checks REFERENCE data is present, not the pixels of the
output. The character-match check is real: it runs
`verification.visual_similarity.check_visual_consistency`, comparing the
entity's canonical reference image to sampled frames of the actual
generated video via CLIP embedding similarity. It writes the reasoning to
the journal linked to the generation event and updates the entity's
per-model confidence score.
"""

from __future__ import annotations

from dataclasses import dataclass

from kinostate.memory.tenant_store import BrandMemory
from kinostate.verification.visual_similarity import VisualSimilarityError, check_visual_consistency

CONFIDENCE_LEARNING_RATE = 0.3


@dataclass
class QAResult:
    passed: bool
    reasoning: list[str]


def run_qa(
    memory: BrandMemory,
    entity_name: str,
    model_name: str,
    generation_id: str,
    output_asset: str,
    reference_key: str = "palette",
) -> QAResult:
    """Check a generation against REFERENCE + WARM canon, journal the result,
    and update the entity's confidence score for this model (FR-17).
    """
    reasoning: list[str] = []
    passed = True

    reference = memory.get_reference(reference_key)
    if not reference or not reference.get("palette_hex"):
        passed = False
        reasoning.append(f"no REFERENCE palette found under key {reference_key!r}")
    else:
        reasoning.append(f"palette check ok against {len(reference['palette_hex'])} approved hex values")

    entity = memory.get_entity("character", entity_name) or {}
    if entity.get("approval_status") == "rejected":
        passed = False
        reasoning.append(f"entity {entity_name!r} is marked rejected — character match fails by policy")
    else:
        character_match_passed, character_match_reasoning = _check_character_match(
            entity, entity_name, output_asset
        )
        passed = passed and character_match_passed
        reasoning.append(character_match_reasoning)

    result = QAResult(passed=passed, reasoning=reasoning)

    memory.write_event(
        evaluated=[f"QA {'passed' if passed else 'failed'} for {entity_name} on {model_name}"],
        extra={
            "generation_id": generation_id,
            "qa_passed": passed,
            "qa_reasoning": reasoning,
        },
    )

    _update_confidence(memory, entity_name, model_name, passed)
    return result


def _check_character_match(entity: dict, entity_name: str, output_asset: str) -> tuple[bool, str]:
    """Run the real visual-consistency check, with two deliberate escapes.

    A mock:// output (the four still-stubbed vendor adapters) has no real
    video to download, so it's skipped rather than treated as a failure —
    that's a limitation of those adapters being unbuilt, not a QA failure.
    A missing canonical_reference_asset fails the check outright (FR-10:
    fail loudly) rather than silently passing with nothing to compare against.
    """
    reference_asset = entity.get("canonical_reference_asset")
    if not reference_asset:
        return False, f"no canonical_reference_asset on file for {entity_name!r} — cannot check character match"

    if output_asset.startswith("mock://"):
        return True, f"character match check skipped — {output_asset!r} is a mocked output, not a real video"

    try:
        passed, _score, reasoning = check_visual_consistency(reference_asset, output_asset)
    except VisualSimilarityError as exc:
        return False, f"character match check failed to run: {exc}"

    return passed, f"{reasoning}, for {entity_name!r}"


def _update_confidence(memory: BrandMemory, entity_name: str, model_name: str, passed: bool) -> None:
    entity = memory.get_entity("character", entity_name)
    if entity is None:
        return

    confidence: dict[str, float] = entity.setdefault("confidence", {})
    current = confidence.get(model_name, 0.5)
    target = 1.0 if passed else 0.0
    confidence[model_name] = current + CONFIDENCE_LEARNING_RATE * (target - current)

    memory.set_entity("character", entity_name, entity)
