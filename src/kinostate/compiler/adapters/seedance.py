"""Live adapter: canonical entities -> fal.ai's Seedance 2.0 Fast
Reference-to-Video model (`bytedance/seedance-2.0/fast/reference-to-video`).

Confirmed live against fal.ai's own model docs. Inputs: `prompt` and
`image_urls` (a flat list of reference images, up to 9) — a simpler, less
structured shape than Kling O1 Reference's per-element frontal/angle
objects, which is exactly why these stay two separate adapters despite both
now living on the same platform (FR-9, FR-11). Output:
`{"video": {"url": ...}, "seed": ...}`.

`image_urls` now includes every angle image each entity has (primary +
additional_reference_images), not just one per entity, since a single
photo per entity leaves the model guessing about anything not visible in
that one frame. The prompt also folds in each entity's description and
forbidden traits (see `base_adapter.describe_entity`).
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter, PayloadValidationError, describe_entity
from kinostate.compiler.canonical import GenerationRequest

FAL_MODEL_PATH = "bytedance/seedance-2.0/fast/reference-to-video"

MAX_TOTAL_REFERENCE_IMAGES = 9  # image_urls is documented as "up to 9" total, not per entity


class SeedanceAdapter(ModelAdapter):
    name = "seedance"
    max_reference_entities = 9

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        missing = [entity.name for entity in request.entities if not entity.canonical_reference_asset]
        if missing:
            raise PayloadValidationError(
                f"{self.name} requires a canonical_reference_asset (image URL) for every "
                f"entity; missing for {missing}"
            )

        context = " ".join(filter(None, (describe_entity(entity) for entity in request.entities)))
        prompt = " ".join(filter(None, [request.style_prompt, context]))

        image_urls = []
        for entity in request.entities:
            image_urls.append(entity.canonical_reference_asset)
            image_urls.extend(entity.additional_reference_images)

        body = {"prompt": prompt, "image_urls": image_urls}
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))

    def validate(self, payload: CompiledPayload) -> None:
        super().validate(payload)
        total_images = len(payload.body["image_urls"])
        if total_images > MAX_TOTAL_REFERENCE_IMAGES:
            raise PayloadValidationError(
                f"{self.name} supports at most {MAX_TOTAL_REFERENCE_IMAGES} total reference "
                f"images (across all entities), got {total_images}"
            )
