"""Live adapter: canonical entities -> fal.ai's Kling O1 Reference model
(`fal-ai/kling-video/o1/standard/reference-to-video`).

Confirmed live against fal.ai's own model docs. Inputs: `prompt` (must tag
each tracked character in the text itself, e.g. "@Element1" — fal's docs:
"Take @Element1, @Element2 to reference elements... in order") and
`elements` (a list of {frontal_image_url, reference_image_urls} objects,
one per tracked character/object). Output: `{"video": {"url": ..., ...}}`.

Each element now carries every angle image the canonical Entity has
(`canonical_reference_asset` as the frontal image, `additional_reference_
images` as `reference_image_urls`) — this model genuinely supports several
angle images per element, and a single photo alone leaves the model
guessing about anything not visible in that one frame. The prompt also
folds in each entity's description and forbidden traits (see
`base_adapter.describe_entity`), since neither was previously reaching
the model at all despite being stored in memory.

`duration` (confirmed via fal.ai's live OpenAPI schema, not the docs
pages — a websearch sanity-check caught itself hallucinating values for
this exact field) is a string enum "3".."10" seconds, default "5".
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import (
    CompiledPayload,
    ModelAdapter,
    PayloadValidationError,
    describe_entity,
    resolve_duration_seconds,
)
from kinostate.compiler.canonical import GenerationRequest

FAL_MODEL_PATH = "fal-ai/kling-video/o1/standard/reference-to-video"

ALLOWED_DURATIONS_SECONDS = {str(s) for s in range(3, 11)}  # "3".."10", per fal's OpenAPI schema


class KlingO1ReferenceAdapter(ModelAdapter):
    name = "kling_o1_reference"
    # fal's docs describe "up to 7 simultaneous inputs" combining tracked
    # elements and style images; treating entities as elements-only, 7 is a
    # conservative upper bound pending a real multi-entity test.
    max_reference_entities = 7

    def compile(self, request: GenerationRequest) -> CompiledPayload:
        missing = [entity.name for entity in request.entities if not entity.canonical_reference_asset]
        if missing:
            raise PayloadValidationError(
                f"{self.name} requires a canonical_reference_asset (image URL) for every "
                f"entity; missing for {missing}"
            )

        duration = resolve_duration_seconds(self.name, request.duration_seconds, ALLOWED_DURATIONS_SECONDS)

        tags = " ".join(f"@Element{i + 1}" for i in range(len(request.entities)))
        context = " ".join(filter(None, (describe_entity(entity) for entity in request.entities)))
        prompt = " ".join(filter(None, [request.style_prompt, tags, context]))

        elements = []
        for entity in request.entities:
            element = {"frontal_image_url": entity.canonical_reference_asset}
            if entity.additional_reference_images:
                element["reference_image_urls"] = entity.additional_reference_images
            elements.append(element)

        body = {"prompt": prompt, "elements": elements, "duration": duration}
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
