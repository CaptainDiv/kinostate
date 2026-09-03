"""Virtuals Protocol / ACP integration (FR-23..25).

`register_provider` (FR-23) proves the connection only. FR-24/FR-25 are
real, event-driven handlers rather than callable "issue a grant" stubs —
research confirmed ACP access grants aren't something Kinostate calls a
function to create; they're jobs *other* agents initiate against
Kinostate, dispatched through a live socket connection
(`economic.clients.virtuals_client.build_listening_client`) to these
handlers:

- `handle_access_request` (FR-24): runs from an `on_new_task` callback
  when another agent requests scoped, paid, read-only access to a brand's
  REFERENCE/WARM data.
- `evaluate_brand_consistency` (FR-25): runs from an `on_evaluate`
  callback, gating payment release on the same real brand-consistency
  check already used for QA (FR-15/16/17), not a new heuristic.

Both need an already-registered agent identity (dashboard signup) to ever
receive real events — see virtuals_client's module docstring. Exact
service_requirement/deliverable key names below are a Kinostate-defined
convention (the SDK leaves that shape to whatever the dashboard-configured
offering declares), not an SDK-mandated schema.
"""

from __future__ import annotations

from typing import Any

from kinostate.economic.clients.virtuals_client import build_client
from kinostate.memory.tenant_store import BrandMemory
from kinostate.verification.visual_similarity import VisualSimilarityError, check_visual_consistency

ELIGIBLE_GRANT_TIERS = {"reference", "warm"}


def register_provider(brand_id: str) -> dict[str, Any]:
    """Connect to Virtuals ACP as a registered provider (FR-23).

    Returns the connected agent's real entity_id/wallet address, plus the
    PRD-required job schema describing Kinostate's own generation request
    shape (brand_id, entity_ids, model_preference, resolution, duration,
    style, budget_ceiling) — that shape is defined here, not by Virtuals'
    own dashboard-configured service schema.
    """
    client = build_client()
    contract_client = client.contract_clients[0]
    return {
        "provider_id": f"acp-{contract_client.entity_id}",
        "wallet_address": contract_client.agent_wallet_address,
        "entity_id": contract_client.entity_id,
        "job_schema": {
            "brand_id": "str",
            "entity_ids": "list[str]",
            "model_preference": "str | None",
            "resolution": "str",
            "duration": "float",
            "style": "str",
            "budget_ceiling": "float",
        },
        "registered": True,
    }


def handle_access_request(memory: BrandMemory, job: Any) -> None:
    """Accept or reject a scoped, paid, read-only ACP access request (FR-24).

    job.service_requirement is expected to carry {"tier": "reference"|"warm",
    "key": ...} (reference) or {"tier": "warm", "kind": ..., "name": ...}
    (an entity). Any other tier is rejected outright — FR-24 explicitly
    scopes grants to REFERENCE/WARM only, never HOT/COLD/ARCHIVE. Every
    accepted grant is journaled (brand_id, requester, tier, key) per the
    PRD's own risk mitigation for cross-agent memory access.
    """
    requirement = job.service_requirement or {}
    tier = requirement.get("tier")

    if tier not in ELIGIBLE_GRANT_TIERS:
        job.reject(f"tier {tier!r} is not eligible for an ACP access grant")
        return

    if tier == "reference":
        key = requirement.get("key")
        data = memory.get_reference(key)
    else:
        kind = requirement.get("kind", "character")
        name = requirement.get("name")
        data = memory.get_entity(kind, name)

    if data is None:
        job.reject(f"no {tier} data found for the requested key")
        return

    job.accept()
    job.deliver({"data": data})

    memory.write_event(
        acted=[f"granted ACP access to {tier} data for job {getattr(job, 'id', '?')}"],
        extra={
            "brand_id": memory.brand_id,
            "requesting_agent": getattr(job, "client_address", None),
            "tier": tier,
            "requirement": requirement,
        },
    )


def evaluate_brand_consistency(memory: BrandMemory, job: Any) -> None:
    """Gate ACP payment release on real brand-consistency verification (FR-25).

    job's deliverable is expected to carry {"entity_name": ..., "output_asset": ...}.
    Reuses the same real CLIP-based check already proven for QA rather
    than a separate heuristic.
    """
    deliverable = getattr(job, "deliverable", None) or {}
    entity_name = deliverable.get("entity_name")
    output_asset = deliverable.get("output_asset")

    entity = memory.get_entity("character", entity_name) or {}
    reference_asset = entity.get("canonical_reference_asset")
    if not reference_asset:
        job.evaluate(False, f"no canonical_reference_asset on file for {entity_name!r}")
        return

    try:
        passed, _score, reasoning = check_visual_consistency(reference_asset, output_asset)
    except VisualSimilarityError as exc:
        job.evaluate(False, f"brand-consistency check failed to run: {exc}")
        return

    job.evaluate(passed, reasoning)
