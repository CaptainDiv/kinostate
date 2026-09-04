"""Shape/limit tests for the live fal.ai adapters, and dispatch tests
for router._call_model's real-vs-mock branching (FR-9, FR-10, FR-11).

kling_o1_reference/seedance were real in an earlier pass but are dormant
now (minimax_h3/xai_grok_imagine_video/gemini_omni_flash replaced them as
cheaper alternatives) -- their own compile-shape tests stay since that
code is unchanged, plus a regression-lock test confirming they correctly
mock now rather than silently dispatching to fal.ai.

No network calls: router-level tests monkeypatch `run_model` itself rather
than going through fal_client's HTTP layer (that's covered in
test_fal_client.py).
"""

from __future__ import annotations

import pytest

from kinostate.compiler.adapters.gemini_omni_flash import FAL_MODEL_PATH as GEMINI_OMNI_FLASH_MODEL_PATH
from kinostate.compiler.adapters.gemini_omni_flash import GeminiOmniFlashAdapter
from kinostate.compiler.adapters.kling_o1_reference import KlingO1ReferenceAdapter
from kinostate.compiler.adapters.minimax_h3 import FAL_MODEL_PATH as MINIMAX_H3_MODEL_PATH
from kinostate.compiler.adapters.minimax_h3 import MinimaxH3Adapter
from kinostate.compiler.adapters.runway import RunwayAdapter
from kinostate.compiler.adapters.seedance import SeedanceAdapter
from kinostate.compiler.adapters.xai_grok_imagine_video import XaiGrokImagineVideoAdapter
from kinostate.compiler.base_adapter import PayloadValidationError
from kinostate.compiler.canonical import Entity, GenerationRequest
from kinostate.router import router as router_module
from kinostate.router.clients.fal_client import FalError


def _entity(
    name: str = "aria",
    reference: str | None = "https://img.example/aria.png",
    additional_reference_images: list[str] | None = None,
    forbidden_traits: list[str] | None = None,
) -> Entity:
    return Entity(
        kind="character",
        name=name,
        description="test entity",
        canonical_reference_asset=reference,
        additional_reference_images=additional_reference_images or [],
        forbidden_traits=forbidden_traits or [],
    )


def _request(
    entities: list[Entity], model_override: str | None = None, duration_seconds: float = 5.0, resolution: str = "480p"
) -> GenerationRequest:
    return GenerationRequest(
        brand_id="acme",
        entities=entities,
        style_prompt="a test shot",
        model_override=model_override,
        duration_seconds=duration_seconds,
        resolution=resolution,
    )


def test_kling_o1_reference_compile_shape():
    adapter = KlingO1ReferenceAdapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot @Element1 test entity"
    assert payload.body["elements"] == [{"frontal_image_url": "https://img.example/aria.png"}]
    assert payload.entity_count == 1
    adapter.validate(payload)  # should not raise


def test_kling_o1_reference_includes_additional_angle_images():
    adapter = KlingO1ReferenceAdapter()
    entity = _entity(additional_reference_images=["https://img.example/aria-side.png"])
    payload = adapter.compile(_request([entity]))

    assert payload.body["elements"] == [
        {"frontal_image_url": "https://img.example/aria.png", "reference_image_urls": ["https://img.example/aria-side.png"]}
    ]


def test_kling_o1_reference_prompt_includes_forbidden_traits():
    adapter = KlingO1ReferenceAdapter()
    entity = _entity(forbidden_traits=["sunglasses", "hat"])
    payload = adapter.compile(_request([entity]))

    assert payload.body["prompt"] == "a test shot @Element1 test entity (avoid: sunglasses, hat)"


def test_kling_o1_reference_accepts_its_real_minimum_duration():
    adapter = KlingO1ReferenceAdapter()
    payload = adapter.compile(_request([_entity()], duration_seconds=3))

    assert payload.body["duration"] == "3"


def test_kling_o1_reference_rejects_duration_outside_real_range():
    adapter = KlingO1ReferenceAdapter()
    with pytest.raises(PayloadValidationError, match="duration_seconds"):
        adapter.compile(_request([_entity()], duration_seconds=11))


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

    assert payload.body["prompt"] == "a test shot test entity"
    assert payload.body["image_urls"] == ["https://img.example/aria.png"]
    adapter.validate(payload)  # should not raise


def test_seedance_missing_reference_asset_raises():
    adapter = SeedanceAdapter()
    with pytest.raises(PayloadValidationError, match="canonical_reference_asset"):
        adapter.compile(_request([_entity(reference=None)]))


