"""Local, zero-cost visual-consistency check via CLIP image embeddings.

Compares a brand's canonical reference image to sampled frames from a
generated video by cosine similarity of CLIP embeddings. This is a general
visual-similarity signal (composition, colors, overall subject) rather than
a face-identity check — that tradeoff was chosen deliberately so this works
for every entity kind the canonical schema allows (character, product,
location), not just human faces, and needs no paid API or account.

The CLIP model is loaded once per process and cached (`_get_clip_model`),
since loading it is the expensive part of every call. Loading it requires
downloading pretrained weights on first use, which needs network access —
callers that want a fully offline/fast path (e.g. most of the test suite)
should mock this module's functions rather than invoke it for real.
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import httpx
from PIL import Image

_MODEL_NAME = "ViT-B-32"
_PRETRAINED = "openai"

# Set this to a locally-downloaded weights file (.safetensors or .bin) to
# skip open_clip's own Hugging Face Hub download entirely — useful on
# networks where that download is unreliable. open_clip's `pretrained`
# argument accepts a local checkpoint path directly, so no Hub cache
# trickery is needed.
_LOCAL_WEIGHTS_ENV_VAR = "KINOSTATE_CLIP_WEIGHTS_PATH"

# Heuristic default, not yet calibrated against real generations (none
# existed at implementation time — fal.ai wasn't funded yet). Re-tune once
# real output videos are available to compare against known-consistent and
# known-inconsistent pairs.
DEFAULT_SIMILARITY_THRESHOLD = 0.75
FRAME_SAMPLE_COUNT = 3


class VisualSimilarityError(RuntimeError):
    """Raised when a reference image or generated video can't be fetched or read."""


@lru_cache(maxsize=1)
def _get_clip_model() -> tuple[Any, Any]:
    import open_clip

    pretrained = os.environ.get(_LOCAL_WEIGHTS_ENV_VAR) or _PRETRAINED
    model, _, preprocess = open_clip.create_model_and_transforms(_MODEL_NAME, pretrained=pretrained)
    model.eval()
    return model, preprocess


def _embed_image(image: Image.Image):
    import torch

    model, preprocess = _get_clip_model()
    with torch.no_grad():
        tensor = preprocess(image).unsqueeze(0)
        features = model.encode_image(tensor)
        return features / features.norm(dim=-1, keepdim=True)


def _download(url: str, suffix: str) -> Path:
    try:
        response = httpx.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise VisualSimilarityError(f"could not download {url!r}: {exc}") from exc

    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    handle.write(response.content)
    handle.close()
    return Path(handle.name)


def sample_frames(video_path: Path, count: int = FRAME_SAMPLE_COUNT) -> list[Image.Image]:
    """Pull `count` frames spread evenly across a local video file."""
    capture = cv2.VideoCapture(str(video_path))
    try:
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            raise VisualSimilarityError(f"could not read any frames from {video_path}")

        indices = [int(total_frames * (i + 1) / (count + 1)) for i in range(count)]
        frames = []
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))

        if not frames:
            raise VisualSimilarityError(f"could not decode any sampled frames from {video_path}")
        return frames
    finally:
        capture.release()


def check_visual_consistency(
    reference_image_urls: str | list[str],
    output_video_url: str,
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[bool, float, str]:
    """Compare one or more reference images to sampled frames of a generated video.

    Returns (passed, best_similarity_score, reasoning). Uses the *best*
    match across every (reference image x sampled frame) pair rather than
    an average, in both directions: a character only needs to be clearly
    recognizable in some frames, not every single one (camera angle and
    motion naturally vary similarity across a clip even when the character
    itself is consistent) — and a generation shot from an angle matching
    any one of several reference photos is a genuine match, not a miss
    just because it doesn't match the *first* reference photo.
    """
    if isinstance(reference_image_urls, str):
        reference_image_urls = [reference_image_urls]

    reference_paths = [_download(url, suffix=".ref") for url in reference_image_urls]
    video_path = _download(output_video_url, suffix=".mp4")
    try:
        reference_embeddings = [_embed_image(Image.open(path).convert("RGB")) for path in reference_paths]
        frames = sample_frames(video_path)
        frame_embeddings = [_embed_image(frame) for frame in frames]
        similarities = [
            float((reference_embedding @ frame_embedding.T).item())
            for reference_embedding in reference_embeddings
            for frame_embedding in frame_embeddings
        ]
    finally:
        for path in reference_paths:
            path.unlink(missing_ok=True)
        video_path.unlink(missing_ok=True)

    best_score = max(similarities)
    passed = best_score >= threshold
    reasoning = (
        f"visual similarity (CLIP, best of {len(reference_paths)} reference image(s) x "
        f"{len(frames)} sampled frames): {best_score:.3f} {'>=' if passed else '<'} threshold {threshold}"
    )
    return passed, best_score, reasoning
