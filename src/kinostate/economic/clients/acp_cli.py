"""Thin wrapper around Virtuals' official `acp` CLI (ACP v2, FR-23..25).

The `virtuals-acp` Python package (ACPContractClientV2) targets ACP v1 —
a numeric entity_id plus a server-whitelisted EVM wallet, authenticated
via direct on-chain contract calls. The current Virtuals dashboard only
issues **v2** identities (their own on-chain wallet + an EC P-256 signer
approved through the browser), which the v1 SDK cannot authenticate as
at all. Virtuals' own support recommended shelling out to their actively-
maintained `acp-cli` (Node.js, `npm i -g @virtuals-protocol/acp-cli`)
rather than reimplementing the P-256/account-abstraction signing that
job creation, funding, and completion require on-chain — this module
does exactly that, parsing the CLI's own `--json` output.

Testnet: `IS_TESTNET=true` switches the CLI to Base Sepolia (confirmed
via `acp chain list --json`) — the same free testnet used throughout
this project — rather than real mainnet USDC. Defaulted on here unless
the caller's own environment already sets it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

DEFAULT_TESTNET_CHAIN_ID = 84532  # Base Sepolia
DEFAULT_MAINNET_CHAIN_ID = 8453  # Base


class AcpCliError(RuntimeError):
    """Raised when the acp CLI exits non-zero or returns unparseable output."""


def _default_chain_id() -> int:
    """Derive the default chain from the same IS_TESTNET flag _run_acp uses for auth.

    A hardcoded chain_id default independent of IS_TESTNET is a real bug,
    not just an inconvenience: authenticating on one network (mainnet or
    testnet) and then defaulting a job action to the *other* network's
    chain ID fails outright — confirmed live when a real mainnet job's
    accept_job() call defaulted to Base Sepolia's chain ID instead of
    Base mainnet's.
    """
    is_testnet = os.environ.get("IS_TESTNET", "true") == "true"
    return DEFAULT_TESTNET_CHAIN_ID if is_testnet else DEFAULT_MAINNET_CHAIN_ID


def _run_acp(*args: str) -> Any:
    # subprocess.run(["acp", ...]) fails to resolve npm's acp.cmd shim on
    # Windows without shell=True (CreateProcess doesn't do PATHEXT
    # resolution for a bare name) — resolving via shutil.which first works
    # correctly on both Windows and POSIX without needing shell=True.
    executable = shutil.which("acp")
    if executable is None:
        raise AcpCliError("the 'acp' CLI is not installed or not on PATH")

    env = dict(os.environ)
    env.setdefault("IS_TESTNET", "true")

    result = subprocess.run(
        [executable, *args, "--json"],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        raise AcpCliError(f"acp {' '.join(args)!r} failed (exit {result.returncode}): {result.stderr.strip()}")

    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise AcpCliError(f"acp {' '.join(args)!r} returned unparseable output: {result.stdout!r}") from exc


def whoami() -> dict:
    """FR-23: prove the connection by asking the CLI who the active agent is."""
    return _run_acp("agent", "whoami")


def use_agent(agent_id: str) -> dict:
    """Set the CLI's active agent context for all subsequent commands."""
    return _run_acp("agent", "use", "--agent-id", agent_id)


def create_custom_job(provider_address: str, description: str, chain_id: int | None = None) -> dict:
    """Create a freeform on-chain job as the currently active (buyer) agent."""
    chain_id = chain_id if chain_id is not None else _default_chain_id()
    return _run_acp(
        "client", "create-custom-job", "--provider", provider_address, "--description", description, "--chain-id", str(chain_id)
    )


def drain_events(events_file: str, limit: int = 10) -> list[dict]:
    """FR-24 trigger point: read and remove pending events from a listen output file.

    Assumes `acp events listen --output <events_file>` is already running
    as a separate long-running process — this module doesn't manage that
    listener itself, only drains what it's already written.
    """
    result = _run_acp("events", "drain", "--file", events_file, "--limit", str(limit))
    return result if isinstance(result, list) else result.get("events", [])


def accept_job(job_id: str, amount_usdc: float, chain_id: int | None = None) -> dict:
    """FR-24: propose a budget for a job (the accept-equivalent on the provider side)."""
    chain_id = chain_id if chain_id is not None else _default_chain_id()
    return _run_acp("provider", "set-budget", "--job-id", job_id, "--amount", str(amount_usdc), "--chain-id", str(chain_id))


def submit_deliverable(job_id: str, deliverable: str, chain_id: int | None = None) -> dict:
    """FR-24: deliver the fulfilled job content."""
    chain_id = chain_id if chain_id is not None else _default_chain_id()
    return _run_acp("provider", "submit", "--job-id", job_id, "--deliverable", deliverable, "--chain-id", str(chain_id))


def complete_job(job_id: str, reason: str, chain_id: int | None = None) -> dict:
    """FR-25: approve and complete a job as evaluator, releasing escrow."""
    chain_id = chain_id if chain_id is not None else _default_chain_id()
    return _run_acp("client", "complete", "--job-id", job_id, "--reason", reason, "--chain-id", str(chain_id))


def reject_job(job_id: str, reason: str, chain_id: int | None = None) -> dict:
    """FR-25: reject a job/deliverable as evaluator, withholding escrow."""
    chain_id = chain_id if chain_id is not None else _default_chain_id()
    return _run_acp("client", "reject", "--job-id", job_id, "--reason", reason, "--chain-id", str(chain_id))
