# Spec: Daily briefing reads stale/empty health data

**Status:** Agreed 2026-08-16
**Reported by:** Felipe (prompt logs for 13/08, 14/08, 15/08 briefings)

## Symptom

The `daily_briefing` prompt's `## Today's Health Data` section reads
`No health data available for today.` (14/08, 15/08) or contains only a thin
subset — resting HR, max HR, stress, SpO2, with no sleep, HRV, or Body Battery
(13/08). The briefing's entire purpose is to assess last night's sleep and
recovery, so it was producing verdicts from nothing.

## Diagnosis (evidence-backed)

Evidence gathered from the production container on the homelab
(`docker exec mycoach`, SQLite at `/data/mycoach.db`) on 2026-08-15.

### Root cause: the sync asks Garmin before Garmin has the answer

`garmin_sync` fires at 06:00 Europe/London (05:00 UTC). At that hour the user is
asleep and the watch has not pushed the night to Garmin Connect. Garmin answers
with an *all-null skeleton* — a ~6 KB JSON document with `calendarDate` set and
every metric `null`. That skeleton is mapped to an all-NULL snapshot row and
written to the DB.

The briefing then runs at 09:30 and reads that row. **Nothing re-syncs between
06:00 and 09:30** (`scheduler/scheduler.py:48-66`), so the briefing is
structurally incapable of seeing the night it exists to assess.

Proof — the 13/08 row was partial in its own 08:30 briefing but is complete in
the DB today (sleep score 80, HRV 73, Body Battery 92). The data existed; the
briefing never saw it, because it only arrived with the *next* day's sync via
`import_health_snapshot`'s null-filling (`sources/garmin/mappers.py:390-393`).

### Compounding cause: a 2-day lookback that closes the window

`_garmin_sync` (`scheduler/jobs.py:215-216`) fetches only `today-2 … today`.
The 14/08 data uploaded to Garmin at some point during the 15th — 18+ hours
after the 15/08 05:00 sync had already asked and been told "nothing". After
2026-08-16's run, 14/08 would have fallen permanently outside the window despite
`import_health_snapshot` being perfectly able to fill it.

Confirmed by experiment: a manual sync at 23:50 on 15/08 turned both empty days
into full ones.

| Date | `raw_data` before | after | sleep/HRV/BB after |
|---|---|---|---|
| 14/08 | 6,290 B (null skeleton) | 268,857 B | populated |
| 15/08 | 5,883 B (null skeleton) | 227,544 B | populated |

Note that the manual sync endpoint (`api/routes/sources.py:134`) already
defaults to **7** days — the scheduler's 2 is the outlier.

### Why it went unnoticed for days

Three independent silences:

1. `_safe_call` (`sources/garmin/source.py:157-162`) swallows every exception
   into `None`. A dead API and a dataless day produce identical rows.
2. `field_status` (`sources/garmin/source.py:121-132`) is an
   `isinstance(x, dict)` **type** check. The 6 KB all-null skeleton scored
   `'sleep': True, 'hrv': True`. The logged flags were byte-identical on 10/08
   (rich data) and 14/08 (empty) — the instrumentation actively misled the
   investigation.
3. `has_data = any(field_status.values())` therefore never fired, so
   `empty_health_days` stayed empty, `job_runs.error` stayed blank, and every
   run reported `success`. Two days of data loss produced zero signal.

### Explicitly not a cause

- Not Garmin auth — `garmin_sync` succeeded every day 12–15/08.
- Not a dead scheduler — container up 8 days healthy, all 5 jobs registered.
- Not a device/watch fault — the data was in Garmin Connect all along.
- Not a timezone bug — cron `hour=6` Europe/London = 05:00 UTC, as observed.

## Decisions

| # | Decision | Chosen |
|---|---|---|
| Q4/Q9 | How the briefing gets fresh data | **Briefing syncs immediately before generating, AND the lookback widens to 7 days.** Both are needed: a pre-briefing sync alone would still have missed 14/08 (that upload landed later on the 15th); only the wider window recovers it. |
| Q7 | Behaviour when the fresh sync genuinely returns nothing | **Skip the briefing**, recording `job_runs.status='skipped'` with a reason. Fabricated recovery advice from absent data is worse than no briefing. |
| — | Where the no-data guard lives | **In the job (`_daily_briefing`), not the engine.** The decision is "we just synced and Garmin gave nothing", which is job-level knowledge. Keeps the manual API route usable for ad-hoc generation and avoids disturbing three existing engine tests that deliberately run without health rows. |

## Requirements

- R1. `_daily_briefing` runs a Garmin sync before calling the coaching engine.
- R2. The scheduler's sync lookback is 7 days, configurable.
- R3. `has_data` is decided by snapshot **content**, not response **type**.
- R4. A day with no usable content is reported: `ImportResult` carries the empty
      days as structured data, not only as a formatted error string.
- R5. An exception from a Garmin call is distinguishable from an empty response,
      and is surfaced in `ImportResult.errors`.
- R6. When the post-sync snapshot for today has no usable content, the briefing
      raises `PipelineSkip` with a reason naming the date.
- R7. A sync failure inside the briefing job must not prevent a briefing when
      usable data is already in the DB.

## Out of scope (backlog)

- User-facing staleness alert ("no Garmin data in N days"). Agreed valuable,
  deferred.
- Additional sync runs per day (e.g. an evening sync).
