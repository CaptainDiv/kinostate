"""Live adapter: canonical entities -> fal.ai's Seedance 2.0 Fast
Reference-to-Video model (`bytedance/seedance-2.0/fast/reference-to-video`).

Confirmed live against fal.ai's own model docs. Inputs: `prompt` and
`image_urls` (a flat list of reference images, up to 9) — a simpler, less
structured shape than Kling O1 Reference's per-element frontal/angle
objects, which is exactly why these stay two separate adapters despite both
now living on the same platform (FR-9, FR-11). Output:
`{"video": {"url": ...}, "seed": ...}`.
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter, PayloadValidationError
from kinostate.compiler.canonical import GenerationRequest

FAL_MODEL_PATH = "bytedance/seedance-2.0/fast/reference-to-video"


class SeedanceAdapter(ModelAdapter):
    name = "seedance"
    max_reference_entities = 9  # image_urls is documented as "up to 9"

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        missing = [entity.name for entity in request.entities if not entity.canonical_reference_asset]
        if missing:
            raise PayloadValidationError(
                f"{self.name} requires a canonical_reference_asset (image URL) for every "
                f"entity; missing for {missing}"
            )

        body = {
            "prompt": request.style_prompt,
            "image_urls": [entity.canonical_reference_asset for entity in request.entities],
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
