"""Live adapter: canonical entities -> fal.ai's Minimax H3 Reference-to-Video
model (`minimax/h3/reference-to-video`).

Confirmed via fal.ai's own live OpenAPI schema (not docs pages — a prior
lookup pass this session caught WebFetch/WebSearch hallucinating values
for these exact kinds of pages). Inputs: `prompt` and `reference_image_urls`
(a flat list, up to 9, no per-image tagging needed — the model infers
subject/style references from list order, unlike Kling/xai's @-tag
convention). Output: `{"video": {"url": ...}}`.

Cost note: this model's own default resolution is "2K" ($0.13/sec) —
2.6x the $0.05/sec 480p rate it was chosen for. This adapter explicitly
requests "480P" unless told otherwise, rather than trusting that default.
duration is a free integer (5-15), not an enum — its real floor (5s) is
higher than Kling's (3s) or Seedance's (4s).
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

FAL_MODEL_PATH = "minimax/h3/reference-to-video"

MIN_DURATION_SECONDS = 5
MAX_DURATION_SECONDS = 15
MAX_TOTAL_REFERENCE_IMAGES = 9  # reference_image_urls is documented as max 9 total

DEFAULT_RESOLUTION = "480P"  # cheapest tier; the vendor's own default ("2K") costs 2.6x more
_RESOLUTION_MAP = {"480p": "480P", "768p": "768P", "2k": "2K", "4k": "4K"}


class MinimaxH3Adapter(ModelAdapter):
    name = "minimax_h3"
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

        context = " ".join(filter(None, (describe_entity(entity) for entity in request.entities)))
        prompt = " ".join(filter(None, [request.style_prompt, context]))

        image_urls = []
        for entity in request.entities:
            image_urls.append(entity.canonical_reference_asset)
            image_urls.extend(entity.additional_reference_images)

        body = {"prompt": prompt, "reference_image_urls": image_urls, "duration": duration, "resolution": resolution}
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))

    def validate(self, payload: CompiledPayload) -> None:
        super().validate(payload)
        total_images = len(payload.body["reference_image_urls"])
        if total_images > MAX_TOTAL_REFERENCE_IMAGES:
            raise PayloadValidationError(
                f"{self.name} supports at most {MAX_TOTAL_REFERENCE_IMAGES} total reference "
                f"images (across all entities), got {total_images}"
            )
