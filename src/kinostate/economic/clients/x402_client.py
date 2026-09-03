"""Thin wrapper for x402 payment verification/settlement (FR-19).

Uses the synchronous `x402` SDK API (this codebase's FastAPI routes are
plain `def`, never `async def`) against the free, public Base Sepolia
testnet facilitator at x402.org/facilitator. Kinostate is the seller here:
a caller must present a valid payment before a generation proceeds.
Verified against the actually-installed `x402` package (2.21.0) rather
than assumed from docs — notably its real payment header is
`PAYMENT-SIGNATURE` (V2); the `X-PAYMENT` header some older writeups
mention is V1/legacy and this SDK's own server no longer extracts it.
"""

from __future__ import annotations

import os

from x402.http import FacilitatorConfig, HTTPFacilitatorClientSync, decode_payment_signature_header
from x402.mechanisms.evm.exact.server import ExactEvmScheme
from x402.server import PaymentRequirements, ResourceConfig, x402ResourceServerSync

DEFAULT_FACILITATOR_URL = "https://x402.org/facilitator"
NETWORK = "eip155:84532"  # Base Sepolia
PAYMENT_HEADER_NAME = "PAYMENT-SIGNATURE"


class X402Error(RuntimeError):
    """Raised on missing pay-to config or any facilitator/verification failure."""


def _build_server() -> x402ResourceServerSync:
    facilitator_url = os.environ.get("X402_FACILITATOR_URL") or DEFAULT_FACILITATOR_URL
    facilitator = HTTPFacilitatorClientSync(FacilitatorConfig(url=facilitator_url))
    server = x402ResourceServerSync(facilitator)
    server.register(NETWORK, ExactEvmScheme())
    server.initialize()
    return server


def build_payment_requirements(price_usdc: float) -> list[PaymentRequirements]:
    pay_to = os.environ.get("KINOSTATE_X402_PAY_TO_ADDRESS")
    if not pay_to:
        raise X402Error("KINOSTATE_X402_PAY_TO_ADDRESS is not set")

    server = _build_server()
    config = ResourceConfig(scheme="exact", payTo=pay_to, price=f"${price_usdc}", network=NETWORK)
    return server.build_payment_requirements(config)


def verify_and_settle(payment_header: str, requirements: list[PaymentRequirements]) -> tuple[bool, str | None, str | None]:
    """Decode a presented PAYMENT-SIGNATURE header, verify it, and settle on success.

    Returns (verified, tx_hash, error_reason).
    """
    try:
        payload = decode_payment_signature_header(payment_header)
    except Exception as exc:
        return False, None, f"could not decode payment header: {exc}"

    server = _build_server()
    matching = requirements[0]

    verify_result = server.verify_payment(payload, matching)
    if not verify_result.is_valid:
        return False, None, verify_result.invalid_reason or "payment verification failed"

    settle_result = server.settle_payment(payload, matching)
    if not settle_result.success:
        return False, None, settle_result.error_reason or "payment settlement failed"

    return True, settle_result.transaction, None
