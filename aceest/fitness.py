"""
Core business logic for ACEest Fitness & Gym.

Everything in this module is pure Python (no Flask, no database) so it can be
unit-tested in isolation. The rules are consolidated from the legacy Tkinter
versions (v1.0 -> v3.2.4) that ship in ``legacy/``.
"""

from __future__ import annotations

import random
from datetime import date, datetime
from typing import Optional

# --------------------------------------------------------------------------- #
# Program catalogue (merged from v1.0 / v1.1 / v2.2.4 / v3.x)
# --------------------------------------------------------------------------- #
PROGRAMS: dict[str, dict] = {
    "fat-loss-3day": {
        "name": "Fat Loss (FL) - 3 day",
        "calorie_factor": 22,
        "description": "3-day full-body fat loss",
        "workout": [
            "Mon: 5x5 Back Squat + AMRAP",
            "Wed: Bench Press + 21-15-9",
            "Fri: 10RFT Deadlifts / Box Jumps",
        ],
        "diet": [
            "B: 3 Egg Whites + Oats Idli",
            "L: Grilled Chicken + Brown Rice",
            "D: Fish Curry + Millet Roti",
        ],
        "target_kcal": 2000,
    },
    "fat-loss-5day": {
        "name": "Fat Loss (FL) - 5 day",
        "calorie_factor": 24,
        "description": "5-day split, higher volume fat loss",
        "workout": [
            "Mon: 5x5 Back Squat + AMRAP",
            "Tue: EMOM 20min Assault Bike",
            "Wed: Bench Press + 21-15-9",
            "Thu: 10RFT Deadlifts / Box Jumps",
            "Fri: 30min Active Recovery",
        ],
        "diet": [
            "B: 3 Egg Whites + Oats Idli",
            "L: Grilled Chicken + Brown Rice",
            "D: Fish Curry + Millet Roti",
        ],
        "target_kcal": 2000,
    },
    "muscle-gain-ppl": {
        "name": "Muscle Gain (MG) - PPL",
        "calorie_factor": 35,
        "description": "Push/Pull/Legs hypertrophy",
        "workout": [
            "Mon: Squat 5x5",
            "Tue: Bench 5x5",
            "Wed: Deadlift 4x6",
            "Thu: Front Squat 4x8",
            "Fri: Incline Press 4x10",
            "Sat: Barbell Rows 4x10",
        ],
        "diet": [
            "B: 4 Eggs + PB Oats",
            "L: Chicken Biryani (250g Chicken)",
            "D: Mutton Curry + Jeera Rice",
        ],
        "target_kcal": 3200,
    },
    "beginner": {
        "name": "Beginner (BG)",
        "calorie_factor": 26,
        "description": "3-day simple beginner full-body",
        "workout": [
            "Circuit Training: Air Squats, Ring Rows, Push-ups",
            "Focus: Technique Mastery & Form (90% Threshold)",
        ],
        "diet": [
            "Balanced Tamil Meals: Idli-Sambar, Rice-Dal, Chapati",
            "Protein: 120g/day",
        ],
        "target_kcal": 2400,
    },
}

# Templates used by the "AI-style" program generator (v3.2.4)
PROGRAM_TEMPLATES: dict[str, list[str]] = {
    "Fat Loss": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    "Muscle Gain": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    "Beginner": ["Full Body 3x/week", "Light Strength + Mobility"],
}

WORKOUT_TYPES = ("Strength", "Hypertrophy", "Cardio", "Mobility")

# Gym site metrics shown on the v1.0 dashboard
SITE_METRICS = {"capacity_users": 150, "area_sq_ft": 10000, "break_even_members": 250}


class ValidationError(ValueError):
    """Raised when user input breaks a business rule."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_program(program_id: str) -> dict:
    """Return a program definition or raise ``ValidationError``."""
    if program_id not in PROGRAMS:
        raise ValidationError(f"Unknown program '{program_id}'")
    return PROGRAMS[program_id]


def calculate_calories(weight_kg: float, program_id: str) -> int:
    """Daily calorie target = body weight (kg) x program calorie factor."""
    if weight_kg is None or weight_kg <= 0:
        raise ValidationError("Weight must be a positive number")
    factor = get_program(program_id)["calorie_factor"]
    return int(weight_kg * factor)


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Body Mass Index rounded to one decimal place."""
    if weight_kg is None or weight_kg <= 0:
        raise ValidationError("Weight must be a positive number")
    if height_cm is None or height_cm <= 0:
        raise ValidationError("Height must be a positive number")
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def bmi_category(bmi: float) -> dict:
    """Map a BMI value to a WHO category and a short risk note."""
    if bmi < 18.5:
        return {"category": "Underweight",
                "risk": "Potential nutrient deficiency, low energy."}
    if bmi < 25:
        return {"category": "Normal",
                "risk": "Low risk if active and strong."}
    if bmi < 30:
        return {"category": "Overweight",
                "risk": "Moderate risk; focus on adherence and conditioning."}
    return {"category": "Obese",
            "risk": "Higher risk; prioritise fat loss, consistency, and supervision."}


def validate_adherence(value: int) -> int:
    """Adherence is a whole-number percentage between 0 and 100."""
    try:
        value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Adherence must be an integer") from exc
    if not 0 <= value <= 100:
        raise ValidationError("Adherence must be between 0 and 100")
    return value


def adherence_summary(values: list[int]) -> dict:
    """Average / best / latest weekly adherence for a client."""
    if not values:
        return {"weeks": 0, "average": None, "best": None, "latest": None}
    return {
        "weeks": len(values),
        "average": round(sum(values) / len(values), 1),
        "best": max(values),
        "latest": values[-1],
    }


def membership_status(end_date: Optional[str], today: Optional[date] = None) -> dict:
    """Return membership state and days remaining for an ISO ``YYYY-MM-DD`` date."""
    today = today or date.today()
    if not end_date:
        return {"status": "No Membership", "days_remaining": None}
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError("membership_end must be YYYY-MM-DD") from exc
    remaining = (end - today).days
    if remaining < 0:
        status = "Expired"
    elif remaining <= 7:
        status = "Expiring Soon"
    else:
        status = "Active"
    return {"status": status, "days_remaining": remaining}


def generate_program(rng: Optional[random.Random] = None, goal: Optional[str] = None) -> dict:
    """Pick a training split, optionally constrained to a goal (v3.2.4 feature)."""
    rng = rng or random.Random()
    if goal is not None and goal not in PROGRAM_TEMPLATES:
        raise ValidationError(f"Unknown goal '{goal}'")
    goal = goal or rng.choice(sorted(PROGRAM_TEMPLATES))
    return {"goal": goal, "program": rng.choice(PROGRAM_TEMPLATES[goal])}


def total_training_volume(exercises: list[dict]) -> float:
    """Sum of sets x reps x weight across a workout's exercises."""
    return float(sum(e.get("sets", 0) * e.get("reps", 0) * e.get("weight", 0.0)
                     for e in exercises))
