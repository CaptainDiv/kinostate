"""Stub adapter: canonical entities -> Kling "Elements" shape."""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter
from kinostate.compiler.canonical import GenerationRequest


class KlingAdapter(ModelAdapter):
    name = "kling"
    max_reference_entities = 4

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        body = {
            "prompt": request.style_prompt,
            "duration": request.duration_seconds,
            "elements": [
                {
                    "elementId": entity.name,
                    "image": entity.canonical_reference_asset,
                    "category": entity.kind,
                }
                for entity in request.entities
            ],
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
