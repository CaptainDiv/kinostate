"""Tests for the per-brand API key auth added to api/main.py (FR-1/FR-2 scoped)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kinostate.api.main import app


@pytest.fixture(autouse=True)
def _isolated_memory_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("kinostate.config.DEFAULT_MEMORY_DIR", tmp_path)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _onboard(client, brand_id="acme"):
    return client.post(
        "/brands",
        json={"brand_id": brand_id, "palette_hex": ["#111111"]},
    )


def test_onboard_returns_api_key(client):
    response = _onboard(client)
    assert response.status_code == 200
    assert response.json()["api_key"]


def test_onboard_twice_does_not_rotate_key(client):
    _onboard(client)
    second = _onboard(client)
    assert second.json()["api_key"] is None


def test_add_entity_without_key_is_rejected(client):
    _onboard(client)
    response = client.post(
        "/brands/acme/entities",
        json={"kind": "character", "name": "aria", "description": "test"},
    )
    assert response.status_code == 401


def test_add_entity_with_wrong_key_is_rejected(client):
    _onboard(client)
    response = client.post(
        "/brands/acme/entities",
        json={"kind": "character", "name": "aria", "description": "test"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_add_entity_with_correct_key_succeeds(client):
    api_key = _onboard(client).json()["api_key"]
    response = client.post(
        "/brands/acme/entities",
        json={"kind": "character", "name": "aria", "description": "test"},
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200


def test_brand_a_key_does_not_work_for_brand_b(client):
    key_a = _onboard(client, "acme").json()["api_key"]
    _onboard(client, "globex")

    response = client.post(
        "/brands/globex/entities",
        json={"kind": "character", "name": "aria", "description": "test"},
        headers={"X-API-Key": key_a},
    )
    assert response.status_code == 401


def test_generate_requires_key(client):
    _onboard(client)
    response = client.post(
        "/generate",
        json={"brand_id": "acme", "entity_names": [], "style_prompt": "a test shot"},
    )
    assert response.status_code == 401


def test_review_requires_key(client):
    _onboard(client)
    response = client.post(
        "/brands/acme/generate/gen-1/review",
        json={"entity_name": "aria", "approved": True},
    )
    assert response.status_code == 401
