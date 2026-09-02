"""Automated brand-consistency QA (FR-15, FR-16, FR-17).

This is a heuristic stand-in, not a real vision-model check (see PRD open
question on QA method). It exists to prove the data flow: run a check,
write the reasoning to the journal linked to the generation event, and
update the entity's per-model confidence score. Swapping in a real
vision-based check only touches `run_qa`'s body.
"""

from __future__ import annotations

from dataclasses import dataclass

from kinostate.memory.tenant_store import BrandMemory

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
        reasoning.append(f"character match ok against canonical reference for {entity_name!r}")

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


def _update_confidence(memory: BrandMemory, entity_name: str, model_name: str, passed: bool) -> None:
    entity = memory.get_entity("character", entity_name)
    if entity is None:
        return

    confidence: dict[str, float] = entity.setdefault("confidence", {})
    current = confidence.get(model_name, 0.5)
    target = 1.0 if passed else 0.0
    confidence[model_name] = current + CONFIDENCE_LEARNING_RATE * (target - current)

    memory.set_entity("character", entity_name, entity)
