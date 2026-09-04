"""Virtuals Protocol / ACP integration (FR-23..25), built on ACP v2 via the acp CLI.

The dashboard now only issues ACP v2 agent identities (own on-chain
wallet + a browser-approved EC P-256 signer) — the `virtuals-acp` Python
package this module used to depend on targets v1 (numeric entity_id +
server-whitelisted wallet) and cannot authenticate as a v2 agent at all.
Every function here now shells out to Virtuals' own `acp` CLI via
`economic.clients.acp_cli`, which correctly handles v2's account-
abstraction signing — see that module's docstring for why.

`register_provider` (FR-23) proves the connection only.
`handle_access_request`/`deliver_access_grant` (FR-24) and
`evaluate_brand_consistency` (FR-25) are real handlers invoked per
drained event (see acp_cli.drain_events) — there's no persistent socket
callback in the CLI-based model, just a poll-once call. Accept and
deliver are two separate functions, not one: confirmed live against a
real job that the protocol itself rejects a deliverable submitted before
the buyer funds the accepted budget. Exact event/requirement/deliverable
key names below are a Kinostate-defined convention, not a schema the CLI
mandates.
"""

from __future__ import annotations

from typing import Any

from kinostate.economic.clients.acp_cli import accept_job, complete_job, reject_job, submit_deliverable, whoami
from kinostate.memory.tenant_store import BrandMemory
from kinostate.verification.visual_similarity import VisualSimilarityError, check_visual_consistency

ELIGIBLE_GRANT_TIERS = {"reference", "warm"}
DEFAULT_GRANT_PRICE_USDC = 0.01


def register_provider(brand_id: str) -> dict[str, Any]:
    """Connect to Virtuals ACP as a registered provider (FR-23).

    Returns the real active agent's identity (whatever `acp agent whoami`
    reports for a v2 agent — no more entity_id, that was v1-specific),
    plus the PRD-required job schema describing Kinostate's own
    generation request shape (brand_id, entity_ids, model_preference,
    resolution, duration, style, budget_ceiling) — that shape is defined
    here, not by Virtuals' own dashboard-configured offering.
    """
    identity = whoami()
    return {
        "agent": identity,
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


def _fetch_grant_data(memory: BrandMemory, requirement: dict[str, Any]) -> Any:
    tier = requirement.get("tier")
    if tier == "reference":
        return memory.get_reference(requirement.get("key"))
    if tier == "warm":
        return memory.get_entity(requirement.get("kind", "character"), requirement.get("name"))
    return None


def handle_access_request(memory: BrandMemory, event: dict[str, Any]) -> None:
    """Accept or reject a newly-created scoped ACP access request (FR-24).

    event is one drained job.created event (see acp_cli.drain_events),
    expected to carry {"job_id": ..., "requirement": {"tier":
    "reference"|"warm", "key": ...}} (reference) or {"tier": "warm",
    "kind": ..., "name": ...} (an entity). Any other tier is rejected
    outright — FR-24 explicitly scopes grants to REFERENCE/WARM only,
    never HOT/COLD/ARCHIVE.

    Only proposes a budget here (the accept-equivalent) — actually
    delivering the data happens in deliver_access_grant, once the buyer
    has funded the job. Confirmed live against a real job that the
    protocol itself rejects a deliverable submitted before funding, so
    accept and deliver must be two separate steps, not one.
    """
    job_id = event["job_id"]
    requirement = event.get("requirement") or {}
    tier = requirement.get("tier")

    if tier not in ELIGIBLE_GRANT_TIERS:
        reject_job(job_id, f"tier {tier!r} is not eligible for an ACP access grant")
        return

    if _fetch_grant_data(memory, requirement) is None:
        reject_job(job_id, f"no {tier} data found for the requested key")
        return

    accept_job(job_id, DEFAULT_GRANT_PRICE_USDC)


def deliver_access_grant(memory: BrandMemory, event: dict[str, Any]) -> None:
    """Deliver a previously-accepted access grant once the job is funded (FR-24).

    event carries the same {"job_id": ..., "requirement": {...}} shape as
    handle_access_request — called from a job.funded-type event, after
    the buyer has funded the budget handle_access_request proposed.
    Journals the fulfilled grant (brand_id, requester, tier, key) per the
    PRD's own risk mitigation for cross-agent memory access.
    """
    job_id = event["job_id"]
    requirement = event.get("requirement") or {}
    tier = requirement.get("tier")
    data = _fetch_grant_data(memory, requirement)

    if data is None:
        reject_job(job_id, f"no {tier} data found for the requested key")
        return

    submit_deliverable(job_id, str({"data": data}))

    memory.write_event(
        acted=[f"delivered ACP access grant for {tier} data, job {job_id}"],
        extra={
            "brand_id": memory.brand_id,
            "requesting_agent": event.get("client_address"),
            "tier": tier,
            "requirement": requirement,
        },
    )


def evaluate_brand_consistency(memory: BrandMemory, event: dict[str, Any]) -> None:
    """Gate ACP payment release on real brand-consistency verification (FR-25).

    event's deliverable is expected to carry {"entity_name": ...,
    "output_asset": ...}. Reuses the same real CLIP-based check already
    proven for QA rather than a separate heuristic.
    """
    job_id = event["job_id"]
    deliverable = event.get("deliverable") or {}
    entity_name = deliverable.get("entity_name")
    output_asset = deliverable.get("output_asset")

    entity = memory.get_entity("character", entity_name) or {}
    reference_asset = entity.get("canonical_reference_asset")
    if not reference_asset:
        reject_job(job_id, f"no canonical_reference_asset on file for {entity_name!r}")
        return

    try:
        passed, _score, reasoning = check_visual_consistency(reference_asset, output_asset)
    except VisualSimilarityError as exc:
        reject_job(job_id, f"brand-consistency check failed to run: {exc}")
        return

    if passed:
        complete_job(job_id, reasoning)
    else:
        reject_job(job_id, reasoning)
