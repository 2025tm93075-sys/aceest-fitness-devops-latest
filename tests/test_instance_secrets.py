"""Secrets are generated once per installation, never hard-coded."""

import os
import stat

from aceest.instance_secrets import load_or_create
from app import create_app


def test_generates_once_and_reuses(tmp_path):
    first, created = load_or_create(str(tmp_path), ".k")
    second, created_again = load_or_create(str(tmp_path), ".k")
    assert created and not created_again
    assert first == second and len(first) >= 32
    assert stat.S_IMODE(os.stat(tmp_path / ".k").st_mode) == 0o600
    assert [p.name for p in tmp_path.iterdir()] == [".k"]   # no temp files left


def test_app_generates_missing_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    app = create_app({"DATABASE": str(tmp_path / "a.db")})
    password = (tmp_path / ".admin_password").read_text()
    assert app.config["SECRET_KEY"] == (tmp_path / ".secret_key").read_text()
    assert app.config["ADMIN_PASSWORD"] == password and password != "admin"
    resp = app.test_client().post("/api/auth/login",
                                  json={"username": "admin", "password": password})
    assert resp.status_code == 200
    # a second worker in the same container sees the same values
    assert create_app({"DATABASE": str(tmp_path / "a.db")}).config["SECRET_KEY"] == \
        app.config["SECRET_KEY"]


def test_environment_values_win(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-env")
    monkeypatch.setenv("ADMIN_PASSWORD", "env-pass")
    app = create_app({"DATABASE": str(tmp_path / "b.db")})
    assert app.config["SECRET_KEY"] == "from-env"
    assert not (tmp_path / ".admin_password").exists()
