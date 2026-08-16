# Daily Briefing Fresh Health Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the daily briefing see the night it is assessing, and make a
dataless Garmin day loudly visible instead of silently fabricated.

**Architecture:** Four independent changes to the Garmin sync path and the
briefing job. (1) `has_data` becomes a check on the *mapped snapshot's content*
rather than the *HTTP response's type*, so Garmin's all-null skeleton is
correctly recognised as "no data". (2) `ImportResult` gains structured
`empty_health_days` and per-day API failure reporting, so callers can act on
emptiness programmatically instead of parsing error strings. (3) The scheduler's
sync lookback widens from 2 to 7 days (configurable), so late uploads are
recovered rather than falling off a cliff. (4) `_daily_briefing` syncs
immediately before generating and raises `PipelineSkip` when today still has no
usable data.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x async, APScheduler,
pytest + pytest-asyncio (`asyncio_mode = "auto"` — async tests need no
decorator), ruff (line-length 100), mypy (`disallow_untyped_defs = true`).

**Spec:** `docs/superpowers/specs/2026-08-16-daily-briefing-stale-health-data.md`

## Global Constraints

- Python 3.11 target (`pyproject.toml` `target-version = "py311"`). Use
  `X | None` unions, not `Optional[X]`.
- Ruff line-length is **100**. Ruff lint selects `E,W,F,I,B,N,UP,SIM`.
- Mypy runs with `disallow_untyped_defs = true` — **every** new function needs
  full type annotations, including `-> None`.
- Tests live under `tests/`, mirroring `src/mycoach/`. `asyncio_mode = "auto"`,
  so `async def test_*` needs no `@pytest.mark.asyncio`.
- Single-user MVP: `USER_ID = 1` in `scheduler/jobs.py`.
- Run tests with `uv run pytest`. Lint with `uv run ruff check .`.
- Do **not** change `import_health_snapshot`'s null-filling semantics
  (`sources/garmin/mappers.py:390-393`) — it is correct and the recovery of
  14/08 depended on it.
- Never make an empty Garmin day silently pass as success. That silence is the
  bug being fixed.

---

### Task 1: Content-based `has_data` detection

Today `_fetch_health_for_day` decides "did we get data?" with
`isinstance(response, dict)`. Garmin's empty-day skeleton is a valid dict full
of nulls, so it scores `True` on every field. This task replaces the type check
with a content check on the mapped snapshot, and fixes the log line that lied.

**Files:**
- Modify: `src/mycoach/sources/garmin/mappers.py` (add `snapshot_has_data` near `_UPDATABLE_FIELDS`, line ~354-364)
- Modify: `src/mycoach/sources/garmin/source.py:104-154` (`_fetch_health_for_day`)
- Test: `tests/test_sources/test_garmin.py`

**Interfaces:**
- Consumes: `_UPDATABLE_FIELDS` (existing, `mappers.py:354`), `DailyHealthSnapshot` model.
- Produces: `snapshot_has_data(snapshot: DailyHealthSnapshot) -> bool` — exported from `mycoach.sources.garmin.mappers`. Task 2 relies on `_fetch_health_for_day` already returning a content-based `has_data`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sources/test_garmin.py`, at the end of the file:

```python
class TestSnapshotHasData:
    def test_all_null_skeleton_has_no_data(self) -> None:
        """Garmin's empty-day response is a valid dict of nulls — not data."""
        skeleton = {
            "restingHeartRate": None,
            "maxHeartRate": None,
            "totalSteps": None,
            "calendarDate": "2026-08-14",
        }
        snapshot = map_health_snapshot(
            user_id=1,
            snapshot_date=date(2026, 8, 14),
            stats=skeleton,
            sleep={"dailySleepDTO": {}},
            hrv={"hrvSummary": {}},
        )
        assert snapshot_has_data(snapshot) is False

    def test_populated_snapshot_has_data(self) -> None:
        snapshot = map_health_snapshot(
            user_id=1,
            snapshot_date=date(2026, 8, 13),
            stats=SAMPLE_STATS,
            sleep=SAMPLE_SLEEP,
        )
        assert snapshot_has_data(snapshot) is True

    def test_raw_data_alone_is_not_data(self) -> None:
        """raw_data is always set, so it must not count as content."""
        snapshot = map_health_snapshot(
            user_id=1,
            snapshot_date=date(2026, 8, 14),
            stats={"calendarDate": "2026-08-14"},
        )
        assert snapshot.raw_data is not None
        assert snapshot_has_data(snapshot) is False
