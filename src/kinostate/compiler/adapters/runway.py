"""Stub adapter: canonical entities -> Runway Gen-4 "References" shape.

Not wired to a live Runway API call — compile() only produces the payload
shape Runway's References feature documents, so the compiler/validation
pipeline can be exercised end-to-end without credentials.
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter
from kinostate.compiler.canonical import GenerationRequest


class RunwayAdapter(ModelAdapter):
    name = "runway"
    max_reference_entities = 3  # Gen-4 References supports multiple reference images

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        body = {
            "promptText": request.style_prompt,
            "duration": request.duration_seconds,
            "ratio": "16:9" if request.resolution == "1080p" else "9:16",
            "entities": [
                {
                    "tag": entity.name,
                    "referenceImage": entity.canonical_reference_asset,
                    "type": entity.kind,
                }
                for entity in request.entities
            ],
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
