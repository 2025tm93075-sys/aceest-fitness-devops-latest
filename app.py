"""
ACEest Fitness & Gym - Flask web application.

Author : Bandgar Omkar Sudhakar Sheetal (2025TM93075)
Course : Introduction to DevOps (CSIZG514/SEZG514) - Assignment 1

Run locally:
    python app.py                       # dev server on http://127.0.0.1:5000
    gunicorn -b 0.0.0.0:5000 "app:create_app()"   # production-style
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from aceest import __version__
from aceest import fitness
from aceest.database import get_db, init_db
from aceest.fitness import ValidationError

CLIENT_FIELDS = ("name", "age", "height", "weight", "program",
                 "target_weight", "target_adherence", "membership_end")


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #
def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("DATABASE_PATH",
                                os.path.join(app.instance_path, "aceest_fitness.db")),
        ADMIN_USER=os.environ.get("ADMIN_USER", "admin"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin"),
    )
    if test_config:
        app.config.update(test_config)

    init_db(app)
    _register_error_handlers(app)
    _register_routes(app)
    return app


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def _number(data: dict, key: str, cast=float, required: bool = False):
    value = data.get(key)
    if value in (None, ""):
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    try:
        return cast(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"'{key}' must be numeric") from exc


def _clean_client(data: dict, partial: bool = False) -> dict:
    """Validate client input and derive the calorie target."""
    clean: dict = {}
    if "name" in data or not partial:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValidationError("'name' is required")
        clean["name"] = name
    for key, cast in (("age", int), ("height", float), ("weight", float),
                      ("target_weight", float)):
        if key in data:
            value = _number(data, key, cast)
            if value is not None and value <= 0:
                raise ValidationError(f"'{key}' must be positive")
            clean[key] = value
    if "target_adherence" in data and data["target_adherence"] not in (None, ""):
        clean["target_adherence"] = fitness.validate_adherence(data["target_adherence"])
    if "program" in data and data["program"]:
        fitness.get_program(data["program"])
        clean["program"] = data["program"]
    if "membership_end" in data and data["membership_end"]:
        fitness.membership_status(data["membership_end"])  # validates format
        clean["membership_end"] = data["membership_end"]
    return clean


def _client_or_404(client_id: int) -> sqlite3.Row:
    row = get_db().execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if row is None:
        abort(404, description=f"Client {client_id} not found")
    return row


def _recalculate_calories(client_id: int) -> None:
    db = get_db()
    row = db.execute("SELECT weight, program FROM clients WHERE id = ?",
                     (client_id,)).fetchone()
    calories = None
    if row["weight"] and row["program"]:
        calories = fitness.calculate_calories(row["weight"], row["program"])
    db.execute("UPDATE clients SET calories = ? WHERE id = ?", (calories, client_id))


def _client_summary(client_id: int) -> dict:
    db = get_db()
    client = dict(_client_or_404(client_id))
    adherence = [r["adherence"] for r in db.execute(
        "SELECT adherence FROM progress WHERE client_id = ? ORDER BY id", (client_id,))]
    summary = {
        "client": client,
        "adherence": fitness.adherence_summary(adherence),
        "membership": fitness.membership_status(client["membership_end"]),
        "bmi": None,
        "workouts_logged": db.execute(
            "SELECT COUNT(*) FROM workouts WHERE client_id = ?", (client_id,)).fetchone()[0],
    }
    if client["weight"] and client["height"]:
        bmi = fitness.calculate_bmi(client["weight"], client["height"])
        summary["bmi"] = {"value": bmi, **fitness.bmi_category(bmi)}
    return summary


# --------------------------------------------------------------------------- #
# Error handling - API routes always answer in JSON
# --------------------------------------------------------------------------- #
def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation(err):
        return jsonify(error=str(err)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def handle_integrity(err):
        return jsonify(error="Conflict: " + str(err)), 409

    @app.errorhandler(HTTPException)
    def handle_http(err):
        if request.path.startswith("/api/") or request.path == "/health":
            return jsonify(error=err.description), err.code
        return err


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def _register_routes(app: Flask) -> None:  # noqa: C901 - flat route table

    # ---------- Ops ----------
    @app.get("/health")
    def health():
        get_db().execute("SELECT 1")
        return jsonify(status="ok", version=__version__)

    @app.get("/api/version")
    def version():
        return jsonify(app="ACEest Fitness & Gym", version=__version__)

    # ---------- Web UI ----------
    @app.get("/")
    def index():
        clients = get_db().execute(
            "SELECT id, name, program, calories, membership_end FROM clients ORDER BY name"
        ).fetchall()
        return render_template("index.html", programs=fitness.PROGRAMS, clients=clients,
                               metrics=fitness.SITE_METRICS, version=__version__)

    @app.post("/clients")
    def create_client_form():
        try:
            data = _clean_client(request.form.to_dict())
            client_id = _insert_client(data)
        except ValidationError as err:
            flash(str(err), "error")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("A client with that name already exists", "error")
            return redirect(url_for("index"))
        flash(f"Client {data['name']} saved", "success")
        return redirect(url_for("client_page", client_id=client_id))

    @app.get("/clients/<int:client_id>")
    def client_page(client_id: int):
        summary = _client_summary(client_id)
        db = get_db()
        progress = db.execute("SELECT week, adherence FROM progress WHERE client_id = ? "
                              "ORDER BY id", (client_id,)).fetchall()
        workouts = db.execute("SELECT * FROM workouts WHERE client_id = ? "
                              "ORDER BY date DESC", (client_id,)).fetchall()
        program = fitness.PROGRAMS.get(summary["client"]["program"] or "")
        return render_template("client.html", s=summary, progress=progress,
                               workouts=workouts, program=program, version=__version__)

    # ---------- Programs & calculators ----------
    @app.get("/api/programs")
    def list_programs():
        return jsonify([{"id": pid, **p} for pid, p in fitness.PROGRAMS.items()])

    @app.get("/api/programs/<program_id>")
    def get_program(program_id: str):
        try:
            return jsonify({"id": program_id, **fitness.get_program(program_id)})
        except ValidationError:
            abort(404, description=f"Program '{program_id}' not found")

    @app.post("/api/calculate/calories")
    def calc_calories():
        data = _json_body()
        weight = _number(data, "weight", required=True)
        program = data.get("program")
        if not program:
            raise ValidationError("'program' is required")
        return jsonify(program=program, weight=weight,
                       calories=fitness.calculate_calories(weight, program))

    @app.post("/api/calculate/bmi")
    def calc_bmi():
        data = _json_body()
        bmi = fitness.calculate_bmi(_number(data, "weight", required=True),
                                    _number(data, "height", required=True))
        return jsonify(bmi=bmi, **fitness.bmi_category(bmi))

    # ---------- Auth ----------
    @app.post("/api/auth/login")
    def login():
        data = _json_body()
        row = get_db().execute("SELECT password_hash, role FROM users WHERE username = ?",
                               (data.get("username", ""),)).fetchone()
        if row is None or not check_password_hash(row["password_hash"],
                                                  str(data.get("password", ""))):
            return jsonify(error="Invalid credentials"), 401
        return jsonify(username=data["username"], role=row["role"])

    # ---------- Clients ----------
    def _insert_client(data: dict) -> int:
        db = get_db()
        cols = [c for c in CLIENT_FIELDS if c in data]
        cur = db.execute(
            f"INSERT INTO clients ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [data[c] for c in cols],
        )
        _recalculate_calories(cur.lastrowid)
        db.commit()
        return cur.lastrowid

    @app.get("/api/clients")
    def list_clients():
        rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.post("/api/clients")
    def create_client():
        client_id = _insert_client(_clean_client(_json_body()))
        return jsonify(dict(_client_or_404(client_id))), 201

    @app.get("/api/clients/<int:client_id>")
    def get_client(client_id: int):
        return jsonify(dict(_client_or_404(client_id)))

    @app.put("/api/clients/<int:client_id>")
    def update_client(client_id: int):
        _client_or_404(client_id)
        data = _clean_client(_json_body(), partial=True)
        if not data:
            raise ValidationError("No updatable fields supplied")
        db = get_db()
        db.execute(f"UPDATE clients SET {', '.join(f'{k} = ?' for k in data)} WHERE id = ?",
                   [*data.values(), client_id])
        _recalculate_calories(client_id)
        db.commit()
        return jsonify(dict(_client_or_404(client_id)))

    @app.delete("/api/clients/<int:client_id>")
    def delete_client(client_id: int):
        _client_or_404(client_id)
        db = get_db()
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
        return "", 204

    @app.get("/api/clients/<int:client_id>/summary")
    def client_summary(client_id: int):
        return jsonify(_client_summary(client_id))

    @app.post("/api/clients/<int:client_id>/generate-program")
    def generate_program(client_id: int):
        _client_or_404(client_id)
        data = request.get_json(silent=True) or {}
        result = fitness.generate_program(goal=data.get("goal"))
        return jsonify(client_id=client_id, **result)

    # ---------- Progress ----------
    @app.post("/api/clients/<int:client_id>/progress")
    def add_progress(client_id: int):
        _client_or_404(client_id)
        data = _json_body()
        adherence = fitness.validate_adherence(data.get("adherence"))
        week = data.get("week") or date.today().strftime("Week %U - %Y")
        db = get_db()
        db.execute("INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
                   (client_id, week, adherence))
        db.commit()
        return jsonify(client_id=client_id, week=week, adherence=adherence), 201

    @app.get("/api/clients/<int:client_id>/progress")
    def list_progress(client_id: int):
        _client_or_404(client_id)
        rows = get_db().execute("SELECT week, adherence FROM progress WHERE client_id = ? "
                                "ORDER BY id", (client_id,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # ---------- Workouts ----------
    @app.post("/api/clients/<int:client_id>/workouts")
    def add_workout(client_id: int):
        _client_or_404(client_id)
        data = _json_body()
        workout_type = data.get("workout_type")
        if workout_type not in fitness.WORKOUT_TYPES:
            raise ValidationError(f"'workout_type' must be one of {list(fitness.WORKOUT_TYPES)}")
        duration = _number(data, "duration_min", int, required=True)
        if duration <= 0:
            raise ValidationError("'duration_min' must be positive")
        exercises = data.get("exercises") or []
        for ex in exercises:
            if not ex.get("name"):
                raise ValidationError("Each exercise needs a 'name'")
            for key in ("sets", "reps"):
                if _number(ex, key, int, required=True) <= 0:
                    raise ValidationError(f"Exercise '{key}' must be positive")

        db = get_db()
        cur = db.execute(
            "INSERT INTO workouts (client_id, date, workout_type, duration_min, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (client_id, data.get("date") or date.today().isoformat(), workout_type,
             duration, data.get("notes", "")),
        )
        for ex in exercises:
            db.execute("INSERT INTO exercises (workout_id, name, sets, reps, weight) "
                       "VALUES (?, ?, ?, ?, ?)",
                       (cur.lastrowid, ex["name"], int(ex["sets"]), int(ex["reps"]),
                        float(ex.get("weight", 0))))
        db.commit()
        return jsonify(id=cur.lastrowid, client_id=client_id, workout_type=workout_type,
                       duration_min=duration,
                       total_volume=fitness.total_training_volume(exercises)), 201

    @app.get("/api/clients/<int:client_id>/workouts")
    def list_workouts(client_id: int):
        _client_or_404(client_id)
        db = get_db()
        workouts = []
        for w in db.execute("SELECT * FROM workouts WHERE client_id = ? ORDER BY date DESC",
                            (client_id,)):
            item = dict(w)
            item["exercises"] = [dict(e) for e in db.execute(
                "SELECT name, sets, reps, weight FROM exercises WHERE workout_id = ?",
                (w["id"],))]
            workouts.append(item)
        return jsonify(workouts)

    # ---------- Body metrics ----------
    @app.post("/api/clients/<int:client_id>/metrics")
    def add_metrics(client_id: int):
        _client_or_404(client_id)
        data = _json_body()
        values = {k: _number(data, k) for k in ("weight", "waist", "bodyfat")}
        if all(v is None for v in values.values()):
            raise ValidationError("Provide at least one of weight, waist, bodyfat")
        db = get_db()
        db.execute("INSERT INTO metrics (client_id, date, weight, waist, bodyfat) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (client_id, data.get("date") or date.today().isoformat(),
                    values["weight"], values["waist"], values["bodyfat"]))
        db.commit()
        return jsonify(client_id=client_id, **values), 201

    @app.get("/api/clients/<int:client_id>/metrics")
    def list_metrics(client_id: int):
        _client_or_404(client_id)
        rows = get_db().execute("SELECT date, weight, waist, bodyfat FROM metrics "
                                "WHERE client_id = ? ORDER BY date", (client_id,)).fetchall()
        return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
