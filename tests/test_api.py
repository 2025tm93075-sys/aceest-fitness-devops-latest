"""Integration tests for the Flask HTTP API and web pages."""

import pytest

from aceest import __version__


# ---------- Ops endpoints ----------
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "version": __version__}


def test_version(client):
    assert client.get("/api/version").get_json()["version"] == __version__


def test_unknown_api_route_returns_json_404(client):
    resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


# ---------- Programs ----------
def test_list_programs(client):
    data = client.get("/api/programs").get_json()
    ids = {p["id"] for p in data}
    assert {"fat-loss-3day", "fat-loss-5day", "muscle-gain-ppl", "beginner"} <= ids


def test_get_program(client):
    resp = client.get("/api/programs/beginner")
    assert resp.status_code == 200
    assert resp.get_json()["calorie_factor"] == 26


def test_get_program_404(client):
    assert client.get("/api/programs/unknown").status_code == 404


# ---------- Calculators ----------
def test_calc_calories(client):
    resp = client.post("/api/calculate/calories",
                       json={"weight": 70, "program": "muscle-gain-ppl"})
    assert resp.status_code == 200
    assert resp.get_json()["calories"] == 2450


@pytest.mark.parametrize("payload", [
    {"program": "beginner"},
    {"weight": 70},
    {"weight": "heavy", "program": "beginner"},
    {"weight": 70, "program": "unknown"},
])
def test_calc_calories_validation(client, payload):
    assert client.post("/api/calculate/calories", json=payload).status_code == 400


def test_calc_calories_requires_json(client):
    resp = client.post("/api/calculate/calories", data="not json",
                       content_type="text/plain")
    assert resp.status_code == 400


def test_calc_bmi(client):
    data = client.post("/api/calculate/bmi", json={"weight": 70, "height": 175}).get_json()
    assert data == {"bmi": 22.9, "category": "Normal",
                    "risk": "Low risk if active and strong."}


def test_calc_bmi_validation(client):
    assert client.post("/api/calculate/bmi", json={"weight": 70}).status_code == 400


# ---------- Auth ----------
def test_login_success(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "s3cret"})
    assert resp.status_code == 200
    assert resp.get_json()["role"] == "Admin"


@pytest.mark.parametrize("creds", [
    {"username": "admin", "password": "wrong"},
    {"username": "ghost", "password": "s3cret"},
    {},
])
def test_login_failure(client, creds):
    assert client.post("/api/auth/login", json=creds).status_code == 401


def test_password_is_hashed(app):
    import sqlite3
    conn = sqlite3.connect(app.config["DATABASE"])
    stored = conn.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
    conn.close()
    assert stored != "s3cret"


# ---------- Client CRUD ----------
def test_create_client_computes_calories(sample_client):
    assert sample_client["id"] == 1
    assert sample_client["calories"] == 80 * 22


def test_create_client_requires_name(client):
    assert client.post("/api/clients", json={"age": 30}).status_code == 400


@pytest.mark.parametrize("payload", [
    {"name": "X", "weight": -1},
    {"name": "X", "age": "old"},
    {"name": "X", "program": "yoga"},
    {"name": "X", "membership_end": "tomorrow"},
    {"name": "X", "target_adherence": 150},
])
def test_create_client_validation(client, payload):
    assert client.post("/api/clients", json=payload).status_code == 400


def test_duplicate_client_conflict(client, sample_client):
    resp = client.post("/api/clients", json={"name": sample_client["name"]})
    assert resp.status_code == 409


def test_list_and_get_client(client, sample_client):
    assert len(client.get("/api/clients").get_json()) == 1
    assert client.get("/api/clients/1").get_json()["name"] == "Arjun"
    assert client.get("/api/clients/999").status_code == 404


def test_update_client_recalculates_calories(client, sample_client):
    resp = client.put("/api/clients/1", json={"program": "muscle-gain-ppl", "weight": 82})
    assert resp.status_code == 200
    assert resp.get_json()["calories"] == 82 * 35


def test_update_client_empty_payload(client, sample_client):
    assert client.put("/api/clients/1", json={}).status_code == 400


def test_update_missing_client(client):
    assert client.put("/api/clients/5", json={"age": 20}).status_code == 404


def test_delete_client_cascades(client, sample_client):
    client.post("/api/clients/1/progress", json={"adherence": 80})
    assert client.delete("/api/clients/1").status_code == 204
    assert client.get("/api/clients/1").status_code == 404
    assert client.delete("/api/clients/1").status_code == 404


