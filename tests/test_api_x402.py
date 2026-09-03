"""Tests for optional x402 payment-gating on /generate (FR-19/20/22).

KINOSTATE_X402_PAY_TO_ADDRESS unset (the default) must leave /generate
behaving exactly as it does in test_api_auth.py — these tests only cover
the additional behavior when it's configured, with meter_call itself
mocked so no live facilitator calls happen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kinostate.api import main as main_module
from kinostate.api.main import app


@pytest.fixture(autouse=True)
def _isolated_memory_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("kinostate.config.DEFAULT_MEMORY_DIR", tmp_path)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _onboard(client, brand_id="acme"):
    return client.post("/brands", json={"brand_id": brand_id, "palette_hex": ["#111111"]})


def test_generate_unmetered_by_default(client, monkeypatch):
    monkeypatch.delenv("KINOSTATE_X402_PAY_TO_ADDRESS", raising=False)
    api_key = _onboard(client).json()["api_key"]

    response = client.post(
        "/generate",
        json={"brand_id": "acme", "entity_names": [], "style_prompt": "a test shot"},
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    assert response.json()["cost_usdc"] is None
    assert response.json()["payment_tx_hash"] is None


def test_generate_requires_payment_when_configured(client, monkeypatch):
    monkeypatch.setenv("KINOSTATE_X402_PAY_TO_ADDRESS", "0xPayTo")
    monkeypatch.setattr(main_module, "meter_call", lambda memory, price, payment_payload=None: {
        "authorized": False,
        "payment_required": [{"scheme": "exact"}],
    })
    api_key = _onboard(client).json()["api_key"]

    response = client.post(
        "/generate",
        json={"brand_id": "acme", "entity_names": [], "style_prompt": "a test shot"},
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 402
    assert response.json()["detail"]["payment_required"] == [{"scheme": "exact"}]


def test_generate_succeeds_with_valid_payment(client, monkeypatch):
    monkeypatch.setenv("KINOSTATE_X402_PAY_TO_ADDRESS", "0xPayTo")
    monkeypatch.setattr(main_module, "meter_call", lambda memory, price, payment_payload=None: {
        "authorized": True,
        "cost_usdc": 0.05,
        "tx_hash": "0xtxhash",
    })
    recorded = {}
    monkeypatch.setattr(
        main_module, "record_cost", lambda memory, generation_id, meter_result: recorded.update(meter_result)
    )
    api_key = _onboard(client).json()["api_key"]

    response = client.post(
        "/generate",
        json={"brand_id": "acme", "entity_names": [], "style_prompt": "a test shot"},
        headers={"X-API-Key": api_key, "PAYMENT-SIGNATURE": "some-real-looking-payload"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cost_usdc"] == 0.05
    assert body["payment_tx_hash"] == "0xtxhash"
    assert recorded["tx_hash"] == "0xtxhash"
