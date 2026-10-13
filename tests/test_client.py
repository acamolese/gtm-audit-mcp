"""The client against a fake session: throttling, retries, read-merge-write."""

from __future__ import annotations

import json

import pytest

from mcp_gtm_audit import client as client_module
from mcp_gtm_audit.client import GTMAPIError, GTMClient


class FakeResponse:
    def __init__(self, status, body=None, text=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, headers=None, params=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json})
        return self.responses.pop(0)


class FakeCreds:
    valid = True
    token = "t"


def make_client(responses):
    sleeps = []
    clock = {"t": 0.0}

    def sleep(seconds):
        sleeps.append(seconds)
        clock["t"] += seconds

    c = GTMClient(FakeCreds(), sleep=sleep, clock=lambda: clock["t"])
    c.session = FakeSession(responses)
    return c, sleeps, clock


def test_sliding_window_sleeps_only_when_the_quota_is_used_up():
    c, sleeps, _ = make_client([FakeResponse(200, {"account": []})] * 40)
    for _ in range(client_module.RATE_LIMIT_CALLS):
        c.list_accounts()
    assert sleeps == []
    c.list_accounts()
    assert len(sleeps) == 1 and sleeps[0] == pytest.approx(client_module.RATE_LIMIT_WINDOW)


def test_429_is_retried_then_succeeds():
    c, sleeps, _ = make_client(
        [FakeResponse(429, text="quota"), FakeResponse(200, {"account": [{"accountId": "1"}]})]
    )
    assert c.list_accounts() == [{"accountId": "1"}]
    assert sleeps == [15.0]


def test_http_errors_carry_status_path_and_hint():
    c, _, _ = make_client([FakeResponse(404, text="not found")])
    with pytest.raises(GTMAPIError) as exc:
        c.get_container("1", "GTM-ABC")
    assert exc.value.status == 404
    assert "numeric" in str(exc.value)


def test_update_entity_reads_merges_and_sends_the_fingerprint():
    current = {
        "tagId": "7",
        "name": "Old",
        "type": "html",
        "fingerprint": "fp1",
        "path": "p",
        "tagManagerUrl": "u",
        "parameter": [{"key": "html", "value": "a"}],
        "firingTriggerId": ["1"],
    }
    c, _, _ = make_client(
        [FakeResponse(200, current), FakeResponse(200, {**current, "name": "New", "fingerprint": "fp2"})]
    )
    out = c.update_entity("1", "2", "3", "tag", "7", {"name": "New"})
    assert out["name"] == "New"
    put = c.session.calls[1]
    assert put["method"] == "PUT"
    assert put["params"] == {"fingerprint": "fp1"}
    assert put["json"]["name"] == "New" and put["json"]["firingTriggerId"] == ["1"]
    assert "fingerprint" not in put["json"] and "tagManagerUrl" not in put["json"]


def test_unknown_kind_is_rejected_before_any_request():
    c, _, _ = make_client([])
    with pytest.raises(ValueError):
        c.get_entity("1", "2", "3", "zone", "1")
    assert c.session.calls == []


def test_writes_are_spaced_and_back_off_longer():
    c, sleeps, _ = make_client(
        [
            FakeResponse(200, {"workspaceId": "1"}),
            FakeResponse(429, text="x"),
            FakeResponse(200, {"workspaceId": "2"}),
        ]
    )
    c.create_workspace("1", "2", "a")
    c.create_workspace("1", "2", "b")
    # second write waited the minimum interval, then backed off on the 429 with the write schedule
    assert sleeps[0] == pytest.approx(client_module.WRITE_MIN_INTERVAL)
    assert client_module.WRITE_BACKOFF[0] in sleeps


def test_a_write_that_never_recovers_fails_with_the_quota_hint():
    c, _, _ = make_client([FakeResponse(429, text="rateLimitExceeded")] * 10)
    with pytest.raises(GTMAPIError) as exc:
        c.create_workspace("1", "2", "a")
    assert exc.value.status == 429
    assert "own, smaller allowance" in str(exc.value)
