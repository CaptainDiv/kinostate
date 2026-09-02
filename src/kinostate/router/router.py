"""Model selection + generation orchestration (FR-12, FR-13, FR-14).

No live video model API calls happen here yet — `_call_model` is a stub that
returns a mock output reference so the full pipeline (route -> compile ->
validate -> "generate" -> journal) is exercisable end-to-end without
credentials. Swapping in real HTTP calls only touches `_call_model`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from kinostate.compiler.adapters import ADAPTERS
from kinostate.compiler.base_adapter import ModelAdapter
from kinostate.compiler.canonical import GenerationRequest
from kinostate.memory.tenant_store import BrandMemory

DEFAULT_CONFIDENCE = 0.5


@dataclass
class RoutingPolicy:
    """Configurable router priority (FR-12)."""

    available_models: list[str] = field(default_factory=lambda: list(ADAPTERS.keys()))
    min_confidence_threshold: float = 0.3  # FR-18: deprioritize below this


def pick_model(memory: BrandMemory, entity_name: str, policy: RoutingPolicy) -> str:
    """Pick the highest-confidence available model for this entity.

    Confidence scores live on the WARM entity body as
    entity["confidence"][model_name], updated by the verification layer
    (FR-17). Models below policy.min_confidence_threshold are skipped
    (FR-18) unless every candidate is below threshold, in which case the
    least-bad one is still returned rather than failing the job outright.
    """
    entity = memory.get_entity("character", entity_name) or {}
    confidence: dict[str, float] = entity.get("confidence", {})

    scored = [(model, confidence.get(model, DEFAULT_CONFIDENCE)) for model in policy.available_models]
    above_threshold = [pair for pair in scored if pair[1] >= policy.min_confidence_threshold]
    candidates = above_threshold or scored
    return max(candidates, key=lambda pair: pair[1])[0]


def _call_model(adapter: ModelAdapter, payload_body: dict[str, Any]) -> str:
    """Stub generation call. Returns a mock output asset reference."""
    return f"mock://{adapter.name}/{uuid.uuid4()}"


def route_and_generate(
    memory: BrandMemory,
    request: GenerationRequest,
    policy: RoutingPolicy | None = None,
) -> dict[str, Any]:
    """Route a GenerationRequest to a model, compile+validate, "generate", and journal it.

    Honors request.model_override for manual selection (FR-13). Every call
    writes one COLD journal event regardless of outcome (FR-14).
    """
    policy = policy or RoutingPolicy()
    primary_entity = request.entities[0].name if request.entities else None

    model_name = request.model_override or (
        pick_model(memory, primary_entity, policy) if primary_entity else policy.available_models[0]
    )
    adapter_cls = ADAPTERS[model_name]
    adapter = adapter_cls()

    payload = adapter.compile(request)
    adapter.validate(payload)
    output_asset = _call_model(adapter, payload.body)

    generation_id = str(uuid.uuid4())
    memory.write_event(
        acted=[f"generated shot for {primary_entity or 'unknown entity'} via {model_name}"],
        extra={
            "generation_id": generation_id,
            "brand_id": request.brand_id,
            "model": model_name,
            "compiled_payload": payload.body,
            "output_asset": output_asset,
            "cost_usdc": None,  # filled in by economic layer once wired up
            "qa_result": None,  # filled in by verification layer next
        },
    )

    return {
        "generation_id": generation_id,
        "model": model_name,
        "payload": payload,
        "output_asset": output_asset,
    }