def test_seedance_includes_additional_angle_images():
    adapter = SeedanceAdapter()
    entity = _entity(additional_reference_images=["https://img.example/aria-side.png", "https://img.example/aria-back.png"])
    payload = adapter.compile(_request([entity]))

    assert payload.body["image_urls"] == [
        "https://img.example/aria.png",
        "https://img.example/aria-side.png",
        "https://img.example/aria-back.png",
    ]
    adapter.validate(payload)  # should not raise, 3 images is well under the cap


def test_seedance_total_image_count_over_cap_raises():
    adapter = SeedanceAdapter()
    entity = _entity(additional_reference_images=[f"https://img.example/aria-{i}.png" for i in range(9)])
    payload = adapter.compile(_request([entity]))  # 1 primary + 9 additional = 10 total

    with pytest.raises(PayloadValidationError, match="at most 9 total reference images"):
        adapter.validate(payload)


def test_seedance_accepts_its_real_minimum_duration():
    adapter = SeedanceAdapter()
    payload = adapter.compile(_request([_entity()], duration_seconds=4))

    assert payload.body["duration"] == "4"


def test_seedance_rejects_duration_below_its_real_floor():
    # Seedance's real floor is 4s, unlike Kling O1 Reference's 3s -- the
    # two models don't share one valid duration range.
    adapter = SeedanceAdapter()
    with pytest.raises(PayloadValidationError, match="duration_seconds"):
        adapter.compile(_request([_entity()], duration_seconds=3))


def test_call_model_dispatches_real_model_to_fal(monkeypatch):
    captured = {}

    def fake_run_model(model_path, inputs, **kwargs):
        captured["model_path"] = model_path
        captured["inputs"] = inputs
        return {"video": {"url": "https://cdn.fal/real.mp4"}}

    monkeypatch.setattr(router_module, "run_model", fake_run_model)

    adapter = MinimaxH3Adapter()
    output_asset = router_module._call_model(adapter, {"prompt": "hi", "reference_image_urls": ["u"]})

    assert output_asset == "https://cdn.fal/real.mp4"
    assert captured["model_path"] == MINIMAX_H3_MODEL_PATH
    assert captured["inputs"] == {"prompt": "hi", "reference_image_urls": ["u"]}


