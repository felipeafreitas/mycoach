"""Tests for the stable exercise identity migration."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command

REPO_ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_REVISION = "8bcc257c3529"


def _alembic_config(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("MYCOACH_DB_URL", f"sqlite+aiosqlite:///{db_path}")
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


def _seed_existing_exercises(db_path: Path) -> None:
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users "
            "(id, name, email, fitness_level, created_at, updated_at, "
            "email_daily_briefing, email_weekly_plan, email_post_workout, "
            "email_sleep_coaching, email_weekly_recap) "
            "VALUES (1, 'A', 'a@b.com', 'intermediate', ?, ?, 0, 0, 0, 0, 0)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO activities "
            "(id, user_id, sport, title, start_time, data_source, created_at) "
            "VALUES (1, 1, 'gym', 'Legs', ?, 'hevy', ?)",
            (now, now),
        )
        conn.executemany(
            "INSERT INTO gym_workout_details "
            "(activity_id, exercise_title, set_index, set_type) VALUES (1, ?, ?, 'normal')",
            [
                ("Squat (Barbell)", 1),
                ("Bulgarian. Split Squat", 2),
                ("Unlisted Machine", 3),
            ],
        )
        conn.execute(
            "INSERT INTO workout_routines "
            "(id, user_id, name, is_active, created_at, updated_at) "
            "VALUES (1, 1, 'Legs', 1, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO routine_days (id, routine_id, name, day_of_week, order_index) "
            "VALUES (1, 1, 'Legs', NULL, 0)"
        )
        conn.executemany(
            "INSERT INTO routine_exercises "
            "(routine_day_id, exercise_name, sets, rep_range, order_index) "
            "VALUES (1, ?, 3, '8-10', ?)",
            [("Squat (Barbell)", 0), ("Unlisted Machine", 1)],
        )
        conn.commit()
    finally:
        conn.close()


def test_upgrade_adds_and_backfills_stable_exercise_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "exercise-identity.db"
    cfg = _alembic_config(db_path, monkeypatch)
    command.upgrade(cfg, PREVIOUS_REVISION)
    _seed_existing_exercises(db_path)

    command.upgrade(cfg, "head")

    conn = sqlite3.connect(db_path)
    try:
        detail_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(gym_workout_details)").fetchall()
        }
        routine_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(routine_exercises)").fetchall()
        }
        details = conn.execute(
            "SELECT exercise_title, exercise_id FROM gym_workout_details ORDER BY set_index"
        ).fetchall()
        routines = conn.execute(
            "SELECT exercise_name, exercise_id FROM routine_exercises ORDER BY order_index"
        ).fetchall()
    finally:
        conn.close()

    assert "exercise_id" in detail_columns
    assert "exercise_id" in routine_columns
    assert details == [
        ("Squat (Barbell)", "Barbell_Squat"),
        ("Bulgarian. Split Squat", "mycoach:bulgarian-split-squat"),
        ("Unlisted Machine", None),
    ]
    assert routines == [
        ("Squat (Barbell)", "Barbell_Squat"),
        ("Unlisted Machine", None),
    ]
