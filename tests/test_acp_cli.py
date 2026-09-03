"""Tests for economic.clients.acp_cli (FR-23..25) — all offline, subprocess mocked."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from kinostate.economic.clients import acp_cli
from kinostate.economic.clients.acp_cli import (
    AcpCliError,
    accept_job,
    complete_job,
    drain_events,
    reject_job,
    submit_deliverable,
    whoami,
)

_FAKE_ACP_PATH = "/fake/acp"


@pytest.fixture(autouse=True)
def _mock_acp_executable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: _FAKE_ACP_PATH)


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_whoami_returns_parsed_json(monkeypatch):
    captured = {}

    def _fake_run(args, capture_output, text, env):
        captured["args"] = args
        return _FakeCompletedProcess(stdout='{"agentId": "abc123"}')

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = whoami()

    assert result == {"agentId": "abc123"}
    assert captured["args"] == [_FAKE_ACP_PATH, "agent", "whoami", "--json"]


def test_run_acp_defaults_to_testnet(monkeypatch):
    captured = {}

    def _fake_run(args, capture_output, text, env):
        captured["env"] = env
        return _FakeCompletedProcess(stdout="{}")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    monkeypatch.delenv("IS_TESTNET", raising=False)

    whoami()

    assert captured["env"]["IS_TESTNET"] == "true"


def test_run_acp_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(returncode=1, stderr="not logged in"))

    with pytest.raises(AcpCliError, match="not logged in"):
        whoami()


def test_run_acp_raises_on_bad_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(stdout="not json"))

    with pytest.raises(AcpCliError, match="unparseable"):
        whoami()


def test_run_acp_raises_when_cli_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(AcpCliError, match="not installed"):
        whoami()


def test_drain_events_parses_list(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeCompletedProcess(stdout='[{"job_id": "1"}]'))

    events = drain_events("/tmp/events.jsonl", limit=5)

    assert events == [{"job_id": "1"}]


def test_accept_job_builds_expected_argv(monkeypatch):
    captured = {}

    def _fake_run(args, capture_output, text, env):
        captured["args"] = args
        return _FakeCompletedProcess(stdout="{}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    accept_job("job-1", 0.05, chain_id=84532)

    assert captured["args"] == [
        _FAKE_ACP_PATH, "provider", "set-budget", "--job-id", "job-1", "--amount", "0.05", "--chain-id", "84532", "--json",
    ]


def test_submit_deliverable_builds_expected_argv(monkeypatch):
    captured = {}

    def _fake_run(args, capture_output, text, env):
        captured["args"] = args
        return _FakeCompletedProcess(stdout="{}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    submit_deliverable("job-1", "some deliverable text")

    assert captured["args"] == [
        _FAKE_ACP_PATH, "provider", "submit", "--job-id", "job-1", "--deliverable", "some deliverable text",
        "--chain-id", str(acp_cli.DEFAULT_TESTNET_CHAIN_ID), "--json",
    ]


def test_complete_and_reject_job_build_expected_argv(monkeypatch):
    captured = []

    def _fake_run(args, capture_output, text, env):
        captured.append(args)
        return _FakeCompletedProcess(stdout="{}")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    complete_job("job-1", "looks good")
    reject_job("job-1", "bad output")

    assert captured[0] == [
        _FAKE_ACP_PATH, "client", "complete", "--job-id", "job-1", "--reason", "looks good",
        "--chain-id", str(acp_cli.DEFAULT_TESTNET_CHAIN_ID), "--json",
    ]
    assert captured[1] == [
        _FAKE_ACP_PATH, "client", "reject", "--job-id", "job-1", "--reason", "bad output",
        "--chain-id", str(acp_cli.DEFAULT_TESTNET_CHAIN_ID), "--json",
    ]