# ---------- Progress ----------
def test_progress_flow(client, sample_client):
    for week, value in (("W1", 60), ("W2", 90)):
        assert client.post("/api/clients/1/progress",
                           json={"week": week, "adherence": value}).status_code == 201
    rows = client.get("/api/clients/1/progress").get_json()
    assert rows == [{"week": "W1", "adherence": 60}, {"week": "W2", "adherence": 90}]


def test_progress_default_week(client, sample_client):
    data = client.post("/api/clients/1/progress", json={"adherence": 70}).get_json()
    assert data["week"].startswith("Week ")


def test_progress_validation(client, sample_client):
    assert client.post("/api/clients/1/progress", json={"adherence": 120}).status_code == 400
    assert client.post("/api/clients/9/progress", json={"adherence": 50}).status_code == 404


# ---------- Workouts ----------
def test_workout_with_exercises(client, sample_client):
    resp = client.post("/api/clients/1/workouts", json={
        "date": "2026-10-01", "workout_type": "Strength", "duration_min": 60,
        "notes": "Felt strong",
        "exercises": [{"name": "Squat", "sets": 5, "reps": 5, "weight": 100}],
    })
    assert resp.status_code == 201
    assert resp.get_json()["total_volume"] == 2500.0

    listed = client.get("/api/clients/1/workouts").get_json()
    assert listed[0]["exercises"][0]["name"] == "Squat"


@pytest.mark.parametrize("payload", [
    {"workout_type": "Zumba", "duration_min": 30},
    {"workout_type": "Cardio"},
    {"workout_type": "Cardio", "duration_min": 0},
    {"workout_type": "Cardio", "duration_min": 30, "exercises": [{"sets": 3, "reps": 5}]},
    {"workout_type": "Cardio", "duration_min": 30,
     "exercises": [{"name": "Row", "sets": 0, "reps": 5}]},
])
def test_workout_validation(client, sample_client, payload):
    assert client.post("/api/clients/1/workouts", json=payload).status_code == 400


# ---------- Metrics ----------
def test_metrics_flow(client, sample_client):
    resp = client.post("/api/clients/1/metrics",
                       json={"date": "2026-10-01", "weight": 79.5, "waist": 84})
    assert resp.status_code == 201
    rows = client.get("/api/clients/1/metrics").get_json()
    assert rows[0]["weight"] == 79.5 and rows[0]["bodyfat"] is None


def test_metrics_requires_a_value(client, sample_client):
    assert client.post("/api/clients/1/metrics", json={"date": "2026-10-01"}).status_code == 400


# ---------- Summary & generator ----------
def test_summary(client, sample_client):
    client.post("/api/clients/1/progress", json={"adherence": 80})
    client.post("/api/clients/1/progress", json={"adherence": 90})
    data = client.get("/api/clients/1/summary").get_json()
    assert data["bmi"]["value"] == 24.7
    assert data["bmi"]["category"] == "Normal"
    assert data["adherence"]["average"] == 85.0
    assert data["membership"]["status"] == "Active"
    assert data["workouts_logged"] == 0


def test_summary_without_body_stats(client):
    client.post("/api/clients", json={"name": "NoStats"})
    data = client.get("/api/clients/1/summary").get_json()
    assert data["bmi"] is None
    assert data["membership"]["status"] == "No Membership"


def test_generate_program_endpoint(client, sample_client):
    resp = client.post("/api/clients/1/generate-program", json={"goal": "Muscle Gain"})
    assert resp.status_code == 200
    assert resp.get_json()["goal"] == "Muscle Gain"
    assert client.post("/api/clients/1/generate-program",
                       json={"goal": "Nope"}).status_code == 400


# ---------- HTML pages ----------
def test_index_page(client, sample_client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "ACEest" in body and "Arjun" in body and "Muscle Gain (MG) - PPL" in body


def test_client_page(client, sample_client):
    client.post("/api/clients/1/progress", json={"week": "W1", "adherence": 75})
    body = client.get("/clients/1").get_data(as_text=True)
    assert "Arjun" in body and "75%" in body


def test_client_page_404(client):
    assert client.get("/clients/42").status_code == 404


def test_form_create_client(client):
    resp = client.post("/clients", data={"name": "Meera", "weight": "60",
                                         "program": "beginner"})
    assert resp.status_code == 302
    assert client.get("/api/clients/1").get_json()["calories"] == 60 * 26


def test_form_create_client_errors(client):
    resp = client.post("/clients", data={"name": ""}, follow_redirects=True)
    assert "required" in resp.get_data(as_text=True)
    client.post("/clients", data={"name": "Meera"})
    resp = client.post("/clients", data={"name": "Meera"}, follow_redirects=True)
    assert "already exists" in resp.get_data(as_text=True)
