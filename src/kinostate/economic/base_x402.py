"""Base / x402 metering + provenance (FR-19..22).

Both `anchor_provenance` (FR-21) and `meter_call` (FR-19, FR-22) are real.
`meter_call` enforces a brand's HOT-state spending policy, then verifies
and settles a presented x402 payment via `economic.clients.x402_client`
against the free Base Sepolia testnet facilitator — a caller must pay
before a generation proceeds. `record_cost` (FR-20) journals the outcome,
kept separate from `meter_call` since payment happens before a
generation_id exists yet.
"""

from __future__ import annotations

import hashlib
from typing import Any

from kinostate.economic.clients.base_client import send_hash_transaction
from kinostate.economic.clients.x402_client import build_payment_requirements, encode_payment_required, verify_and_settle
from kinostate.memory.tenant_store import BrandMemory


def meter_call(memory: BrandMemory, estimated_cost_usdc: float, payment_payload: str | None = None) -> dict[str, Any]:
    """Enforce the brand's budget ceiling (FR-22), then verify+settle an x402 payment (FR-19).

    Returns {"authorized": False, "reason": ...} if the budget ceiling is
    exceeded or the payment is missing/invalid (with "payment_required"
    set to the real payment requirements when no payment was presented at
    all), or {"authorized": True, "cost_usdc": ..., "tx_hash": ...} on a
    genuinely settled payment.
    """
    policy = memory.get_state("spending_policy") or {}
    ceiling = policy.get("budget_ceiling_usdc")
    if ceiling is not None and estimated_cost_usdc > ceiling:
        return {"authorized": False, "reason": f"cost {estimated_cost_usdc} exceeds budget ceiling {ceiling}"}

    requirements = build_payment_requirements(estimated_cost_usdc)
    if payment_payload is None:
        return {
            "authorized": False,
            "payment_required": [req.model_dump() for req in requirements],
            "payment_required_header": encode_payment_required(requirements),
        }

    verified, tx_hash, error = verify_and_settle(payment_payload, requirements)
    if not verified:
        return {"authorized": False, "reason": error}

    return {"authorized": True, "cost_usdc": estimated_cost_usdc, "tx_hash": tx_hash}


def record_cost(memory: BrandMemory, generation_id: str, meter_result: dict[str, Any]) -> None:
    """Journal a metering outcome linked to a generation (FR-20)."""
    memory.write_event(
        acted=[f"metered generation {generation_id}: authorized={meter_result['authorized']}"],
        extra={"generation_id": generation_id, **meter_result},
    )


def anchor_provenance(output_asset: str, compiled_payload: dict[str, Any]) -> dict[str, Any]:
    """Anchor a hash of (output asset + compiled payload) on Base Sepolia (FR-21).

    Hashes the two inputs locally, then sends that hash as calldata in a
    real testnet transaction (see economic.clients.base_client), so the
    returned tx_hash is independently verifiable on a block explorer.
    """
    digest_input = f"{output_asset}:{compiled_payload}".encode()
    content_hash = hashlib.sha256(digest_input).hexdigest()
    tx_hash = send_hash_transaction(content_hash)
    return {
        "content_hash": content_hash,
        "tx_hash": tx_hash,
        "anchored": True,
    }
