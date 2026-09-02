"""Stub adapter: canonical entities -> Pika "CREF" (character reference) shape.

Pika's CREF conditions on a single character reference per call, so this
adapter deliberately caps max_reference_entities at 1 — sending a
multi-entity request here should fail validation (FR-10), not silently
drop entities.
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter
from kinostate.compiler.canonical import GenerationRequest


class PikaAdapter(ModelAdapter):
    name = "pika"
    max_reference_entities = 1

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        primary = request.entities[0] if request.entities else None
        body = {
            "prompt": request.style_prompt,
            "aspectRatio": "16:9",
            "entities": (
                [{"crefImage": primary.canonical_reference_asset, "strength": 0.8}]
                if primary
                else []
            ),
        }
        return CompiledPayload(
            model_name=self.name, body=body, entity_count=len(request.entities)
        )