def test_call_model_missing_fal_key_raises(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    adapter = MinimaxH3Adapter()

    with pytest.raises(FalError, match="FAL_KEY is not set"):
        router_module._call_model(adapter, {"prompt": "hi"})


def test_call_model_still_mocks_legacy_adapters():
    adapter = RunwayAdapter()
    output_asset = router_module._call_model(adapter, {})

    assert output_asset.startswith("mock://runway/")


def test_call_model_now_mocks_dormant_former_real_adapters():
    # Regression lock: kling_o1_reference/seedance were real in an earlier
    # pass; confirm they correctly fall back to mock:// now that cheaper
    # adapters replaced them in REAL_MODELS, rather than silently still
    # dispatching to fal.ai.
    kling_output = router_module._call_model(KlingO1ReferenceAdapter(), {})
    seedance_output = router_module._call_model(SeedanceAdapter(), {})

    assert kling_output.startswith("mock://kling_o1_reference/")
    assert seedance_output.startswith("mock://seedance/")


def test_minimax_h3_compile_shape():
    adapter = MinimaxH3Adapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot test entity"
    assert payload.body["reference_image_urls"] == ["https://img.example/aria.png"]
    assert payload.body["duration"] == 5
    assert payload.body["resolution"] == "480P"
    adapter.validate(payload)  # should not raise


def test_minimax_h3_defaults_to_cheapest_resolution_tier(monkeypatch):
    # The vendor's own default resolution ("2K") costs 2.6x more -- any
    # canonical resolution this adapter doesn't recognize should fall
    # back to the cheap tier, not the vendor default.
    adapter = MinimaxH3Adapter()
    payload = adapter.compile(_request([_entity()], resolution="unrecognized-tier"))

    assert payload.body["resolution"] == "480P"


def test_minimax_h3_maps_higher_resolution_tiers():
    adapter = MinimaxH3Adapter()
    payload = adapter.compile(_request([_entity()], resolution="2k"))

    assert payload.body["resolution"] == "2K"


def test_minimax_h3_rejects_duration_below_its_real_floor():
    # minimax/h3's real floor is 5s -- higher than Kling's 3s or
    # Seedance's 4s.
    adapter = MinimaxH3Adapter()
    with pytest.raises(PayloadValidationError, match="duration_seconds"):
        adapter.compile(_request([_entity()], duration_seconds=4))


def test_minimax_h3_missing_reference_asset_raises():
    adapter = MinimaxH3Adapter()
    with pytest.raises(PayloadValidationError, match="canonical_reference_asset"):
        adapter.compile(_request([_entity(reference=None)]))


def test_minimax_h3_total_image_count_over_cap_raises():
    adapter = MinimaxH3Adapter()
    entity = _entity(additional_reference_images=[f"https://img.example/aria-{i}.png" for i in range(9)])
    payload = adapter.compile(_request([entity]))  # 1 primary + 9 additional = 10 total

    with pytest.raises(PayloadValidationError, match="at most 9 total reference images"):
        adapter.validate(payload)


def test_xai_grok_imagine_video_compile_shape():
    adapter = XaiGrokImagineVideoAdapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot @Image1 test entity"
    assert payload.body["reference_image_urls"] == ["https://img.example/aria.png"]
    assert payload.body["duration"] == 5
    assert payload.body["resolution"] == "480p"
    adapter.validate(payload)  # should not raise


def test_xai_grok_imagine_video_requires_at_least_one_entity():
    # Unlike the other real adapters, this model has no prompt-only mode --
    # reference_image_urls is a required field with a real minimum of 1.
    adapter = XaiGrokImagineVideoAdapter()
    with pytest.raises(PayloadValidationError, match="at least one entity"):
        adapter.compile(_request([]))


def test_xai_grok_imagine_video_accepts_its_real_duration_range():
    adapter = XaiGrokImagineVideoAdapter()
    payload = adapter.compile(_request([_entity()], duration_seconds=1))

    assert payload.body["duration"] == 1


def test_xai_grok_imagine_video_rejects_duration_outside_real_range():
    adapter = XaiGrokImagineVideoAdapter()
    with pytest.raises(PayloadValidationError, match="duration_seconds"):
        adapter.compile(_request([_entity()], duration_seconds=11))


def test_xai_grok_imagine_video_total_image_count_over_cap_raises():
    adapter = XaiGrokImagineVideoAdapter()
    entity = _entity(additional_reference_images=[f"https://img.example/aria-{i}.png" for i in range(7)])
    payload = adapter.compile(_request([entity]))  # 1 primary + 7 additional = 8 total

    with pytest.raises(PayloadValidationError, match="at most 7 total reference images"):
        adapter.validate(payload)


def test_gemini_omni_flash_compile_shape():
    adapter = GeminiOmniFlashAdapter()
    payload = adapter.compile(_request([_entity()]))

    assert payload.body["prompt"] == "a test shot <IMAGE_REF_0> test entity"
    assert payload.body["image_urls"] == ["https://img.example/aria.png"]
    assert payload.body["duration"] == 5
    assert payload.body["resolution"] == "360p"
    adapter.validate(payload)  # should not raise


def test_gemini_omni_flash_works_with_zero_entities():
    # Unlike xai_grok_imagine_video, this model's image_urls has no
    # required minimum -- prompt-only generation is valid.
    adapter = GeminiOmniFlashAdapter()
    payload = adapter.compile(_request([]))

    assert payload.body["image_urls"] == []
    adapter.validate(payload)  # should not raise


def test_gemini_omni_flash_falls_back_to_cheapest_tier_for_unmapped_resolution():
    # This project's own canonical default ("480p") isn't one of this
    # model's real tiers at all -- it should fall through to the
    # cheapest real tier rather than erroring or silently misconfiguring.
    adapter = GeminiOmniFlashAdapter()
    payload = adapter.compile(_request([_entity()], resolution="480p"))

    assert payload.body["resolution"] == "360p"


def test_gemini_omni_flash_rejects_duration_outside_real_range():
    adapter = GeminiOmniFlashAdapter()
    with pytest.raises(PayloadValidationError, match="duration_seconds"):
        adapter.compile(_request([_entity()], duration_seconds=11))


def test_gemini_omni_flash_total_image_count_over_cap_raises():
    adapter = GeminiOmniFlashAdapter()
    entity = _entity(additional_reference_images=[f"https://img.example/aria-{i}.png" for i in range(10)])
    payload = adapter.compile(_request([entity]))  # 1 primary + 10 additional = 11 total

    with pytest.raises(PayloadValidationError, match="at most 10 total reference images"):
        adapter.validate(payload)
