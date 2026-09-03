"""Virtuals Protocol / ACP integration (FR-23..25).

`register_provider` (FR-23) is real: it connects to Virtuals' ACP via
`economic.clients.virtuals_client` as an already-dashboard-registered
agent (registration itself, including the job schema/service offering,
happens on Virtuals' own dashboard — no SDK call creates it). `grant_access`
(FR-24, scoped paid access grants via ACP escrow) and the Evaluator role
(FR-25) remain intentional stubs — they need a funded buyer agent and a
second counterparty to transact with, out of scope for this pass.
"""

from __future__ import annotations

from typing import Any

from kinostate.economic.clients.virtuals_client import build_client


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
