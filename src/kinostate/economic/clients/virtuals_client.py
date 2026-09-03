"""Thin wrapper for connecting to Virtuals Protocol's ACP as a registered provider (FR-23).

Registration itself (job schema, pricing, service offering) happens on
Virtuals' own dashboard (app.virtuals.io/acp/join) — there's no SDK method
that creates it from code. What this module does is perform the real
`virtuals-acp` SDK connection/auth handshake for an already-registered
agent, using the free Base Sepolia sandbox. Both ACPContractClientV2's
constructor and VirtualsACP's constructor make real network calls (reading
sub-contract addresses on-chain, validating the session key on-chain), so
this genuinely proves the connection rather than mocking it.
"""

from __future__ import annotations

import os

from virtuals_acp.client import VirtualsACP
from virtuals_acp.configs.configs import BASE_SEPOLIA_CONFIG_V2
from virtuals_acp.contract_clients.contract_client_v2 import ACPContractClientV2


class VirtualsAcpError(RuntimeError):
    """Raised on a missing wallet/entity config or any SDK connection/auth failure."""


def build_client() -> VirtualsACP:
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
        contract_client = ACPContractClientV2(
            agent_wallet_address,
            private_key,
            int(entity_id),
            config=BASE_SEPOLIA_CONFIG_V2,
        )
        return VirtualsACP(acp_contract_clients=contract_client, skip_socket_connection=True)
    except Exception as exc:  # SDK raises its own ACPError/ACPApiError plus web3/network errors
        raise VirtualsAcpError(f"could not connect to Virtuals ACP: {exc}") from exc
