"""Real, end-to-end x402 payment demo: a throwaway buyer wallet actually
pays Kinostate's /generate endpoint in Base Sepolia testnet USDC.

This is the payer-side counterpart to the seller-side x402 metering built
into api/main.py's /generate (see economic/base_x402.py). It proves the
whole loop — 402 -> sign payment -> retry -> 200 -> settled tx hash — not
just the seller half, which was already dry-run-verified separately.

Requires (see .env.example): KINOSTATE_X402_PAY_TO_ADDRESS (the seller's
receiving address — no private key needed for that side) and
X402_PAYER_PRIVATE_KEY (a disposable Base Sepolia testnet wallet funded
with a little USDC from faucet.circle.com). Spins up a real local server
(a requests.Session can't be pointed at FastAPI's in-process TestClient)
against an isolated, temporary memory directory.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from eth_account import Account

from x402.client import x402ClientSync
from x402.http.clients.requests import x402_requests
from x402.mechanisms.evm.exact import register_exact_evm_client

HOST = "127.0.0.1"
PORT = 8811
BASE_URL = f"http://{HOST}:{PORT}"


def _wait_for_server(timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            requests.get(f"{BASE_URL}/openapi.json", timeout=3.0)
            return
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.5)
    raise RuntimeError(f"server did not come up on {BASE_URL} within {timeout_seconds}s")


def main() -> None:
    load_dotenv()

    pay_to = os.environ.get("KINOSTATE_X402_PAY_TO_ADDRESS")
    payer_key = os.environ.get("X402_PAYER_PRIVATE_KEY")
    if not pay_to or not payer_key:
        print("Skipping — set KINOSTATE_X402_PAY_TO_ADDRESS and X402_PAYER_PRIVATE_KEY in .env first.")
        return

    memory_dir = Path(tempfile.mkdtemp(prefix="kinostate-x402-demo-"))
    server_env = {**os.environ, "KINOSTATE_MEMORY_DIR": str(memory_dir)}

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "kinostate.api.main:app", "--host", HOST, "--port", str(PORT)],
        env=server_env,
    )
    try:
        _wait_for_server()

        onboard = requests.post(f"{BASE_URL}/brands", json={"brand_id": "x402demo", "palette_hex": ["#111111"]})
        onboard.raise_for_status()
        api_key = onboard.json()["api_key"]
        print(f"Onboarded demo brand, api_key issued: {bool(api_key)}")

        account = Account.from_key(payer_key)
        client = x402ClientSync()
        register_exact_evm_client(client, account)
        payer_session = x402_requests(client)

        response = payer_session.post(
            f"{BASE_URL}/generate",
            json={"brand_id": "x402demo", "entity_names": [], "style_prompt": "a real paid test shot"},
            headers={"X-API-Key": api_key},
        )
        print(f"/generate status: {response.status_code}")
        response.raise_for_status()
        body = response.json()
        print(f"cost_usdc={body['cost_usdc']}  payment_tx_hash={body['payment_tx_hash']}")
        if body.get("payment_tx_hash"):
            print(f"  https://sepolia.basescan.org/tx/{body['payment_tx_hash']}")
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
