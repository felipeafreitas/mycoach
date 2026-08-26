"""APScheduler setup — configures and manages the background scheduler.

The scheduler runs five jobs as part of the daily coaching pipeline:
1. Garmin sync (default 6:00 AM) — fetch health + activity data
2. Daily briefing (default from 9:30 AM) — a poll, not a single shot. Every
   15 minutes it syncs Garmin and, if the data has arrived, generates the
   briefing; it stops generating at 14:00 and stops watching at 20:00. The
   standalone 6:00 AM sync runs before Garmin has finalised the night's sleep,
   so the briefing cannot rely on it, and the watch's own upload can land hours
   later still — hence a window rather than a moment.
3. Post-workout analysis (default 7:00 AM) — analyze new activities after sync
4. Weekly plan (default Sunday 6:00 PM) — generate next week's training plan
5. Weekly recap (default Monday 7:00 AM) — recap the previous week

Gym workouts arrive via Hevy CSV import or the offline companion logger
(POST /api/sources/import/workouts), not a scheduled sync.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from mycoach.config import Settings
from mycoach.scheduler.briefing_window import (
    EVALUATE_CUTOFF,
    GENERATE_CUTOFF,
    POLL_INTERVAL_MINUTES,
)
from mycoach.scheduler.jobs import (
    job_daily_briefing_poll,
    job_garmin_sync,
    job_post_workout_analysis,
    job_weekly_plan,
    job_weekly_recap,
)

logger = logging.getLogger(__name__)

# Day name → APScheduler day-of-week string
DAY_MAP = {
    "mon": "mon",
    "tue": "tue",
    "wed": "wed",
    "thu": "thu",
    "fri": "fri",
    "sat": "sat",
    "sun": "sun",
}


def create_scheduler(settings: Settings) -> BackgroundScheduler:
    """Create and configure the background scheduler with all coaching pipeline jobs.

    Jobs are not started — call scheduler.start() to begin execution.
    """
    # Checked before a single job is added, because both failure modes without
    # it are worse than a startup error. An hour past the evaluation cutoff
    # makes APScheduler's own range validation raise something opaque about
    # minimums and maximums; an hour between the two cutoffs builds a perfectly
    # valid trigger that then silently never generates anything, which is the
    # class of silent failure this whole change exists to remove.
    if settings.scheduler_briefing_hour >= GENERATE_CUTOFF.hour:
        raise ValueError(
            f"MYCOACH_SCHEDULER_BRIEFING_HOUR={settings.scheduler_briefing_hour} is "
            f"at or after the {GENERATE_CUTOFF:%H:%M} briefing generation cutoff, so "
            f"no briefing could ever be generated. Set it earlier."
        )

    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    # 1. Garmin sync — daily (fetches health + activities, then auto-merges)
    scheduler.add_job(
        job_garmin_sync,
        "cron",
        id="garmin_sync",
        hour=settings.scheduler_sync_hour,
        minute=settings.scheduler_sync_minute,
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # 2. Daily briefing — polled across a window; syncs Garmin itself each tick.
    #
    # The trigger is deliberately dumber than the behaviour: it fires on every
    # quarter hour from the briefing hour to the evaluation cutoff, and each
    # tick asks ``briefing_window`` whether there is anything to do. Putting the
    # window's real bounds (opens at the configured minute, stops generating at
    # 14:00, one alert per day) in the trigger would split the rules across a
    # cron expression and a decision function, and only one of those two can be
    # read off ``job_runs`` after the fact.
    #
    # A short grace time with coalescing, rather than the hour the once-a-day
    # jobs use: a poll missed while the container was down should be replaced by
    # the next one, not replayed as a burst of stale ticks.
    scheduler.add_job(
        job_daily_briefing_poll,
        "cron",
        id="daily_briefing",
        hour=f"{settings.scheduler_briefing_hour}-{EVALUATE_CUTOFF.hour}",
        minute=f"*/{POLL_INTERVAL_MINUTES}",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )

    # 3. Post-workout analysis — daily, after briefing (analyzes new activities)
    scheduler.add_job(
        job_post_workout_analysis,
        "cron",
        id="post_workout_analysis",
        hour=settings.scheduler_post_workout_hour,
        minute=settings.scheduler_post_workout_minute,
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # 4. Weekly plan — once per week (default Sunday evening)
    plan_day = DAY_MAP.get(settings.scheduler_weekly_plan_day.lower(), "sun")
    scheduler.add_job(
        job_weekly_plan,
        "cron",
        id="weekly_plan",
        day_of_week=plan_day,
        hour=settings.scheduler_weekly_plan_hour,
        minute=settings.scheduler_weekly_plan_minute,
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # 5. Weekly recap — once per week (default Monday morning, after the week ends)
    recap_day = DAY_MAP.get(settings.scheduler_weekly_recap_day.lower(), "mon")
    scheduler.add_job(
        job_weekly_recap,
        "cron",
        id="weekly_recap",
        day_of_week=recap_day,
        hour=settings.scheduler_weekly_recap_hour,
        minute=settings.scheduler_weekly_recap_minute,
        misfire_grace_time=3600,
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: sync=%02d:%02d, briefing polls %02d:%02d-%02d:00/%dm, "
        "post_workout=%02d:%02d, plan=%s@%02d:%02d, recap=%s@%02d:%02d, tz=%s",
        settings.scheduler_sync_hour,
        settings.scheduler_sync_minute,
        settings.scheduler_briefing_hour,
        settings.scheduler_briefing_minute,
        EVALUATE_CUTOFF.hour,
        POLL_INTERVAL_MINUTES,
        settings.scheduler_post_workout_hour,
        settings.scheduler_post_workout_minute,
        plan_day,
        settings.scheduler_weekly_plan_hour,
        settings.scheduler_weekly_plan_minute,
        recap_day,
        settings.scheduler_weekly_recap_hour,
        settings.scheduler_weekly_recap_minute,
        settings.scheduler_timezone,
    )

    return scheduler
