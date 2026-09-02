"""Live adapter: canonical entities -> fal.ai's Kling O1 Reference model
(`fal-ai/kling-video/o1/standard/reference-to-video`).

Confirmed live against fal.ai's own model docs. Inputs: `prompt` (must tag
each tracked character in the text itself, e.g. "@Element1" — fal's docs:
"Take @Element1, @Element2 to reference elements... in order") and
`elements` (a list of {frontal_image_url, reference_image_urls} objects,
one per tracked character/object). Output: `{"video": {"url": ..., ...}}`.

Each canonical Entity only carries one reference image today
(`Entity.canonical_reference_asset`), so each element gets a frontal image
only, with no extra angle images — a limitation of the canonical schema,
not of this model (which supports several angle images per element).
"""

from __future__ import annotations

from kinostate.compiler.base_adapter import CompiledPayload, ModelAdapter, PayloadValidationError
from kinostate.compiler.canonical import GenerationRequest

FAL_MODEL_PATH = "fal-ai/kling-video/o1/standard/reference-to-video"


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

        tags = " ".join(f"@Element{i + 1}" for i in range(len(request.entities)))
        body = {
            "prompt": f"{request.style_prompt} {tags}".strip(),
            "elements": [{"frontal_image_url": entity.canonical_reference_asset} for entity in request.entities],
        }
        return CompiledPayload(model_name=self.name, body=body, entity_count=len(request.entities))
