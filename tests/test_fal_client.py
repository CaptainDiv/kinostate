"""Exercises router.clients.fal_client against a fake HTTP client.

No real network calls, no credits spent — a `client` object with mocked
`.post`/`.get` methods is injected directly, so these tests run fast and
free while still covering the real submit -> poll -> fetch-result control
flow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kinostate.router.clients.fal_client import FalError, extract_output_url, run_model


def _response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body or {}
    if status_code >= 400:
        response.raise_for_status.side_effect = RuntimeError(f"HTTP {status_code}")
    return response


def test_run_model_success():
    client = MagicMock()
    client.post.return_value = _response(
        json_body={
            "request_id": "req-1",
            "status_url": "https://queue.fal.run/m/requests/req-1/status",
            "response_url": "https://queue.fal.run/m/requests/req-1",
        }
    )
    client.get.return_value = _response(
        json_body={"status": "COMPLETED", "video": {"url": "https://cdn.fal/out.mp4"}}
    )

    result = run_model("fal-ai/kling-video/o1/standard/reference-to-video", {"prompt": "a cat"}, client=client)

    assert extract_output_url(result) == "https://cdn.fal/out.mp4"
    client.post.assert_called_once_with(
        "/fal-ai/kling-video/o1/standard/reference-to-video", json={"prompt": "a cat"}
    )


def test_run_model_polls_until_completed():
    client = MagicMock()
    client.post.return_value = _response(
        json_body={"status_url": "https://queue.fal.run/m/status", "response_url": "https://queue.fal.run/m/result"}
    )
    client.get.side_effect = [
        _response(json_body={"status": "IN_QUEUE"}),
        _response(json_body={"status": "IN_PROGRESS"}),
        # third get() call is the status poll returning COMPLETED, the
        # fourth is the separate fetch of response_url.
        _response(json_body={"status": "COMPLETED"}),
        _response(json_body={"video": {"url": "https://cdn.fal/out2.mp4"}}),
    ]

    result = run_model("m", {}, client=client, poll_interval_seconds=0)

    assert extract_output_url(result) == "https://cdn.fal/out2.mp4"
    assert client.get.call_count == 4


def test_run_model_failed_status_raises():
    client = MagicMock()
    client.post.return_value = _response(
        json_body={"status_url": "https://queue.fal.run/m/status", "response_url": "https://queue.fal.run/m/result"}
    )
    client.get.return_value = _response(json_body={"status": "ERROR", "error": "bad input"})

    with pytest.raises(FalError, match="bad input"):
        run_model("m", {}, client=client)


def test_run_model_submit_error_raises_with_body():
    client = MagicMock()
    client.post.return_value = _response(status_code=403, json_body={"detail": "insufficient balance"})

    with pytest.raises(FalError, match="insufficient balance"):
        run_model("m", {}, client=client)


def test_run_model_timeout_raises():
    client = MagicMock()
    client.post.return_value = _response(
        json_body={"status_url": "https://queue.fal.run/m/status", "response_url": "https://queue.fal.run/m/result"}
    )
    client.get.return_value = _response(json_body={"status": "IN_PROGRESS"})

    with pytest.raises(FalError, match="did not complete within"):
        run_model("m", {}, client=client, timeout_seconds=0, poll_interval_seconds=0)


def test_run_model_missing_status_url_raises():
    client = MagicMock()
    client.post.return_value = _response(json_body={"request_id": "req-1"})

    with pytest.raises(FalError, match="missing status_url/response_url"):
        run_model("m", {}, client=client)


def test_extract_output_url_missing_key_raises():
    with pytest.raises(FalError, match="could not find a video URL"):
        extract_output_url({"status": "COMPLETED"})


def test_extract_output_url_plain_string():
    assert extract_output_url({"video": "https://cdn.fal/plain.mp4"}) == "https://cdn.fal/plain.mp4"
