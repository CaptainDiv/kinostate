"""Live adapter: canonical entities -> fal.ai's Grok Imagine Video
Reference-to-Video model, v1 (`xai/grok-imagine-video/reference-to-video`
— NOT the v1.5 endpoint, which is pricier despite being newer).

Confirmed via fal.ai's own live OpenAPI schema (not docs pages). Inputs:
`prompt` (must tag each reference image inline, e.g. "@Image1" — same
@-tag convention as Kling O1 Reference's @ElementN) and
`reference_image_urls` (a flat list, 1-7, **required** — this model has
no prompt-only mode, unlike the other real adapters). Output:
`{"video": {"url": ...}}`.

duration is a free integer (1-10), not an enum. resolution defaults to
"480p" already (the cheap tier), set explicitly here anyway for the same
predictability reasons as the other adapters rather than relying on it
silently staying that way.
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import (
    CompiledPayload,
    ModelAdapter,
    PayloadValidationError,
    describe_entity,
    resolve_duration_in_range,
)
from kinostate.compiler.canonical import GenerationRequest

FAL_MODEL_PATH = "xai/grok-imagine-video/reference-to-video"

MIN_DURATION_SECONDS = 1
MAX_DURATION_SECONDS = 10
MAX_TOTAL_REFERENCE_IMAGES = 7  # reference_image_urls is documented as required, 1-7

DEFAULT_RESOLUTION = "480p"  # already the vendor's cheap default; set explicitly for predictability
_RESOLUTION_MAP = {"480p": "480p", "720p": "720p"}


class XaiGrokImagineVideoAdapter(ModelAdapter):
    name = "xai_grok_imagine_video"
    max_reference_entities = MAX_TOTAL_REFERENCE_IMAGES

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        if not request.entities:
            raise PayloadValidationError(f"{self.name} requires at least one entity with a reference image")

        missing = [entity.name for entity in request.entities if not entity.canonical_reference_asset]
        if missing:
            raise PayloadValidationError(
                f"{self.name} requires a canonical_reference_asset (image URL) for every "
                f"entity; missing for {missing}"
            )

        duration = resolve_duration_in_range(self.name, request.duration_seconds, MIN_DURATION_SECONDS, MAX_DURATION_SECONDS)
        resolution = _RESOLUTION_MAP.get(request.resolution.lower(), DEFAULT_RESOLUTION)

        tags = " ".join(f"@Image{i + 1}" for i in range(len(request.entities)))
        context = " ".join(filter(None, (describe_entity(entity) for entity in request.entities)))
        prompt = " ".join(filter(None, [request.style_prompt, tags, context]))

        image_urls = []
        for entity in request.entities:
            image_urls.append(entity.canonical_reference_asset)
            image_urls.extend(entity.additional_reference_images)

        body = {
            "prompt": prompt,
            "reference_image_urls": image_urls,
            "duration": duration,
            "resolution": resolution,
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))

    def validate(self, payload: CompiledPayload) -> None:
        super().validate(payload)
        total_images = len(payload.body["reference_image_urls"])
        if total_images > MAX_TOTAL_REFERENCE_IMAGES:
            raise PayloadValidationError(
                f"{self.name} supports at most {MAX_TOTAL_REFERENCE_IMAGES} total reference "
                f"images (across all entities), got {total_images}"
            )
