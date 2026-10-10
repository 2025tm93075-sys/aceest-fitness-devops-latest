"""Shared Pytest fixtures: an isolated app + database per test."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.db"),
        "ADMIN_USER": "admin",
        "ADMIN_PASSWORD": "s3cret",
    })
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_client(client):
    """Create one fully-populated client and return its JSON."""
    resp = client.post("/api/clients", json={
        "name": "Arjun",
        "age": 30,
        "height": 180,
        "weight": 80,
        "program": "fat-loss-3day",
        "target_weight": 72,
        "target_adherence": 85,
        "membership_end": "2099-12-31",
    })
    assert resp.status_code == 201
    return resp.get_json()
