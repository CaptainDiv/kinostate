"""FastAPI backend for the Brand Console (FR-26, FR-27, FR-28 backend surface).

No frontend is built in this pass — these endpoints exist so the
onboarding / generation / review flows can be exercised (curl, tests, or a
future UI) against the real memory + compiler + router + verification
pipeline.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from kinostate.compiler.canonical import Entity, GenerationRequest
from kinostate.memory.tenant_store import BrandMemory
from kinostate.router.router import RoutingPolicy, route_and_generate
from kinostate.verification.qa import run_qa

app = FastAPI(title="Kinostate", summary="Kinostate — memory-native AI video agent")


class OnboardBrandRequest(BaseModel):
    brand_id: str
    palette_hex: list[str]
    typography: str | None = None
    tone_rules: list[str] = []
    forbidden_content: list[str] = []


class AddEntityRequest(BaseModel):
    kind: str
    name: str
    description: str
    canonical_reference_asset: str | None = None
    forbidden_traits: list[str] = []


class GenerateRequestBody(BaseModel):
    brand_id: str
    entity_names: list[str]
    style_prompt: str
    duration_seconds: float = 4.0
    resolution: str = "1080p"
    model_override: str | None = None


class ReviewRequest(BaseModel):
    entity_name: str
    approved: bool


@app.post("/brands")
def onboard_brand(req: OnboardBrandRequest) -> dict:
    """FR-26: define REFERENCE data for a new brand."""
    memory = BrandMemory.open(req.brand_id)
    memory.set_reference(
        "palette",
        {
            "palette_hex": req.palette_hex,
            "typography": req.typography,
            "tone_rules": req.tone_rules,
            "forbidden_content": req.forbidden_content,
        },
    )
    return {"brand_id": req.brand_id, "status": "onboarded"}


@app.post("/brands/{brand_id}/entities")
def add_entity(brand_id: str, req: AddEntityRequest) -> dict:
    """FR-26: define an initial WARM entity (character/product)."""
    memory = BrandMemory.open(brand_id)
    entity = Entity(
        kind=req.kind,
        name=req.name,
        description=req.description,
        canonical_reference_asset=req.canonical_reference_asset,
        forbidden_traits=req.forbidden_traits,
    )
    memory.set_entity(
        "character",
        entity.name,
        {
            "kind": entity.kind,
            "description": entity.description,
            "canonical_reference_asset": entity.canonical_reference_asset,
            "forbidden_traits": entity.forbidden_traits,
            "approval_status": entity.approval_status,
            "confidence": {},
        },
    )
    return {"brand_id": brand_id, "entity": entity.name, "status": "created"}


@app.post("/generate")
def generate(req: GenerateRequestBody) -> dict:
    """FR-27: request a shot; route to a model, compile, generate, verify."""
    memory = BrandMemory.open(req.brand_id)

    entities: list[Entity] = []
    for name in req.entity_names:
        body = memory.get_entity("character", name)
        if body is None:
            raise HTTPException(status_code=404, detail=f"unknown entity {name!r} for brand {req.brand_id!r}")
        entities.append(
            Entity(
                kind=body.get("kind", "character"),
                name=name,
                description=body.get("description", ""),
                canonical_reference_asset=body.get("canonical_reference_asset"),
                forbidden_traits=body.get("forbidden_traits", []),
                approval_status=body.get("approval_status", "pending"),
            )
        )

    gen_request = GenerationRequest(
        brand_id=req.brand_id,
        entities=entities,
        style_prompt=req.style_prompt,
        duration_seconds=req.duration_seconds,
        resolution=req.resolution,
        model_override=req.model_override,
    )

    result = route_and_generate(memory, gen_request, RoutingPolicy())

    qa_result = None
    if entities:
        qa_result = run_qa(
            memory,
            entity_name=entities[0].name,
            model_name=result["model"],
            generation_id=result["generation_id"],
            output_asset=result["output_asset"],
        )

    return {
        "generation_id": result["generation_id"],
        "model": result["model"],
        "output_asset": result["output_asset"],
        "qa_passed": qa_result.passed if qa_result else None,
        "qa_reasoning": qa_result.reasoning if qa_result else [],
    }


@app.post("/brands/{brand_id}/generate/{generation_id}/review")
def review_generation(brand_id: str, generation_id: str, req: ReviewRequest) -> dict:
    """FR-28: brand approves/rejects an output, updating entity approval status."""
    memory = BrandMemory.open(brand_id)
    entity = memory.get_entity("character", req.entity_name)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"unknown entity {req.entity_name!r}")

    entity["approval_status"] = "approved" if req.approved else "rejected"
    memory.set_entity("character", req.entity_name, entity)
    memory.write_event(
        evaluated=[f"brand review for generation {generation_id}: {'approved' if req.approved else 'rejected'}"],
        extra={"generation_id": generation_id, "entity_name": req.entity_name, "approved": req.approved},
    )
    return {"generation_id": generation_id, "entity_name": req.entity_name, "approval_status": entity["approval_status"]}
