"""Base / x402 metering + provenance (FR-19..22).

`anchor_provenance` (FR-21) is real: it sends an actual Base Sepolia
testnet transaction via `economic.clients.base_client`. `meter_call`
(FR-19, FR-20, FR-22 — x402 payment metering) is still an intentional
stub, not yet wired to a real x402 facilitator or wallet balance check;
it keeps returning a clearly-marked mock value with the shape a real
integration would return, so callers don't need to change again when
that's made real too.
"""

from __future__ import annotations

import hashlib
from typing import Any

from kinostate.economic.clients.base_client import send_hash_transaction


def meter_call(model_name: str, estimated_cost_usdc: float) -> dict[str, Any]:
    """Stub for x402-metered payment authorization (FR-19, FR-22).

    A real implementation checks the brand's HOT-state budget ceiling before
    authorizing payment, then settles via x402 on Base.
    """
    return {
        "authorized": True,
        "cost_usdc": estimated_cost_usdc,
        "model": model_name,
        "tx_hash": None,  # would be a real Base tx hash once wired up
        "mock": True,
    }


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
