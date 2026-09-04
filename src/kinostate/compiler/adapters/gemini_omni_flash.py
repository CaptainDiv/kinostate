"""Live adapter: canonical entities -> fal.ai's Gemini Omni Flash
Reference-to-Video model (`google/gemini-omni-flash/v1.1/reference-to-video`).

Confirmed via fal.ai's own live OpenAPI schema (not docs pages). Inputs:
`prompt` (must tag each reference image inline as "<IMAGE_REF_0>",
"<IMAGE_REF_1>", ... — 0-indexed, confirmed exact syntax from the
model's own schema examples, a third distinct convention alongside
Kling/xai's @-tags and minimax's untagged flat list) and `image_urls`
(note: not "reference_image_urls" — yet another real vendor-specific
field name), a flat list, up to 10, optional (works with zero entities,
unlike xai_grok_imagine_video). Output: `{"video": {"url": ...}}`.

Cost note: this model's own default resolution is "720p" ($0.10/sec) —
more than 3x the $0.03/sec 360p rate it was chosen for. This adapter
explicitly requests "360p" unless told otherwise. duration is a free
integer (3-10), not an enum.
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

FAL_MODEL_PATH = "google/gemini-omni-flash/v1.1/reference-to-video"

MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 10
MAX_TOTAL_REFERENCE_IMAGES = 10  # image_urls is documented as max 10

DEFAULT_RESOLUTION = "360p"  # cheapest tier; the vendor's own default ("720p") costs 3.3x more
# "480p" (this project's own canonical default) isn't one of this model's real
# tiers at all, so it deliberately falls through to the cheapest tier below.
_RESOLUTION_MAP = {"360p": "360p", "720p": "720p", "1080p": "1080p", "4k": "4k"}


class GeminiOmniFlashAdapter(ModelAdapter):
    name = "gemini_omni_flash"
    max_reference_entities = MAX_TOTAL_REFERENCE_IMAGES

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        missing = [entity.name for entity in request.entities if not entity.canonical_reference_asset]
        if missing:
            raise PayloadValidationError(
                f"{self.name} requires a canonical_reference_asset (image URL) for every "
                f"entity; missing for {missing}"
            )

        duration = resolve_duration_in_range(self.name, request.duration_seconds, MIN_DURATION_SECONDS, MAX_DURATION_SECONDS)
        resolution = _RESOLUTION_MAP.get(request.resolution.lower(), DEFAULT_RESOLUTION)

        image_urls = []
        for entity in request.entities:
            image_urls.append(entity.canonical_reference_asset)
            image_urls.extend(entity.additional_reference_images)

        tags = " ".join(f"<IMAGE_REF_{i}>" for i in range(len(image_urls)))
        context = " ".join(filter(None, (describe_entity(entity) for entity in request.entities)))
        prompt = " ".join(filter(None, [request.style_prompt, tags, context]))

        body = {"prompt": prompt, "image_urls": image_urls, "duration": duration, "resolution": resolution}
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))

    def validate(self, payload: CompiledPayload) -> None:
        super().validate(payload)
        total_images = len(payload.body["image_urls"])
        if total_images > MAX_TOTAL_REFERENCE_IMAGES:
            raise PayloadValidationError(
                f"{self.name} supports at most {MAX_TOTAL_REFERENCE_IMAGES} total reference "
                f"images (across all entities), got {total_images}"
            )
