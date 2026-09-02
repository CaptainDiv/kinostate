"""End-to-end CLI demo of the Continuity pipeline.

Onboards a brand, defines a character, requests a shot on one model, then
requests another shot of the *same* character on a *different* model from a
brand-new BrandMemory instance — demonstrating PRD Key User Flow #3
(fresh-session recall across a model switch) — and prints the resulting
COLD journal.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from kinostate.compiler.canonical import Entity, GenerationRequest
from kinostate.memory.tenant_store import BrandMemory
from kinostate.router.router import RoutingPolicy, route_and_generate
from kinostate.verification.qa import run_qa


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
            "canonical_reference_asset": "sha256:deadbeef",
            "approval_status": "approved",
            "confidence": {},
        },
    )
    print("Onboarded brand 'acme' with entity 'aria'.\n")

    aria = Entity(
        kind="character",
        name="aria",
        description="Auburn hair, green jacket, brand mascot",
        canonical_reference_asset="sha256:deadbeef",
        approval_status="approved",
    )

    # 2. First generation, forced onto Runway.
    request_one = GenerationRequest(
        brand_id="acme",
        entities=[aria],
        style_prompt="Aria waving at the camera in a sunlit park",
        model_override="runway",
    )
    result_one = route_and_generate(memory, request_one, RoutingPolicy())
    qa_one = run_qa(memory, "aria", result_one["model"], result_one["generation_id"])
    print(f"Generation 1: model={result_one['model']} qa_passed={qa_one.passed}")
    print(f"  output_asset={result_one['output_asset']}\n")

    # 3. "Fresh session": open a brand-new BrandMemory instance (simulating a
    #    new process) and request another shot of the same entity, routed to
    #    a different model, with no re-entry of brand facts.
    fresh_session_memory = BrandMemory.open("acme", memory_dir=memory_dir)
    request_two = GenerationRequest(
        brand_id="acme",
        entities=[aria],
        style_prompt="Aria running along the same park path at dusk",
        model_override="luma",
    )
    result_two = route_and_generate(fresh_session_memory, request_two, RoutingPolicy())
    qa_two = run_qa(fresh_session_memory, "aria", result_two["model"], result_two["generation_id"])
    print(f"Generation 2 (fresh session, different model): model={result_two['model']} qa_passed={qa_two.passed}")
    print(f"  output_asset={result_two['output_asset']}\n")

    # 4. Print the COLD journal to show both generations + both QA events.
    print("COLD journal:")
    for event in fresh_session_memory.read_events(limit=10):
        print(json.dumps(event, indent=2, default=str))


if __name__ == "__main__":
    main()
