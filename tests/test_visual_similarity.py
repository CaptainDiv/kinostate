"""Tests for verification.visual_similarity.

Frame-sampling tests use a real tiny synthetic video (via opencv) — fast,
offline, no model involved. The similarity-decision test monkeypatches
`_embed_image` itself (real torch tensors, fake values) so the CLIP model
never has to load — that's the expensive part this suite deliberately
avoids by default. A real CLIP-loading test exists but is skipped unless
explicitly opted into, since it downloads model weights on first use.
"""

from __future__ import annotations

import os

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

from kinostate.verification import visual_similarity
from kinostate.verification.visual_similarity import (
    VisualSimilarityError,
    check_visual_consistency,
    sample_frames,
)


def _write_synthetic_video(path, frame_count: int = 20, size: int = 32) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (size, size))
    try:
        for i in range(frame_count):
            frame = np.full((size, size, 3), (i * 12) % 256, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_sample_frames_returns_requested_count(tmp_path):
    video_path = tmp_path / "clip.mp4"
    _write_synthetic_video(video_path)

    frames = sample_frames(video_path, count=3)

    assert len(frames) == 3
    assert all(isinstance(frame, Image.Image) for frame in frames)


def test_sample_frames_raises_on_unreadable_video(tmp_path):
    empty_path = tmp_path / "empty.mp4"
    empty_path.write_bytes(b"")

    with pytest.raises(VisualSimilarityError):
        sample_frames(empty_path)


class _FakeImage(str):
    def convert(self, mode):
        return self


def test_check_visual_consistency_passes_when_best_frame_matches(monkeypatch, tmp_path):
    embeddings = {
        "reference": torch.tensor([[1.0, 0.0]]),
        "frame_low": torch.tensor([[0.0, 1.0]]),
        "frame_high": torch.tensor([[1.0, 0.0]]),
    }

    monkeypatch.setattr(visual_similarity, "_download", lambda url, suffix: tmp_path / suffix.lstrip("."))
    monkeypatch.setattr(visual_similarity, "sample_frames", lambda path: ["frame_low", "frame_high"])
    monkeypatch.setattr(visual_similarity.Image, "open", lambda path: _FakeImage("reference"))
    monkeypatch.setattr(visual_similarity, "_embed_image", lambda image: embeddings[str(image)])

    passed, score, reasoning = check_visual_consistency("http://ref", "http://video", threshold=0.75)

    assert passed is True
    assert score == pytest.approx(1.0)
    assert "best of 2 sampled frames" in reasoning


def test_check_visual_consistency_fails_below_threshold(monkeypatch, tmp_path):
    embeddings = {
        "reference": torch.tensor([[1.0, 0.0]]),
        "frame_low": torch.tensor([[0.0, 1.0]]),
        "frame_mid": torch.tensor([[0.6, 0.8]]),
    }

    monkeypatch.setattr(visual_similarity, "_download", lambda url, suffix: tmp_path / suffix.lstrip("."))
    monkeypatch.setattr(visual_similarity, "sample_frames", lambda path: ["frame_low", "frame_mid"])
    monkeypatch.setattr(visual_similarity.Image, "open", lambda path: _FakeImage("reference"))
    monkeypatch.setattr(visual_similarity, "_embed_image", lambda image: embeddings[str(image)])

    passed, score, _reasoning = check_visual_consistency("http://ref", "http://video", threshold=0.75)

    assert passed is False
    assert score == pytest.approx(0.6)


def test_download_wraps_http_errors(monkeypatch):
    import httpx

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(visual_similarity.httpx, "get", _raise)

    with pytest.raises(VisualSimilarityError, match="could not download"):
        visual_similarity._download("http://unreachable", suffix=".mp4")


@pytest.mark.skipif(
    os.environ.get("KINOSTATE_RUN_SLOW_TESTS") != "1",
    reason="downloads real CLIP weights on first run; opt in with KINOSTATE_RUN_SLOW_TESTS=1",
)
def test_embed_image_real_clip_same_image_is_near_identical():
    image = Image.new("RGB", (64, 64), color=(255, 0, 0))
    embedding_a = visual_similarity._embed_image(image)
    embedding_b = visual_similarity._embed_image(image)

    similarity = float((embedding_a @ embedding_b.T).item())
    assert similarity > 0.99
