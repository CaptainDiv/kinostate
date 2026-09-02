"""Thin client for fal.ai's queue-based model inference API.

fal's flow: POST the model's own input fields directly (no wrapper key) to
`https://queue.fal.run/{model_path}` to submit a job; the response carries
`status_url`/`response_url`. Poll `status_url` until `status == "COMPLETED"`,
then GET `response_url` for the final result. Auth is `Authorization: Key
{FAL_KEY}` — confirmed against fal's own docs; note this is `Key`, not
`Bearer`, an easy copy-paste mistake from the wireflow client this replaces.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

FAL_QUEUE_BASE_URL = "https://queue.fal.run"
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_POLL_INTERVAL_SECONDS = 3.0

_FAILED_STATUSES = ("ERROR", "FAILED")


class FalError(RuntimeError):
    """Raised on any failure to get a completed result from fal.ai.

    Covers HTTP errors (including a billing/balance rejection on submit —
    the exact status code for that hasn't been confirmed against a live
    account yet, so any non-2xx response is surfaced with its full body
    rather than assumed to be a specific code), a failed job status, a poll
    timeout, and an unrecognized success response shape.
    """


def run_model(
    model_path: str,
    inputs: dict[str, Any],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Submit a fal.ai model request and block until it completes.

    Returns the completed result's full JSON body. Raises FalError on any
    failure rather than returning a partial or mock result.
    """
    owns_client = client is None
    http = client or httpx.Client(base_url=FAL_QUEUE_BASE_URL, headers=_auth_header(), timeout=30.0)
    try:
        status_url, response_url = _submit(http, model_path, inputs)
        _poll_until_done(http, status_url, timeout_seconds, poll_interval_seconds)
        return _fetch_result(http, response_url)
    finally:
        if owns_client:
            http.close()


def extract_output_url(result: dict[str, Any]) -> str:
    """Pull the generated video URL out of a completed fal.ai result.

    Confirmed shape: {"video": {"url": ..., "file_name": ..., ...}}. Also
    accepts a plain string under "video" in case a given model departs from
    that shape, and raises FalError (rather than returning None) if neither
    is present, so an unexpected response shape fails loudly.
    """
    video = result.get("video")
    if isinstance(video, dict) and video.get("url"):
        return video["url"]
    if isinstance(video, str) and video:
        return video

    raise FalError(f"could not find a video URL in fal result: {result}")


def _api_key() -> str:
    key = os.environ.get("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY is not set")
    return key


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Key {_api_key()}"}


def _submit(http: httpx.Client, model_path: str, inputs: dict[str, Any]) -> tuple[str, str]:
    response = http.post(f"/{model_path}", json=inputs)
    if response.status_code >= 400:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        raise FalError(f"fal submit failed ({response.status_code}): {detail}")

    body = response.json()
    status_url = body.get("status_url")
    response_url = body.get("response_url")
    if not status_url or not response_url:
        raise FalError(f"fal submit response missing status_url/response_url: {body}")
    return status_url, response_url


def _poll_until_done(
    http: httpx.Client,
    status_url: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        response = http.get(status_url)
        response.raise_for_status()
        body = response.json()
        status = body.get("status")

        if status == "COMPLETED":
            return
        if status in _FAILED_STATUSES:
            raise FalError(f"fal request failed: {body}")

        if time.monotonic() >= deadline:
            raise FalError(f"fal request did not complete within {timeout_seconds}s")
        time.sleep(poll_interval_seconds)


def _fetch_result(http: httpx.Client, response_url: str) -> dict[str, Any]:
    response = http.get(response_url)
    response.raise_for_status()
    return response.json()
