"""
Post-deployment smoke tests.

These run against a live deployment, not the Flask test client. They are
skipped unless SMOKE_BASE_URL is set. In the pipeline they run inside the
cluster as a Kubernetes Job built from the test image (k8s/jobs/smoke-test.yaml):

    SMOKE_BASE_URL=http://aceest-canary.aceest.svc.cluster.local \
    SMOKE_EXPECT_VERSION=1.2.0 SMOKE_EXPECT_TRACK=canary pytest tests/smoke

Only stateless endpoints are checked, so results do not depend on which
replica answers.
"""

import json
import os
import time
import urllib.error
import urllib.request

import pytest

BASE_URL = os.environ.get("SMOKE_BASE_URL", "").rstrip("/")
EXPECT_VERSION = os.environ.get("SMOKE_EXPECT_VERSION", "").lstrip("v")
EXPECT_TRACK = os.environ.get("SMOKE_EXPECT_TRACK", "")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="SMOKE_BASE_URL not set")


def call(path, payload=None, retries=10):
    """GET (or POST JSON) with retries while the Service warms up."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    last_error = None
    for _ in range(retries):
        req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read().decode()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read().decode()
        except (urllib.error.URLError, OSError) as err:
            last_error = err
            time.sleep(2)
    raise AssertionError(f"{BASE_URL}{path} unreachable: {last_error}")


def test_health():
    status, _, body = call("/health")
    assert status == 200 and json.loads(body)["status"] == "ok"


def test_ready():
    status, _, body = call("/ready")
    assert status == 200 and json.loads(body)["ready"] is True


def test_expected_version_and_track():
    status, headers, body = call("/api/version")
    info = json.loads(body)
    assert status == 200
    if EXPECT_VERSION:
        assert info["version"] == EXPECT_VERSION, f"running {info['version']}"
    if EXPECT_TRACK:
        assert info["track"] == EXPECT_TRACK, f"track {info['track']}"
    assert headers.get("X-App-Version") == info["version"]


def test_program_catalogue():
    status, _, body = call("/api/programs")
    assert status == 200 and len(json.loads(body)) >= 4


def test_calorie_calculator():
    status, _, body = call("/api/calculate/calories", {"weight": 70, "program": "muscle-gain-ppl"})
    assert status == 200 and json.loads(body)["calories"] == 2450


def test_validation_still_rejects_bad_input():
    status, _, _ = call("/api/calculate/bmi", {"weight": -5, "height": 170})
    assert status == 400


def test_dashboard_renders():
    status, _, body = call("/")
    assert status == 200 and "ACEest" in body
