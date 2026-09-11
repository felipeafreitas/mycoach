"""Companion-logger API — data the offline logger PWA needs (API-key guarded)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mycoach.api.deps import require_api_key
from mycoach.database import get_db
from mycoach.exercise_catalogue import load_exercise_catalogue
from mycoach.models.routine import RoutineDay, WorkoutRoutine
from mycoach.schemas.routine import WorkoutRoutineRead

router = APIRouter(prefix="/api/logger", tags=["logger"])

# MVP: single user, id=1
DEFAULT_USER_ID = 1


class ExerciseListItem(BaseModel):
    id: str
    name: str


class ExerciseListResponse(BaseModel):
    exercises: list[ExerciseListItem]


@router.get(
    "/exercises",
    response_model=ExerciseListResponse,
    dependencies=[Depends(require_api_key)],
)
async def list_exercises(
    session: AsyncSession = Depends(get_db),
) -> ExerciseListResponse:
    """The stable exercise catalogue cached by the offline logger.

    The dependency is retained so this route shares the logger API's normal
    lifecycle even though the pinned catalogue itself is file-backed.
    """
    del session
    return ExerciseListResponse(
        exercises=[
            ExerciseListItem(id=exercise.id, name=exercise.name)
            for exercise in load_exercise_catalogue()
        ]
    )


@router.get(
    "/routines",
    response_model=WorkoutRoutineRead | None,
    dependencies=[Depends(require_api_key)],
)
async def get_active_routine(
    session: AsyncSession = Depends(get_db),
) -> WorkoutRoutine | None:
    """The user's active routine, with its days/exercises, for the logger to prefill.

    Returns null if the user has no active routine. Mirrors
    ``api/routes/routines.py::get_active_routine`` but sits under the
    API-key-guarded ``/api/logger`` surface the offline logger authenticates against.
    """
    stmt = (
        select(WorkoutRoutine)
        .where(WorkoutRoutine.user_id == DEFAULT_USER_ID, WorkoutRoutine.is_active.is_(True))
        .options(selectinload(WorkoutRoutine.days).selectinload(RoutineDay.exercises))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
