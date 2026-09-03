"""End-to-end CLI demo of the Kinostate pipeline.

Onboards a brand, defines a character, requests a shot on one *real* model
(via fal.ai), then requests another shot of the *same* character on a
different real model from a brand-new BrandMemory instance — demonstrating
PRD Key User Flow #3 (fresh-session recall across a model switch) against
actual generated video, not a mock:// stub — and prints the resulting COLD
journal.

Requires FAL_KEY to be set (see .env.example) and spends real fal.ai
balance on each run — this is the one deliberately minimal live smoke test
called for in the Milestone 1 plan, not something to run on a loop.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from kinostate.compiler.canonical import Entity, GenerationRequest
from kinostate.economic.base_x402 import anchor_provenance
from kinostate.economic.clients.acp_cli import AcpCliError
from kinostate.economic.virtuals_acp import register_provider
from kinostate.memory.tenant_store import BrandMemory
from kinostate.router.router import RoutingPolicy, route_and_generate
from kinostate.verification.qa import run_qa

# Placeholder character photo, publicly reachable so fal.ai can fetch it.
# Swap this for a real branded reference asset before recording an actual
# demo — this default only exists so the pipeline is runnable out of the box.
DEMO_REFERENCE_IMAGE_URL = os.environ.get(
    "KINOSTATE_DEMO_REFERENCE_IMAGE_URL", "https://picsum.photos/seed/aria/512/512"
)


def main() -> None:
    memory_dir = Path(tempfile.mkdtemp(prefix="kinostate-demo-"))
    print(f"Using demo memory dir: {memory_dir}\n")

    # 1. Brand onboarding (REFERENCE + first WARM entity).
    memory = BrandMemory.open("acme", memory_dir=memory_dir)
    memory.set_reference(
        "palette",
        {"palette_hex": ["#1DB954", "#191414"], "typography": "Inter", "tone_rules": ["confident", "warm"]},
    )
    memory.set_entity(
        "character",
        "aria",
        {
            "kind": "character",
            "description": "Auburn hair, green jacket, brand mascot",
            "canonical_reference_asset": DEMO_REFERENCE_IMAGE_URL,
            "approval_status": "approved",
            "confidence": {},
        },
    )
    print("Onboarded brand 'acme' with entity 'aria'.\n")

    aria = Entity(
        kind="character",
        name="aria",
        description="Auburn hair, green jacket, brand mascot",
        canonical_reference_asset=DEMO_REFERENCE_IMAGE_URL,
        approval_status="approved",
    )

    # 2. First generation, forced onto Kling O1 Reference (real, via fal.ai).
    request_one = GenerationRequest(
        brand_id="acme",
        entities=[aria],
        style_prompt="Aria waving at the camera in a sunlit park",
        model_override="kling_o1_reference",
    )
    result_one = route_and_generate(memory, request_one, RoutingPolicy())
    qa_one = run_qa(memory, "aria", result_one["model"], result_one["generation_id"], result_one["output_asset"])
    print(f"Generation 1: model={result_one['model']} qa_passed={qa_one.passed}")
    print(f"  output_asset={result_one['output_asset']}\n")

    # 2b. Anchor this generation's provenance on Base Sepolia (FR-21) —
    #     requires BASE_WALLET_PRIVATE_KEY to be set and funded with
    #     testnet ETH; skipped with a note if it isn't configured.
    if os.environ.get("BASE_WALLET_PRIVATE_KEY"):
        provenance = anchor_provenance(result_one["output_asset"], result_one["payload"].body)
        print(f"Provenance anchored: tx_hash={provenance['tx_hash']}")
        print(f"  https://sepolia.basescan.org/tx/{provenance['tx_hash']}\n")
    else:
        print("Skipping provenance anchoring — BASE_WALLET_PRIVATE_KEY not set.\n")

    # 2c. Connect to Virtuals ACP as a registered provider (FR-23) — auth
    #     lives in the `acp` CLI's own local login state (`acp configure`),
    #     not env vars, so this is a try/skip rather than an env check.
    try:
        provider = register_provider("acme")
        print(f"Connected to Virtuals ACP: {provider['agent']}\n")
    except AcpCliError as exc:
        print(f"Skipping Virtuals ACP connection — {exc}\n")

    # 3. "Fresh session": open a brand-new BrandMemory instance (simulating a
    #    new process) and request another shot of the same entity, routed to
    #    a different real model, with no re-entry of brand facts.
    fresh_session_memory = BrandMemory.open("acme", memory_dir=memory_dir)
    request_two = GenerationRequest(
        brand_id="acme",
        entities=[aria],
        style_prompt="Aria running along the same park path at dusk",
        model_override="seedance",
    )
    result_two = route_and_generate(fresh_session_memory, request_two, RoutingPolicy())
    qa_two = run_qa(
        fresh_session_memory, "aria", result_two["model"], result_two["generation_id"], result_two["output_asset"]
    )
    print(f"Generation 2 (fresh session, different model): model={result_two['model']} qa_passed={qa_two.passed}")
    print(f"  output_asset={result_two['output_asset']}\n")

    # 4. Print the COLD journal to show both generations + both QA events.
    print("COLD journal:")
    for event in fresh_session_memory.read_events(limit=10):
        print(json.dumps(event, indent=2, default=str))


if __name__ == "__main__":
    main()
