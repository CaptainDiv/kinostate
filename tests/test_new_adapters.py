"""Shape/limit tests for the two live fal.ai adapters, and dispatch tests
for router._call_model's real-vs-mock branching (FR-9, FR-10, FR-11).

No network calls: router-level tests monkeypatch `run_model` itself rather
than going through fal_client's HTTP layer (that's covered in
test_fal_client.py).
"""

from __future__ import annotations

import pytest

from kinostate.compiler.adapters.kling_o1_reference import FAL_MODEL_PATH as KLING_O1_MODEL_PATH
from kinostate.compiler.adapters.kling_o1_reference import KlingO1ReferenceAdapter
from kinostate.compiler.adapters.runway import RunwayAdapter
from kinostate.compiler.adapters.seedance import SeedanceAdapter
from kinostate.compiler.base_adapter import PayloadValidationError
from kinostate.compiler.canonical import Entity, GenerationRequest
from kinostate.router import router as router_module
from kinostate.router.clients.fal_client import FalError


def _entity(name: str = "aria", reference: str | None = "https://img.example/aria.png") -> Entity:
    return Entity(kind="character", name=name, description="test entity", canonical_reference_asset=reference)


def _request(entities: list[Entity], model_override: str | None = None) -> GenerationRequest:
    return GenerationRequest(brand_id="acme", entities=entities, style_prompt="a test shot", model_override=model_override)


def test_kling_o1_reference_compile_shape():
    adapter = KlingO1ReferenceAdapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot @Element1"
    assert payload.body["elements"] == [{"frontal_image_url": "https://img.example/aria.png"}]
    assert payload.entity_count == 1
    adapter.validate(payload)  # should not raise


def test_kling_o1_reference_missing_reference_asset_raises():
    adapter = KlingO1ReferenceAdapter()
    with pytest.raises(PayloadValidationError, match="canonical_reference_asset"):
        adapter.compile(_request([_entity(reference=None)]))


def test_kling_o1_reference_entity_count_over_limit_raises():
    adapter = KlingO1ReferenceAdapter()
    entities = [_entity(name=f"e{i}") for i in range(adapter.max_reference_entities + 1)]
    payload = adapter.compile(_request(entities))

    with pytest.raises(PayloadValidationError, match="at most"):
        adapter.validate(payload)


def test_seedance_compile_shape():
    adapter = SeedanceAdapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot"
    assert payload.body["image_urls"] == ["https://img.example/aria.png"]
    adapter.validate(payload)  # should not raise


def test_seedance_missing_reference_asset_raises():
    adapter = SeedanceAdapter()
    with pytest.raises(PayloadValidationError, match="canonical_reference_asset"):
        adapter.compile(_request([_entity(reference=None)]))


def test_call_model_dispatches_real_model_to_fal(monkeypatch):
    captured = {}

    def fake_run_model(model_path, inputs, **kwargs):
        captured["model_path"] = model_path
        captured["inputs"] = inputs
        return {"video": {"url": "https://cdn.fal/real.mp4"}}

    monkeypatch.setattr(router_module, "run_model", fake_run_model)

    adapter = KlingO1ReferenceAdapter()
    output_asset = router_module._call_model(adapter, {"prompt": "hi @Element1", "elements": [{"frontal_image_url": "u"}]})

    assert output_asset == "https://cdn.fal/real.mp4"
    assert captured["model_path"] == KLING_O1_MODEL_PATH
    assert captured["inputs"] == {"prompt": "hi @Element1", "elements": [{"frontal_image_url": "u"}]}


def test_call_model_missing_fal_key_raises(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    adapter = KlingO1ReferenceAdapter()

    with pytest.raises(FalError, match="FAL_KEY is not set"):
        router_module._call_model(adapter, {"prompt": "hi"})


def test_call_model_still_mocks_legacy_adapters():
    adapter = RunwayAdapter()
    output_asset = router_module._call_model(adapter, {})

    assert output_asset.startswith("mock://runway/")
