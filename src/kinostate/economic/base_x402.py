"""Base / x402 metering + provenance stubs (FR-19..22).

Not wired to a real Base RPC, x402 facilitator, or wallet — no live keys are
configured for this scaffold. Every function here returns a clearly-marked
mock value with the same shape a real integration would return, so callers
(router, API layer) don't need to change when this is made real.
"""

from __future__ import annotations

import hashlib
from typing import Any


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
    """Stub for on-chain provenance anchoring (FR-21).

    Real implementation hashes (output asset + compiled payload + memory
    state) and anchors it on Base. Here we compute the hash locally and
    return a fake tx reference so downstream code (journal, provenance
    viewer) has something consistent to display.
    """
    digest_input = f"{output_asset}:{compiled_payload}".encode()
    content_hash = hashlib.sha256(digest_input).hexdigest()
    return {
        "content_hash": content_hash,
        "tx_hash": f"0xstub{content_hash[:16]}",
        "anchored": False,  # flips to True once real Base integration lands
        "mock": True,
    }
