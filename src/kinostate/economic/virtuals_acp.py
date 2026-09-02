"""Virtuals Protocol / ACP stubs (FR-23..25).

Not wired to a live Virtuals ACP registry — no provider account configured
for this scaffold. Mirrors the shape a real ACP client would return.
"""

from __future__ import annotations

from typing import Any


def register_provider(brand_id: str) -> dict[str, Any]:
    """Stub ACP Provider registration (FR-23) with the job schema from PRD FR-23:
    brand_id, entity_ids, model_preference, resolution, duration, style, budget_ceiling.
    """
    return {
        "provider_id": f"acp-stub-{brand_id}",
        "job_schema": {
            "brand_id": "str",
            "entity_ids": "list[str]",
            "model_preference": "str | None",
            "resolution": "str",
            "duration": "float",
            "style": "str",
            "budget_ceiling": "float",
        },
        "registered": False,
        "mock": True,
    }


def grant_access(brand_id: str, tiers: list[str], requesting_agent_id: str) -> dict[str, Any]:
    """Stub scoped, paid, read-only access grant (FR-24) gated by an
    Evaluator role (FR-25) in a real implementation.
    """
    return {
        "grant_id": f"grant-stub-{brand_id}-{requesting_agent_id}",
        "brand_id": brand_id,
        "tiers": tiers,
        "requesting_agent_id": requesting_agent_id,
        "escrow_settled": False,
        "mock": True,
    }
