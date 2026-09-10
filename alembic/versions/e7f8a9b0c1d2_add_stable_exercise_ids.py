"""add stable exercise ids

Revision ID: e7f8a9b0c1d2
Revises: 8bcc257c3529
Create Date: 2026-09-10

"""

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "8bcc257c3529"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _crosswalk() -> list[dict[str, str | None]]:
    path = Path(__file__).resolve().parents[2] / "src/mycoach/data/exercise_crosswalk.json"
    return json.loads(path.read_text())["entries"]


def upgrade() -> None:
    with op.batch_alter_table("gym_workout_details", schema=None) as batch_op:
        batch_op.add_column(sa.Column("exercise_id", sa.String(length=200), nullable=True))
        batch_op.create_index("ix_gym_workout_details_exercise_id", ["exercise_id"])

    with op.batch_alter_table("routine_exercises", schema=None) as batch_op:
        batch_op.add_column(sa.Column("exercise_id", sa.String(length=200), nullable=True))
        batch_op.create_index("ix_routine_exercises_exercise_id", ["exercise_id"])

    connection = op.get_bind()
    for entry in _crosswalk():
        exercise_id = entry["exercise_id"]
        if exercise_id is None:
            continue
        connection.execute(
            sa.text(
                "UPDATE gym_workout_details SET exercise_id = :exercise_id "
                "WHERE exercise_title = :exercise_title"
            ),
            {"exercise_id": exercise_id, "exercise_title": entry["exercise_title"]},
        )
        connection.execute(
            sa.text(
                "UPDATE routine_exercises SET exercise_id = :exercise_id "
                "WHERE exercise_name = :exercise_title"
            ),
            {"exercise_id": exercise_id, "exercise_title": entry["exercise_title"]},
        )


def downgrade() -> None:
    with op.batch_alter_table("routine_exercises", schema=None) as batch_op:
        batch_op.drop_index("ix_routine_exercises_exercise_id")
        batch_op.drop_column("exercise_id")

    with op.batch_alter_table("gym_workout_details", schema=None) as batch_op:
        batch_op.drop_index("ix_gym_workout_details_exercise_id")
        batch_op.drop_column("exercise_id")
