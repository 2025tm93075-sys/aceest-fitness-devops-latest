"""Tests for deployment metadata, readiness and fault injection (v1.1.0)."""

import importlib

import pytest

from aceest import __version__
from aceest.deployment import deployment_info, fault_mode


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("DEPLOYMENT_TRACK", "UI_VARIANT", "POD_NAME", "FAULT_INJECTION"):
        monkeypatch.delenv(key, raising=False)


def test_deployment_info_defaults():
    info = deployment_info()
    assert info["version"] == __version__
    assert info["track"] == "local"
    assert info["variant"] == "A"
    assert info["pod"]


def test_deployment_info_from_env(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TRACK", "canary")
    monkeypatch.setenv("UI_VARIANT", "b")
    monkeypatch.setenv("POD_NAME", "aceest-canary-7d9f")
    assert deployment_info() == {"version": __version__, "track": "canary",
                                 "variant": "B", "pod": "aceest-canary-7d9f"}


def test_invalid_variant_falls_back_to_a(monkeypatch):
    monkeypatch.setenv("UI_VARIANT", "Z")
    assert deployment_info()["variant"] == "A"


@pytest.mark.parametrize("value, expected", [
    ("", ""), ("none", "none"), ("HEALTH", "health"), ("explode", "")])
def test_fault_mode(monkeypatch, value, expected):
    monkeypatch.setenv("FAULT_INJECTION", value)
    assert fault_mode() == expected


def test_version_endpoint_reports_track(client, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TRACK", "green")
    data = client.get("/api/version").get_json()
    assert data["version"] == __version__ and data["track"] == "green"


def test_deployment_headers_on_every_response(client, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TRACK", "blue")
    monkeypatch.setenv("POD_NAME", "pod-1")
    for path in ("/", "/health", "/api/programs"):
        headers = client.get(path).headers
        assert headers["X-App-Version"] == __version__
        assert headers["X-Deployment-Track"] == "blue"
        assert headers["X-Pod"] == "pod-1"
        assert headers["X-UI-Variant"] == "A"


def test_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.get_json()["ready"] is True


def test_fault_injection_fails_probes(client, monkeypatch):
    monkeypatch.setenv("FAULT_INJECTION", "health")
    assert client.get("/health").status_code == 503
    assert client.get("/ready").status_code == 503
    # business endpoints keep working; only the probes signal the fault
    assert client.get("/api/programs").status_code == 200


def test_banner_shows_version_and_track(client, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_TRACK", "stable")
    body = client.get("/").get_data(as_text=True)
    assert f"v{__version__}" in body and "stable" in body


def test_entrypoint_exposes_wsgi_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "entry.db"))
    module = importlib.import_module("ACEest_Fitness")
    module = importlib.reload(module)
    assert module.app.test_client().get("/health").status_code == 200
