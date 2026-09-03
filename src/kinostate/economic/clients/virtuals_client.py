"""Thin wrapper for connecting to Virtuals Protocol's ACP as a registered provider (FR-23..25).

Registration itself (job schema, pricing, service offering) happens on
Virtuals' own dashboard (app.virtuals.io/acp/join) — there's no SDK method
that creates it from code. What this module does is perform the real
`virtuals-acp` SDK connection/auth handshake for an already-registered
agent, using the free Base Sepolia sandbox. Both ACPContractClientV2's
constructor and VirtualsACP's constructor make real network calls (reading
sub-contract addresses on-chain, validating the session key on-chain), so
this genuinely proves the connection rather than mocking it.

Two client modes: `build_client()` (FR-23) just proves the connection —
no socket, no callbacks. `build_listening_client()` (FR-24/25) is the real
job-handling mode: it keeps a live socket connection open and dispatches
incoming jobs/evaluation requests to the given callbacks, per the SDK's
own event model (there's no polling-based alternative for these events).
"""

from __future__ import annotations

import os
from typing import Callable

from virtuals_acp.client import VirtualsACP
from virtuals_acp.configs.configs import BASE_SEPOLIA_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2


class VirtualsAcpError(RuntimeError):
    """Raised on a missing wallet/entity config or any SDK connection/auth failure."""


def _build_contract_client() -> ACPContractClientV2:
    private_key = os.environ.get("VIRTUALS_WALLET_PRIVATE_KEY")
    agent_wallet_address = os.environ.get("VIRTUALS_AGENT_WALLET_ADDRESS")
    entity_id = os.environ.get("VIRTUALS_ENTITY_ID")
    missing = [
        name
        for name, value in (
            ("VIRTUALS_WALLET_PRIVATE_KEY", private_key),
            ("VIRTUALS_AGENT_WALLET_ADDRESS", agent_wallet_address),
            ("VIRTUALS_ENTITY_ID", entity_id),
        )
        if not value
    ]
    if missing:
        raise VirtualsAcpError(f"missing required env var(s): {', '.join(missing)}")

    try:
        return ACPContractClientV2(
            agent_wallet_address,
            private_key,
            int(entity_id),
            config=BASE_SEPOLIA_CONFIG_V2,
        )
    except Exception as exc:  # SDK raises its own ACPError/ACPApiError plus web3/network errors
        raise VirtualsAcpError(f"could not connect to Virtuals ACP: {exc}") from exc


def build_client() -> VirtualsACP:
    """Prove the connection only (FR-23) — no socket, no job handling."""
    contract_client = _build_contract_client()
    try:
        return VirtualsACP(acp_contract_clients=contract_client, skip_socket_connection=True)
    except Exception as exc:
        raise VirtualsAcpError(f"could not connect to Virtuals ACP: {exc}") from exc


def build_listening_client(
    on_new_task: Callable | None = None,
    on_evaluate: Callable | None = None,
) -> VirtualsACP:
    """Keep a live socket open and dispatch jobs/evaluations (FR-24, FR-25).

    on_new_task(job, memo_to_sign) fires for an incoming job request;
    on_evaluate(job) fires when this agent is acting as the job's
    Evaluator. Both are the SDK's only dispatch path for these events —
    there's no polling-based alternative.
    """
    contract_client = _build_contract_client()
    try:
        return VirtualsACP(
            acp_contract_clients=contract_client,
            on_new_task=on_new_task,
            on_evaluate=on_evaluate,
            skip_socket_connection=False,
        )
    except Exception as exc:
        raise VirtualsAcpError(f"could not connect to Virtuals ACP: {exc}") from exc
