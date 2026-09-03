"""Thin client for anchoring a content hash on Base Sepolia (FR-21).

No contract deployment: anchoring is a zero-value transaction from the
configured wallet to itself, with the content hash placed in the tx's
`data` field (calldata). The resulting tx hash is independently
verifiable by anyone on a Base Sepolia block explorer. Follows the same
"thin hand-rolled client over httpx" pattern as
`router/clients/fal_client.py` rather than pulling in the full web3.py
stack — eth-account is used only for offline transaction signing.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from eth_account import Account

DEFAULT_RPC_URL = "https://sepolia.base.org"
CHAIN_ID = 84532  # Base Sepolia
GAS_LIMIT = 30_000  # comfortably covers 21000 base + a 32-byte-hash calldata cost


class BaseAnchorError(RuntimeError):
    """Raised on a missing wallet key, an RPC error, or a malformed RPC response."""


def send_hash_transaction(content_hash: str, *, rpc_url: str | None = None) -> str:
    """Send content_hash as calldata in a zero-value self-send tx. Returns the tx hash.

    Raises BaseAnchorError rather than silently returning a fake hash —
    same fail-loudly precedent as FalError in router/clients/fal_client.py.
    """
    private_key = os.environ.get("BASE_WALLET_PRIVATE_KEY")
    if not private_key:
        raise BaseAnchorError("BASE_WALLET_PRIVATE_KEY is not set")

    url = rpc_url or os.environ.get("BASE_RPC_URL") or DEFAULT_RPC_URL
    account = Account.from_key(private_key)

    nonce = int(_rpc_call(url, "eth_getTransactionCount", [account.address, "pending"]), 16)
    gas_price = int(_rpc_call(url, "eth_gasPrice", []), 16)

    signed = Account.sign_transaction(
        {
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "to": account.address,
            "value": 0,
            "gas": GAS_LIMIT,
            "gasPrice": gas_price,
            "data": "0x" + content_hash,
        },
        private_key,
    )
    raw_tx = "0x" + signed.raw_transaction.hex().removeprefix("0x")
    return _rpc_call(url, "eth_sendRawTransaction", [raw_tx])


def _rpc_call(url: str, method: str, params: list[Any]) -> str:
    try:
        response = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise BaseAnchorError(f"Base RPC call {method!r} failed: {exc}") from exc

    body = response.json()
    if "error" in body:
        raise BaseAnchorError(f"Base RPC call {method!r} returned an error: {body['error']}")
    return body["result"]
