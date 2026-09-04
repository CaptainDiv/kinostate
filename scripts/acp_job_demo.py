"""Real, live ACP v2 job-mechanics demo — kinostate accepting a real
access-grant request without any real money ever moving.

This mirrors an actual live run performed against Base mainnet (job
#76023): a buyer agent creates a real on-chain job requesting scoped
REFERENCE-tier data, kinostate (the seller) sees it and proposes a real
budget via `handle_access_request`, and the demo stops there — it never
calls `client fund`, so no USDC changes hands. Confirmed live that the
protocol itself rejects a deliverable submitted before funding, which is
exactly why `handle_access_request` (accept/propose) and
`deliver_access_grant` (submit) are two separate functions, not one.

Known CLI limitation, discovered live: a job's on-chain description text
isn't echoed back by `acp events drain` or `acp job history` — only
identity/status metadata is. A production listener would need a direct
on-chain read to recover it; this demo already knows what it asked for,
so it passes the requirement through directly rather than round-tripping
it through the CLI.

Requires: `acp configure` already run, plus KINOSTATE_ACP_AGENT_ID and
KINOSTATE_ACP_BUYER_AGENT_ID set to two real agent IDs (see `acp agent
list`), each with an approved signer (`acp agent add-signer`).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from kinostate.economic.clients.acp_cli import (
    create_custom_job,
    drain_events,
    use_agent,
    whoami,
)
from kinostate.economic.virtuals_acp import handle_access_request
from kinostate.memory.tenant_store import BrandMemory

REQUIREMENT = {"tier": "reference", "key": "palette"}


def main() -> None:
    kinostate_id = os.environ.get("KINOSTATE_ACP_AGENT_ID")
    buyer_id = os.environ.get("KINOSTATE_ACP_BUYER_AGENT_ID")
    if not kinostate_id or not buyer_id:
        print("Skipping — set KINOSTATE_ACP_AGENT_ID and KINOSTATE_ACP_BUYER_AGENT_ID first.")
        return

    memory = BrandMemory.open("acme")
    memory.set_reference("palette", {"palette_hex": ["#1DB954", "#191414"], "typography": "Inter"})

    use_agent(kinostate_id)
    kinostate_wallet = whoami()["walletAddress"]

    events_file = Path(tempfile.mkdtemp(prefix="kinostate-acp-demo-")) / "events.jsonl"
    listener = subprocess.Popen(
        ["acp", "events", "listen", "--output", str(events_file)],
        env={**os.environ, "IS_TESTNET": os.environ.get("IS_TESTNET", "false")},
    )
    try:
        time.sleep(3)  # give the listener a moment to connect

        use_agent(buyer_id)
        job = create_custom_job(kinostate_wallet, json.dumps(REQUIREMENT))
        job_id = job["jobId"]
        print(f"Buyer created real job #{job_id} requesting: {REQUIREMENT}")

        use_agent(kinostate_id)
        deadline = time.monotonic() + 30
        events = []
        while time.monotonic() < deadline and not events:
            events = drain_events(str(events_file))
            time.sleep(2)

        if not events:
            print("No event arrived within 30s — job may not have propagated yet.")
            return

        print(f"kinostate drained a real event: {events[0]}")
        handle_access_request(memory, {"job_id": job_id, "requirement": REQUIREMENT})
        print(f"Real budget proposed on-chain for job #{job_id} — stopping here, no funds ever moved.")
        print(f"Check it yourself: https://app.virtuals.io/acp/agents/{kinostate_id}?tab=acp")
    finally:
        listener.terminate()
        listener.wait(timeout=10)


if __name__ == "__main__":
    main()
