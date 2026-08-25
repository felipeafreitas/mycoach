"""Tests for scheduler configuration and job registration."""

from mycoach.config import Settings
from mycoach.scheduler.scheduler import create_scheduler


def test_create_scheduler_registers_all_jobs() -> None:
    """Scheduler should register all coaching-pipeline jobs.

    Gym workouts arrive via CSV import / the offline logger push endpoint, so
    there is no scheduled gym-sync job.
    """
    settings = Settings(
        scheduler_timezone="UTC",
        scheduler_sync_hour=6,
        scheduler_sync_minute=0,
        scheduler_briefing_hour=6,
        scheduler_briefing_minute=30,
        scheduler_post_workout_hour=7,
        scheduler_post_workout_minute=0,
        scheduler_weekly_plan_day="sun",
        scheduler_weekly_plan_hour=18,
    )
    scheduler = create_scheduler(settings)

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {
        "garmin_sync",
        "daily_briefing",
        "post_workout_analysis",
        "weekly_plan",
        "weekly_recap",
    }


def test_create_scheduler_uses_configured_timezone() -> None:
    """Scheduler should use the timezone from settings."""
    settings = Settings(scheduler_timezone="America/New_York")
    scheduler = create_scheduler(settings)
    assert str(scheduler.timezone) == "America/New_York"


def test_create_scheduler_default_timezone() -> None:
    """Scheduler should default to Europe/London."""
    settings = Settings()
    scheduler = create_scheduler(settings)
    assert str(scheduler.timezone) == "Europe/London"


def test_weekly_plan_day_configurable() -> None:
    """Weekly plan job should respect the configured day."""
    settings = Settings(scheduler_weekly_plan_day="sat", scheduler_weekly_plan_hour=20)
    scheduler = create_scheduler(settings)
    plan_job = scheduler.get_job("weekly_plan")
    assert plan_job is not None
    trigger_str = str(plan_job.trigger)
    assert "sat" in trigger_str


def test_weekly_plan_minute_configurable() -> None:
    """Weekly plan job should respect the configured minute."""
    settings = Settings(scheduler_weekly_plan_minute=30)
    scheduler = create_scheduler(settings)
    plan_job = scheduler.get_job("weekly_plan")
    assert plan_job is not None
    assert "minute='30'" in str(plan_job.trigger)


def test_weekly_recap_day_configurable() -> None:
    """Weekly recap job should respect the configured day."""
    settings = Settings(scheduler_weekly_recap_day="sun")
    scheduler = create_scheduler(settings)
    recap_job = scheduler.get_job("weekly_recap")
    assert recap_job is not None
    assert "sun" in str(recap_job.trigger)


def test_weekly_recap_time_configurable() -> None:
    """Weekly recap job should respect the configured hour and minute."""
    settings = Settings(scheduler_weekly_recap_hour=9, scheduler_weekly_recap_minute=15)
    scheduler = create_scheduler(settings)
    recap_job = scheduler.get_job("weekly_recap")
    assert recap_job is not None
    trigger_str = str(recap_job.trigger)
    assert "hour='9'" in trigger_str
    assert "minute='15'" in trigger_str


def test_scheduler_not_started() -> None:
    """create_scheduler should not start the scheduler automatically."""
    settings = Settings()
    scheduler = create_scheduler(settings)
    assert not scheduler.running


def test_daily_briefing_is_registered_as_a_poll_not_a_single_shot() -> None:
    """One 09:30 attempt loses roughly one briefing in five to upload timing alone."""
    settings = Settings(scheduler_briefing_hour=9, scheduler_briefing_minute=30)
    job = create_scheduler(settings).get_job("daily_briefing")

    assert job is not None
    trigger = str(job.trigger)
    assert "*/15" in trigger
    assert "9-20" in trigger


def test_daily_briefing_poll_does_not_replay_stale_ticks() -> None:
    """A poll missed while the container was down is replaced, not queued up."""
    job = create_scheduler(Settings()).get_job("daily_briefing")

    assert job is not None
    assert job.coalesce is True
    assert job.max_instances == 1
    assert job.misfire_grace_time == 300


def test_rejects_a_briefing_hour_that_could_never_generate() -> None:
    """Between the two cutoffs the trigger is valid but never generates anything.

    A silent no-op is the exact class of failure the retry window exists to
    remove, so it fails loudly at startup instead — naming the setting.
    """
    import pytest

    with pytest.raises(ValueError, match="MYCOACH_SCHEDULER_BRIEFING_HOUR=14"):
        create_scheduler(Settings(scheduler_briefing_hour=14))


def test_rejects_a_briefing_hour_past_the_evaluation_cutoff() -> None:
    """APScheduler's own error here is an opaque note about ranges."""
    import pytest

    with pytest.raises(ValueError, match="could ever be generated"):
        create_scheduler(Settings(scheduler_briefing_hour=21))


def test_a_late_but_workable_briefing_hour_still_builds_a_trigger() -> None:
    job = create_scheduler(Settings(scheduler_briefing_hour=13)).get_job("daily_briefing")
    assert job is not None
    assert "13-20" in str(job.trigger)
