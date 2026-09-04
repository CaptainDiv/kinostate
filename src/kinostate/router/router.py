"""Model selection + generation orchestration (FR-12, FR-13, FR-14).

Most adapters are still stubs — `_call_model` returns a mock output
reference for them so the full pipeline (route -> compile -> validate ->
"generate" -> journal) stays exercisable end-to-end without credentials.
`minimax_h3`, `xai_grok_imagine_video`, and `gemini_omni_flash` are real:
they're routed through fal.ai (see `router.clients.fal_client`) instead
of mocked. `kling_o1_reference`/`seedance` were real in an earlier pass
but are dormant now (cheaper alternatives replaced them) — the adapter
files stay, just no longer listed in REAL_MODELS below, so they mock
like every other stub adapter. Wiring up a new live model later means one
adapter file (exporting its fal model path) plus one new REAL_MODELS
entry below — nothing else in this module changes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from kinostate.compiler.adapters import ADAPTERS
from kinostate.compiler.adapters.gemini_omni_flash import FAL_MODEL_PATH as GEMINI_OMNI_FLASH_MODEL_PATH
from kinostate.compiler.adapters.minimax_h3 import FAL_MODEL_PATH as MINIMAX_H3_MODEL_PATH
from kinostate.compiler.adapters.xai_grok_imagine_video import FAL_MODEL_PATH as XAI_GROK_MODEL_PATH
from kinostate.compiler.base_adapter import ModelAdapter
from kinostate.compiler.canonical import GenerationRequest
from kinostate.memory.tenant_store import BrandMemory
from kinostate.router.clients.fal_client import FalError, extract_output_url, run_model

DEFAULT_CONFIDENCE = 0.5

# Adapter name -> its fal.ai model path. Only adapters listed here make a
# real call; every other adapter name in ADAPTERS still gets the mock://
# stub below. Unlike wireflow, fal needs no per-model workflow id — just
# FAL_KEY (checked inside fal_client) and the model's own path.
REAL_MODELS: dict[str, str] = {
    "minimax_h3": MINIMAX_H3_MODEL_PATH,
    "xai_grok_imagine_video": XAI_GROK_MODEL_PATH,
    "gemini_omni_flash": GEMINI_OMNI_FLASH_MODEL_PATH,
}


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
    """Generate via fal.ai for live-integrated models, mock otherwise.

    Raises FalError (e.g. FAL_KEY missing, or the request itself failing)
    rather than silently falling back to a mock result — a real model that
    quietly returned fake output would be worse than an explicit error.
    """
    model_path = REAL_MODELS.get(adapter.name)
    if model_path is None:
        return f"mock://{adapter.name}/{uuid.uuid4()}"

    result = run_model(model_path, payload_body)
    return extract_output_url(result)


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