```

Add `snapshot_has_data` to the existing import block at the top of the file:

```python
from mycoach.sources.garmin.mappers import (
    import_activities,
    import_health_snapshot,
    map_activity,
    map_health_snapshot,
    snapshot_has_data,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sources/test_garmin.py::TestSnapshotHasData -v`
Expected: FAIL at collection with `ImportError: cannot import name 'snapshot_has_data'`

- [ ] **Step 3: Write minimal implementation**

In `src/mycoach/sources/garmin/mappers.py`, directly after the
`_UPDATABLE_FIELDS` list (ends line ~364), add:

```python
# raw_data is excluded: it is always written, even for Garmin's empty-day
# skeleton, so its presence says nothing about whether the day has content.
_CONTENT_FIELDS = [f for f in _UPDATABLE_FIELDS if f != "raw_data"]


def snapshot_has_data(snapshot: DailyHealthSnapshot) -> bool:
    """Does this snapshot carry any usable metric?

    Garmin answers a day it has no data for with a well-formed JSON document
    whose every metric is null. Checking the *response type* cannot tell that
    apart from a rich day — checking the *mapped content* can.
    """
    return any(getattr(snapshot, field) is not None for field in _CONTENT_FIELDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sources/test_garmin.py::TestSnapshotHasData -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the failing test for the source using it**

Add to `tests/test_sources/test_garmin.py` inside `class TestGarminSource`:

```python
    async def test_null_skeleton_day_is_flagged_as_empty(self, setup_db) -> None:  # type: ignore[no-untyped-def]
        """A dict-shaped but all-null Garmin response must count as no data."""
        from tests.conftest import test_session

        mock_client = MagicMock()
        mock_client.get_stats.return_value = {"calendarDate": "2026-08-14"}
        mock_client.get_sleep_data.return_value = {"dailySleepDTO": {}}
        mock_client.get_hrv_data.return_value = {"hrvSummary": {}}
        mock_client.get_stress_data.return_value = {}
        mock_client.get_body_battery.return_value = []
        mock_client.get_training_readiness.return_value = {}
        mock_client.get_training_status.return_value = {}
        mock_client.get_max_metrics.return_value = []
        mock_client.get_respiration_data.return_value = {}
        mock_client.get_spo2_data.return_value = {}
        mock_client.get_activities_by_date.return_value = []

        source = GarminSource(client=mock_client)

        async with test_session() as session:
            user = await _create_user(session)
            await session.commit()

            result = await source.fetch_and_import(
                session, user.id, since=datetime(2026, 8, 14)
            )

            assert result.errors is not None
            assert any("no usable Garmin health data" in e for e in result.errors)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_sources/test_garmin.py::TestGarminSource::test_null_skeleton_day_is_flagged_as_empty -v`
Expected: FAIL — `assert result.errors is not None` fails, because the current
`isinstance` checks score the skeleton as data.

- [ ] **Step 7: Replace the type check with the content check**

In `src/mycoach/sources/garmin/source.py`, replace lines 121-154 (the
`field_status` dict through the `return`) with:

```python
        snapshot = map_health_snapshot(
            user_id=user_id,
            snapshot_date=day,
            stats=stats,
            sleep=sleep,
            hrv=hrv,
            stress=stress,
            body_battery=body_battery if isinstance(body_battery, list) else None,
            training_readiness=training_readiness,
            training_status=training_status,
            max_metrics=max_metrics,
            respiration=respiration,
            spo2=spo2,
        )

        # Judge the mapped content, not the response type. Garmin answers a day
        # it has nothing for with a well-formed document of nulls, which an
        # isinstance() check scores as data — that is what hid two days of
        # missing briefing data.
        has_data = snapshot_has_data(snapshot)
        if not has_data:
            logger.warning(
                "Garmin health fetch for %s: response carried no usable values", day
            )
        return snapshot, has_data
```

Update the import at the top of `source.py` — find the existing
`from mycoach.sources.garmin.mappers import (...)` block and add
`snapshot_has_data` to it (keep the names alphabetically sorted, ruff `I` will
enforce this).

- [ ] **Step 8: Run the full Garmin suite**

Run: `uv run pytest tests/test_sources/test_garmin.py -v`
Expected: PASS. `test_fetch_and_import` still passes (rich samples produce
content) and `test_list_shaped_stats_for_today_does_not_crash` still passes
(all-empty input still flags).

- [ ] **Step 9: Lint**

Run: `uv run ruff check src/mycoach/sources/garmin/ tests/test_sources/test_garmin.py`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add src/mycoach/sources/garmin/mappers.py src/mycoach/sources/garmin/source.py tests/test_sources/test_garmin.py
git commit -m "fix(garmin): judge day emptiness by snapshot content, not response type

Garmin answers a day it has no data for with a well-formed JSON document
whose every metric is null. The isinstance(x, dict) field_status check
scored that as data, so empty days were logged identically to rich ones
and never reached the empty_health_days warning."
```

---

### Task 2: Report empty days and API failures as structured data

`fetch_and_import` currently reports empty days only as a formatted string
inside `errors`. Task 4 needs to ask "did *today* come back empty?" without
parsing prose. This task also stops `_safe_call` from making a crashed endpoint
look like an empty one.

**Files:**
- Modify: `src/mycoach/sources/base.py:9-21` (`ImportResult`)
- Modify: `src/mycoach/sources/garmin/source.py:60-102` (`fetch_and_import`), `:104-154` (`_fetch_health_for_day`), `:156-162` (`_safe_call`)
- Test: `tests/test_sources/test_garmin.py`

**Interfaces:**
- Consumes: `snapshot_has_data` from Task 1.
- Produces:
  - `ImportResult.empty_health_days: list[date]` (default `[]`) — days whose fetch produced no usable content.
  - `GarminSource._safe_call(func, *args, failures: list[str] | None = None) -> Any` — appends `func.__name__` to `failures` on exception.
  - `_fetch_health_for_day(user_id, day) -> tuple[DailyHealthSnapshot, bool, list[str]]` — third element is the names of Garmin calls that raised.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_sources/test_garmin.py` inside `class TestGarminSource`:

```python
    async def test_empty_days_exposed_as_structured_dates(self, setup_db) -> None:  # type: ignore[no-untyped-def]
        """Callers must be able to ask 'was this day empty?' without parsing prose."""
        from tests.conftest import test_session

        mock_client = MagicMock()
        mock_client.get_stats.return_value = {"calendarDate": "2026-08-14"}
        mock_client.get_sleep_data.return_value = {}
        mock_client.get_hrv_data.return_value = {}
        mock_client.get_stress_data.return_value = {}
        mock_client.get_body_battery.return_value = []
        mock_client.get_training_readiness.return_value = {}
        mock_client.get_training_status.return_value = {}
        mock_client.get_max_metrics.return_value = []
        mock_client.get_respiration_data.return_value = {}
        mock_client.get_spo2_data.return_value = {}
        mock_client.get_activities_by_date.return_value = []

        source = GarminSource(client=mock_client)

        async with test_session() as session:
            user = await _create_user(session)
            await session.commit()

            result = await source.fetch_and_import(
                session, user.id, since=datetime(2026, 8, 14)
            )

            assert date(2026, 8, 14) in result.empty_health_days

    async def test_api_exception_reported_separately_from_emptiness(self, setup_db) -> None:  # type: ignore[no-untyped-def]
        """A crashed endpoint must not masquerade as a day with no data."""
        from tests.conftest import test_session

        mock_client = MagicMock()
        mock_client.get_stats.return_value = SAMPLE_STATS
        mock_client.get_sleep_data.side_effect = RuntimeError("401 Unauthorized")
        mock_client.get_hrv_data.return_value = SAMPLE_HRV
        mock_client.get_stress_data.return_value = SAMPLE_STRESS
        mock_client.get_body_battery.return_value = SAMPLE_BODY_BATTERY
        mock_client.get_training_readiness.return_value = SAMPLE_TRAINING_READINESS
        mock_client.get_training_status.return_value = SAMPLE_TRAINING_STATUS
        mock_client.get_max_metrics.return_value = SAMPLE_MAX_METRICS
        mock_client.get_respiration_data.return_value = SAMPLE_RESPIRATION
        mock_client.get_spo2_data.return_value = SAMPLE_SPO2
        mock_client.get_activities_by_date.return_value = []

        source = GarminSource(client=mock_client)

        async with test_session() as session:
            user = await _create_user(session)
            await session.commit()

            result = await source.fetch_and_import(
                session, user.id, since=datetime(2026, 8, 14)
            )

            assert result.errors is not None
            assert any("get_sleep_data" in e for e in result.errors)
            # The day still had other content, so it is not an "empty" day.
            assert result.empty_health_days == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sources/test_garmin.py::TestGarminSource::test_empty_days_exposed_as_structured_dates tests/test_sources/test_garmin.py::TestGarminSource::test_api_exception_reported_separately_from_emptiness -v`
Expected: FAIL — first with `AttributeError: 'ImportResult' object has no attribute 'empty_health_days'`, second with the `get_sleep_data` assertion.

- [ ] **Step 3: Add the field to `ImportResult`**

In `src/mycoach/sources/base.py`, add to the dataclass (after
`health_snapshots_updated`, before `errors`):

```python
    empty_health_days: list[date] = field(default_factory=list)
```

Update the imports at the top of `src/mycoach/sources/base.py`:

```python
from dataclasses import dataclass, field
from datetime import date
```

(Keep the existing `from abc import ABC, abstractmethod` and any other imports;
ruff `I` will order them.)

- [ ] **Step 4: Make `_safe_call` record failures**

In `src/mycoach/sources/garmin/source.py`, replace `_safe_call` (lines 156-162):

```python
    @staticmethod
    def _safe_call(func: Any, *args: Any, failures: list[str] | None = None) -> Any:
        """Call a Garmin API method, returning None on failure.

        The failure is also appended to ``failures`` when one is given, because
        a returned ``None`` alone cannot be told apart from an endpoint that
        legitimately had nothing to report — and treating a crash as an empty
        day is how a broken sync stays invisible.
        """
        try:
            return func(*args)
        except Exception as e:
            logger.warning("Garmin API call %s failed: %s", func.__name__, e)
            if failures is not None:
                failures.append(func.__name__)
            return None
```

- [ ] **Step 5: Thread failures through `_fetch_health_for_day`**

In the same file, change the signature and the ten `_safe_call` lines
(currently 104-119):

```python
    def _fetch_health_for_day(
        self, user_id: int, day: date
    ) -> tuple[DailyHealthSnapshot, bool, list[str]]:
        """Fetch all health data for a single day and build a snapshot.

        Each API call is wrapped individually so partial data is still captured.
        Returns the snapshot, whether it carries usable content, and the names
        of any Garmin calls that raised.
        """
        failures: list[str] = []
        raw_stats = self._safe_call(self._client.get_stats, day, failures=failures)
        stats = raw_stats if isinstance(raw_stats, dict) else {}
        sleep = self._safe_call(self._client.get_sleep_data, day, failures=failures)
        hrv = self._safe_call(self._client.get_hrv_data, day, failures=failures)
        stress = self._safe_call(self._client.get_stress_data, day, failures=failures)
        body_battery = self._safe_call(
            self._client.get_body_battery, day, day, failures=failures
        )
        training_readiness = self._safe_call(
            self._client.get_training_readiness, day, failures=failures
        )
        training_status = self._safe_call(
            self._client.get_training_status, day, failures=failures
        )
        max_metrics = self._safe_call(self._client.get_max_metrics, day, failures=failures)
        respiration = self._safe_call(
            self._client.get_respiration_data, day, failures=failures
        )
        spo2 = self._safe_call(self._client.get_spo2_data, day, failures=failures)
```

and change the final `return` (written in Task 1 Step 7) to:

```python
        return snapshot, has_data, failures
```

- [ ] **Step 6: Update the caller loop**

In `fetch_and_import`, replace lines 61-83 (the `empty_health_days` local
through the `if empty_health_days:` block) with:

```python
        # Fetch health snapshots day by day
        current = start_date
        while current <= end_date:
            try:
                snapshot, has_data, failures = self._fetch_health_for_day(user_id, current)
                if not has_data:
                    result.empty_health_days.append(current)
                if failures:
                    errors.append(
                        f"Garmin API calls failed for {current}: {', '.join(failures)}"
                    )
                created = await import_health_snapshot(session, snapshot)
                if created:
                    result.health_snapshots_created += 1
                else:
                    result.health_snapshots_updated += 1
            except Exception as e:
                await session.rollback()
                errors.append(f"Health fetch failed for {current}: {e}")
                logger.warning("Health fetch failed for %s: %s", current, e)
            current += timedelta(days=1)

        if result.empty_health_days:
            errors.append(
                f"{len(result.empty_health_days)} day(s) synced with no usable Garmin "
                f"health data: {', '.join(str(d) for d in result.empty_health_days)}"
            )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_sources/test_garmin.py -v`
Expected: PASS, all tests including the two new ones and the pre-existing
`test_list_shaped_stats_for_today_does_not_crash`.

- [ ] **Step 8: Run the wider suite for `ImportResult` consumers**

Run: `uv run pytest tests/test_sources/ tests/test_api/ -v`
Expected: PASS. `ImportResult` is also built in `sources/hevy/` and consumed by
`api/routes/sources.py`; the new field has a default, so nothing else needs
changing — this run proves it.

- [ ] **Step 9: Lint and typecheck**

Run: `uv run ruff check src/ tests/ && uv run mypy src/mycoach/sources/`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add src/mycoach/sources/base.py src/mycoach/sources/garmin/source.py tests/test_sources/test_garmin.py
git commit -m "feat(garmin): expose empty days and API failures on ImportResult

Empty days were reported only as a formatted string, so callers could not
act on them. _safe_call also turned a crashed endpoint into an
indistinguishable None, letting a broken sync look like a quiet day."
```

---

### Task 3: Widen the scheduler's sync lookback to 7 days

The scheduler looks back 2 days; the manual sync endpoint already defaults to 7.
A Garmin upload that lands more than 2 days late is currently unrecoverable —
which nearly lost 14/08 permanently.

**Files:**
- Modify: `src/mycoach/config.py` (add setting near `scheduler_sync_minute`, line ~70)
- Modify: `src/mycoach/scheduler/jobs.py:200-225` (`job_garmin_sync`, `_garmin_sync`)
- Test: `tests/test_scheduler/test_jobs.py`

**Interfaces:**
- Consumes: `get_settings()` (already imported in `scheduler/jobs.py:22`).
- Produces:
  - `Settings.scheduler_sync_lookback_days: int = 7`
  - `_garmin_sync(days: int | None = None) -> ImportResult` — now **returns** the result, which Task 4 depends on. `days=None` reads the setting.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler/test_jobs.py`, after `test_garmin_sync_success`:

```python
async def test_garmin_sync_looks_back_seven_days_by_default(
    mock_session: AsyncMock,
) -> None:
    """A late Garmin upload must still be recoverable days later."""
    mock_source = MagicMock()
    mock_source.authenticate = AsyncMock(return_value=True)
    mock_result = MagicMock()
    mock_result.health_snapshots_created = 0
    mock_result.activities_created = 0
    mock_source.fetch_and_import = AsyncMock(return_value=mock_result)
    mock_merge = MagicMock(merged=0)

    with (
        patch("mycoach.scheduler.jobs.GarminSource", return_value=mock_source),
        patch("mycoach.scheduler.jobs.async_session", return_value=mock_session),
        patch("mycoach.scheduler.jobs.merge_garmin_hevy", AsyncMock(return_value=mock_merge)),
    ):
        await _garmin_sync()

    since = mock_source.fetch_and_import.await_args.kwargs["since"]
    assert (datetime.utcnow().date() - since.date()).days == 7


async def test_garmin_sync_returns_the_import_result(mock_session: AsyncMock) -> None:
    """The briefing job needs the result to decide whether to skip."""
    mock_source = MagicMock()
    mock_source.authenticate = AsyncMock(return_value=True)
    mock_result = MagicMock()
    mock_result.health_snapshots_created = 1
    mock_result.activities_created = 0
    mock_source.fetch_and_import = AsyncMock(return_value=mock_result)
    mock_merge = MagicMock(merged=0)

    with (
        patch("mycoach.scheduler.jobs.GarminSource", return_value=mock_source),
        patch("mycoach.scheduler.jobs.async_session", return_value=mock_session),
        patch("mycoach.scheduler.jobs.merge_garmin_hevy", AsyncMock(return_value=mock_merge)),
    ):
        result = await _garmin_sync()

    assert result is mock_result
```

Add `datetime` to the test file's imports — change line 4
(`from datetime import date`) to:

```python
from datetime import date, datetime
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler/test_jobs.py::test_garmin_sync_looks_back_seven_days_by_default tests/test_scheduler/test_jobs.py::test_garmin_sync_returns_the_import_result -v`
Expected: FAIL — the first asserts `2 == 7`, the second gets `None`.

- [ ] **Step 3: Add the setting**

In `src/mycoach/config.py`, after `scheduler_sync_minute: int = 0` (line ~70):

```python
    # Garmin uploads can land a day or more after the fact, so each sync
    # re-fetches a window rather than only the newest days. import_health_snapshot
    # fills nulls on re-fetch, so a wider window is pure recovery.
    scheduler_sync_lookback_days: int = 7
```

- [ ] **Step 4: Use it, and return the result**

In `src/mycoach/scheduler/jobs.py`, replace `job_garmin_sync` and
`_garmin_sync` (lines 200-225) with:

```python
def job_garmin_sync() -> None:
    """Sync health and activity data from Garmin Connect."""
    logger.info("Scheduler: starting Garmin sync")
    _run_recorded_job("garmin_sync", _garmin_sync())


async def _garmin_sync(days: int | None = None) -> ImportResult:
    """Fetch and import a window of Garmin data, returning what was imported.

    The window is wider than "since the last run" on purpose: Garmin uploads
    can arrive a day or more late, and ``import_health_snapshot`` fills nulls
    on re-fetch, so re-asking for a day we already have can only improve it.
    """
    if days is None:
        days = get_settings().scheduler_sync_lookback_days

    source = GarminSource()
    if not await source.authenticate():
        raise RuntimeError("Garmin authentication failed")

    async with async_session() as session:
        since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        since = since - timedelta(days=days)
        result = await source.fetch_and_import(session, USER_ID, since=since)
        merge_result = await merge_garmin_hevy(session, USER_ID)
        await session.commit()
        logger.info(
            "Scheduler: Garmin sync complete — health=%d, activities=%d, merged=%d",
            result.health_snapshots_created,
            result.activities_created,
            merge_result.merged,
        )
        return result
```

Add the import to `src/mycoach/scheduler/jobs.py` (near line 37, alongside the
existing `from mycoach.sources.garmin.source import GarminSource`):

```python
from mycoach.sources.base import ImportResult
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler/test_jobs.py -v`
Expected: PASS, including the pre-existing `test_garmin_sync_success` and
`test_garmin_sync_auth_failure_raises`.

- [ ] **Step 6: Confirm the setting is readable**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS. The new field has a default, so no config test needs changing.

- [ ] **Step 7: Lint**

Run: `uv run ruff check src/mycoach/config.py src/mycoach/scheduler/jobs.py tests/test_scheduler/test_jobs.py`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add src/mycoach/config.py src/mycoach/scheduler/jobs.py tests/test_scheduler/test_jobs.py
git commit -m "fix(scheduler): widen Garmin sync lookback from 2 to 7 days

Garmin uploads can land more than 2 days late, at which point the old
window had already closed and the day was unrecoverable. The manual sync
endpoint already defaulted to 7."
```

---

### Task 4: Briefing syncs first, and skips when there is nothing to brief on

The briefing reads a snapshot written 3.5 hours earlier, before the night's
sleep existed. This task makes it fetch its own data, and refuse to invent a
recovery verdict when there genuinely is none.

**Files:**
- Modify: `src/mycoach/scheduler/jobs.py:228-242` (`job_daily_briefing`, `_daily_briefing`)
- Test: `tests/test_scheduler/test_jobs.py`

**Interfaces:**
- Consumes: `_garmin_sync(days: int | None = None) -> ImportResult` (Task 3), `ImportResult.empty_health_days` (Task 2), `PipelineSkip` (already imported, `scheduler/jobs.py:21`).
- Produces: nothing downstream.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler/test_jobs.py`, after the existing
`test_daily_briefing_success`:

```python
async def test_daily_briefing_syncs_before_generating(
    mock_session: AsyncMock, mock_engine: MagicMock
) -> None:
    """The briefing must fetch fresh data, not read a snapshot hours old."""
    calls: list[str] = []

    async def fake_sync(days: int | None = None) -> MagicMock:
        calls.append("sync")
        return MagicMock(empty_health_days=[])

    async def fake_generate(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append("generate")
        return MagicMock(content='{"readiness_verdict": "go_hard"}')

    mock_engine.generate_daily_briefing = AsyncMock(side_effect=fake_generate)

    with (
        patch("mycoach.scheduler.jobs._garmin_sync", fake_sync),
        patch("mycoach.scheduler.jobs.CoachingEngine", return_value=mock_engine),
        patch("mycoach.scheduler.jobs.async_session", return_value=mock_session),
        patch("mycoach.scheduler.jobs._get_user_email_pref", AsyncMock(return_value=False)),
    ):
        await _daily_briefing()

    assert calls == ["sync", "generate"]


async def test_daily_briefing_skips_when_today_has_no_health_data(
    mock_session: AsyncMock, mock_engine: MagicMock
) -> None:
    """No data is a skip with a reason — never a briefing invented from nothing."""
    today = date.today()

    async def fake_sync(days: int | None = None) -> MagicMock:
        return MagicMock(empty_health_days=[today])

    with (
        patch("mycoach.scheduler.jobs._garmin_sync", fake_sync),
        patch("mycoach.scheduler.jobs.CoachingEngine", return_value=mock_engine),
        patch("mycoach.scheduler.jobs.async_session", return_value=mock_session),
        pytest.raises(PipelineSkip, match="no usable health data"),
    ):
        await _daily_briefing()

    mock_engine.generate_daily_briefing.assert_not_awaited()


async def test_daily_briefing_proceeds_when_sync_fails(
    mock_session: AsyncMock, mock_engine: MagicMock
) -> None:
    """A sync failure must not block a briefing when the DB already has data."""

    async def failing_sync(days: int | None = None) -> MagicMock:
        raise RuntimeError("Garmin authentication failed")

    mock_engine.generate_daily_briefing = AsyncMock(
        return_value=MagicMock(content='{"readiness_verdict": "moderate"}')
    )

    with (
        patch("mycoach.scheduler.jobs._garmin_sync", failing_sync),
        patch("mycoach.scheduler.jobs.CoachingEngine", return_value=mock_engine),
        patch("mycoach.scheduler.jobs.async_session", return_value=mock_session),
        patch("mycoach.scheduler.jobs._get_user_email_pref", AsyncMock(return_value=False)),
    ):
        await _daily_briefing()

    mock_engine.generate_daily_briefing.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scheduler/test_jobs.py -k daily_briefing -v`
Expected: FAIL — `test_daily_briefing_syncs_before_generating` gets
`calls == ["generate"]`, and the skip test gets no `PipelineSkip`.

- [ ] **Step 3: Write the implementation**

In `src/mycoach/scheduler/jobs.py`, replace `_daily_briefing` (lines 234-242):

```python
async def _daily_briefing() -> None:
    """Sync fresh Garmin data, then generate the briefing from it.

    The sync is part of the job rather than a separate cron entry because the
    coupling is real: a briefing about last night's sleep is meaningless
    without last night's sleep, and the standalone 06:00 sync runs before
    Garmin has finalised it. Encoding that in the job beats spacing two crons
    and hoping.
    """
    today = date.today()

    # A sync failure is not a reason to withhold a briefing — yesterday's data
    # may well be enough, and the failure is logged either way. Only a
    # confirmed absence of today's data below stops the run.
    empty_days: list[date] = []
    try:
        sync_result = await _garmin_sync()
        empty_days = list(sync_result.empty_health_days)
    except Exception as e:  # noqa: BLE001 - logged, and the briefing may still be viable
        logger.warning("Scheduler: pre-briefing Garmin sync failed — %s", e)

    if today in empty_days:
        raise PipelineSkip(
            f"Garmin returned no usable health data for {today} — skipping the "
            f"briefing rather than inferring recovery from nothing"
        )

    engine = CoachingEngine()
    async with async_session() as session:
        insight = await engine.generate_daily_briefing(session, USER_ID)
        logger.info("Scheduler: daily briefing generated")

        if await _get_user_email_pref("email_daily_briefing"):
            content = json.loads(insight.content)
            _deliver(partial(send_daily_briefing, content), "daily briefing")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scheduler/test_jobs.py -k daily_briefing -v`
Expected: PASS, including the pre-existing `test_daily_briefing_success`,
`test_daily_briefing_raises_skip_on_duplicate`, `test_daily_briefing_job_logs_skip`
and `test_daily_briefing_job_logs_malformed_response_as_failure`.

> If `test_daily_briefing_success` now fails because it does not patch
> `_garmin_sync`, patch it there too with
> `patch("mycoach.scheduler.jobs._garmin_sync", AsyncMock(return_value=MagicMock(empty_health_days=[])))`.
> Do not weaken the new behaviour to accommodate the old test.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: PASS. Pay attention to `tests/test_scheduler/test_job_runs.py` and
`tests/test_email/test_job_email.py`, which drive `_daily_briefing` end-to-end
and may need the same `_garmin_sync` patch.

- [ ] **Step 6: Lint and typecheck**

Run: `uv run ruff check src/ tests/ && uv run mypy src/mycoach/scheduler/`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/mycoach/scheduler/jobs.py tests/test_scheduler/test_jobs.py
git commit -m "fix(briefing): sync Garmin before generating, skip when no data

The briefing ran 3.5h after the sync and read a snapshot written before
Garmin had finalised the night's sleep, so it never saw the night it
exists to assess. It now fetches its own data, and skips with a recorded
reason rather than inferring a recovery verdict from nothing."
```

---

### Task 5: Update the scheduler docstring and verify against production

The module docstring still describes the old job layout, and the fix should be
confirmed against the real Garmin account before it is trusted.

**Files:**
- Modify: `src/mycoach/scheduler/scheduler.py:1-11` (module docstring), `:59-60` (comment)

**Interfaces:**
- Consumes: everything from Tasks 1-4. Produces: nothing.

- [ ] **Step 1: Update the docstring**

In `src/mycoach/scheduler/scheduler.py`, update the numbered list in the module
docstring so entry 2 reads:

```
2. Daily briefing (default 9:30 AM) — syncs Garmin first, then generates the
   briefing from the fresh data. The standalone 6:00 AM sync runs before Garmin
   has finalised the night's sleep, so the briefing cannot rely on it.
```

And update the comment at line 59 from `# 2. Daily briefing — daily, after
Garmin sync` to `# 2. Daily briefing — daily; syncs Garmin itself first`.

- [ ] **Step 2: Run the full suite one final time**

Run: `uv run pytest && uv run ruff check src/ tests/ && uv run mypy src/mycoach/`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add src/mycoach/scheduler/scheduler.py
git commit -m "docs(scheduler): describe the briefing's own Garmin sync"
```

- [ ] **Step 4: Verify against production**

Deploy, then on the homelab (`ssh 192.168.1.142`) trigger a real briefing and
confirm the prompt now carries today's sleep:

```bash
TOKEN=$(docker exec mycoach printenv MYCOACH_API_TOKEN)
curl -s -X POST -H "X-API-Key: $TOKEN" localhost:8000/api/system/scheduler/trigger/daily_briefing
sleep 60
docker exec mycoach python -c "import sqlite3; c=sqlite3.connect('/data/mycoach.db'); print(*[r[0][:900] for r in c.execute(\"select prompt_text from prompt_logs where prompt_type='daily_briefing' order by id desc limit 1\")], sep='\n')"
```

Expected: the `## Today's Health Data` section lists `Sleep score`, `HRV`, and
`Body Battery (morning)` — not `No health data available for today.`

> A briefing already exists for today after a normal run, so this will raise
> `PipelineSkip("Daily briefing already exists")`. To force a real regeneration,
> delete today's insight first, or run the check on a day before 09:30.

---

## Notes for the implementer

**Why the no-data guard is in the job, not the engine.** `generate_daily_briefing`
is also called by the manual API route, and three existing engine tests
(`test_logs_prompt`, `test_duplicate_raises`, `test_llm_failure_raises_and_logs`
in `tests/test_coaching/test_engine.py`) deliberately run with no health rows.
Putting the guard in the engine would break them and would block ad-hoc manual
generation. The job is where "we just synced and Garmin gave nothing" is known.

**Do not "fix" the empty row by not writing it.** Writing a row for a dataless
day is correct — `import_health_snapshot` later fills its nulls, which is
exactly how 14/08 and 15/08 were recovered. The bug was never the row; it was
calling that row a success.
