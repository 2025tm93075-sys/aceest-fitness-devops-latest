"""Unit tests for the pure business logic in aceest.fitness."""

import random
from datetime import date

import pytest

from aceest import fitness
from aceest.fitness import ValidationError


# ---------- Program catalogue ----------
def test_all_programs_have_required_fields():
    for pid, prog in fitness.PROGRAMS.items():
        for key in ("name", "calorie_factor", "workout", "diet", "description"):
            assert key in prog, f"{pid} missing {key}"
        assert prog["calorie_factor"] > 0
        assert prog["workout"] and prog["diet"]


def test_get_program_unknown_raises():
    with pytest.raises(ValidationError):
        fitness.get_program("does-not-exist")


# ---------- Calories ----------
@pytest.mark.parametrize("program_id, weight, expected", [
    ("fat-loss-3day", 80, 1760),     # 80 x 22
    ("fat-loss-5day", 80, 1920),     # 80 x 24
    ("muscle-gain-ppl", 70, 2450),   # 70 x 35
    ("beginner", 65.5, 1703),        # int(65.5 x 26)
])
def test_calculate_calories(program_id, weight, expected):
    assert fitness.calculate_calories(weight, program_id) == expected


@pytest.mark.parametrize("weight", [0, -5, None])
def test_calculate_calories_rejects_bad_weight(weight):
    with pytest.raises(ValidationError):
        fitness.calculate_calories(weight, "beginner")


# ---------- BMI ----------
def test_calculate_bmi():
    assert fitness.calculate_bmi(70, 175) == 22.9


@pytest.mark.parametrize("weight, height", [(0, 170), (70, 0), (-1, 170), (70, None)])
def test_calculate_bmi_rejects_bad_input(weight, height):
    with pytest.raises(ValidationError):
        fitness.calculate_bmi(weight, height)


@pytest.mark.parametrize("bmi, category", [
    (17.0, "Underweight"), (18.5, "Normal"), (24.9, "Normal"),
    (25.0, "Overweight"), (29.9, "Overweight"), (30.0, "Obese"), (42.0, "Obese"),
])
def test_bmi_category_boundaries(bmi, category):
    result = fitness.bmi_category(bmi)
    assert result["category"] == category
    assert result["risk"]


# ---------- Adherence ----------
@pytest.mark.parametrize("value", [0, 50, 100, "75"])
def test_validate_adherence_ok(value):
    assert fitness.validate_adherence(value) == int(value)


@pytest.mark.parametrize("value", [-1, 101, "abc", None])
def test_validate_adherence_rejects(value):
    with pytest.raises(ValidationError):
        fitness.validate_adherence(value)


def test_adherence_summary_empty():
    assert fitness.adherence_summary([]) == {
        "weeks": 0, "average": None, "best": None, "latest": None}


def test_adherence_summary_values():
    assert fitness.adherence_summary([60, 80, 70]) == {
        "weeks": 3, "average": 70.0, "best": 80, "latest": 70}


# ---------- Membership ----------
TODAY = date(2026, 10, 10)


@pytest.mark.parametrize("end, status, days", [
    ("2026-12-31", "Active", 82),
    ("2026-10-15", "Expiring Soon", 5),
    ("2026-10-10", "Expiring Soon", 0),
    ("2026-10-01", "Expired", -9),
])
def test_membership_status(end, status, days):
    assert fitness.membership_status(end, today=TODAY) == {
        "status": status, "days_remaining": days}


def test_membership_status_none():
    assert fitness.membership_status(None)["status"] == "No Membership"


def test_membership_status_bad_format():
    with pytest.raises(ValidationError):
        fitness.membership_status("31/12/2026")


# ---------- Program generator ----------
def test_generate_program_is_valid_and_seedable():
    a = fitness.generate_program(random.Random(42))
    b = fitness.generate_program(random.Random(42))
    assert a == b
    assert a["program"] in fitness.PROGRAM_TEMPLATES[a["goal"]]


def test_generate_program_respects_goal():
    result = fitness.generate_program(random.Random(1), goal="Beginner")
    assert result["goal"] == "Beginner"
    assert result["program"] in fitness.PROGRAM_TEMPLATES["Beginner"]


def test_generate_program_unknown_goal():
    with pytest.raises(ValidationError):
        fitness.generate_program(goal="Powerlifting")


# ---------- Training volume ----------
def test_total_training_volume():
    exercises = [{"sets": 5, "reps": 5, "weight": 100},
                 {"sets": 3, "reps": 10, "weight": 20.5}]
    assert fitness.total_training_volume(exercises) == 2500 + 615


def test_total_training_volume_empty():
    assert fitness.total_training_volume([]) == 0.0
