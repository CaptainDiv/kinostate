"""Stub adapter: canonical entities -> Luma "Character Seed" shape."""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter
from kinostate.compiler.canonical import GenerationRequest


class LumaAdapter(ModelAdapter):
    name = "luma"
    max_reference_entities = 4

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        body = {
            "prompt": request.style_prompt,
            "duration": request.duration_seconds,
            "entities": [
                {
                    "characterSeed": entity.canonical_reference_asset,
                    "label": entity.name,
                }
                for entity in request.entities
            ],
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
