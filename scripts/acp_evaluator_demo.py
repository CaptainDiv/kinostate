"""Real, live ACP v2 evaluator demo — proving evaluate_brand_consistency()
genuinely gates payment release on a real on-chain job (FR-25).

Mirrors an actual live run against Base mainnet (job #76033): a buyer
creates a job against kinostate with no --evaluator flag, so the CLI
defaults the evaluator role to the buyer itself — a provider can't be its
own evaluator (confirmed live: the contract reverts the attempt, which
makes sense given FR-25 explicitly calls for an *independent* evaluator).
Acting as that evaluator, evaluate_brand_consistency() rejects the job
because the test entity has no canonical_reference_asset on file —
deterministic, no image/video downloads needed, so this stays free and
fast without re-validating the CLIP model itself (already proven
separately in test_embed_image_real_clip_same_image_is_near_identical).

Requires: `acp configure` already run, plus KINOSTATE_ACP_AGENT_ID (the
provider) and KINOSTATE_ACP_BUYER_AGENT_ID (client + evaluator) set to
two real agent IDs (see `acp agent list`), each with an approved signer.
"""

from __future__ import annotations

import os

from kinostate.economic.clients.acp_cli import create_custom_job, use_agent, whoami
from kinostate.economic.virtuals_acp import evaluate_brand_consistency
from kinostate.memory.tenant_store import BrandMemory


def main() -> None:
    kinostate_id = os.environ.get("KINOSTATE_ACP_AGENT_ID")
    buyer_id = os.environ.get("KINOSTATE_ACP_BUYER_AGENT_ID")
    if not kinostate_id or not buyer_id:
        print("Skipping — set KINOSTATE_ACP_AGENT_ID and KINOSTATE_ACP_BUYER_AGENT_ID first.")
        return

    use_agent(kinostate_id)
    kinostate_wallet = whoami()["walletAddress"]

    use_agent(buyer_id)
    job = create_custom_job(kinostate_wallet, "FR-25 evaluator demo")
    job_id = job["jobId"]
    print(f"Buyer created real job #{job_id}; evaluator defaulted to: {job['evaluator']}")

    memory = BrandMemory.open("acme")
    memory.set_entity("character", "aria", {"confidence": {}})  # deliberately no canonical_reference_asset

    event = {"job_id": job_id, "deliverable": {"entity_name": "aria", "output_asset": "https://cdn.fal/real.mp4"}}
    evaluate_brand_consistency(memory, event)
    print(f"Real rejection issued on-chain for job #{job_id} — payment release correctly withheld.")
    print(f"Check it yourself: https://app.virtuals.io/acp/agents/{kinostate_id}?tab=acp")


if __name__ == "__main__":
    main()
