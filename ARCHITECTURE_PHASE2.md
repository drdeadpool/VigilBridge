# Vigil Phase 2 Architecture — Trend Analysis

Created: 2026-06-06. Implementation gate: ~2026-06-13 (≥7 days of device observations).

---

## Design Goals

Produce per-metric personal baselines and deviation scores from raw observations. No scoring systems, no AI interpretation, no recovery engine in this phase. The only output is: *is today's value normal for this person?*

---

## Core Data Flow

```
observations (Postgres)
    → rolling window query (7/14/30 days)
    → per-metric stats (mean, std, count)
    → stored in baselines table
    → deviation computed at read time
    → GET /trends/{user_id}?metric=X&period=Y
```

---

## New Database Table

```sql
CREATE TABLE baselines (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID    NOT NULL REFERENCES users(id),
    metric_type VARCHAR(64) NOT NULL,
    period_days INTEGER NOT NULL,        -- 7, 14, or 30
    computed_at TIMESTAMPTZ NOT NULL,
    n           INTEGER NOT NULL,        -- number of observations in window
    mean        FLOAT NOT NULL,
    std         FLOAT NOT NULL,
    min         FLOAT NOT NULL,
    max         FLOAT NOT NULL,
    UNIQUE (user_id, metric_type, period_days)
);
```

`UNIQUE (user_id, metric_type, period_days)` → one current baseline per metric per window. Upsert on recompute.

---

## Baseline Computation

**When:** Recompute after each successful `/ingest` that inserts new observations.

**How:**
```python
SELECT
    date_trunc('day', timestamp AT TIME ZONE user_tz) AS day,
    AVG(value) AS daily_avg
FROM observations
WHERE user_id = ? AND metric_type = ? AND data_quality_status = 'valid'
  AND timestamp > now() - interval '? days'
GROUP BY 1
ORDER BY 1
```

Daily-average first (prevents high-frequency sync from biasing stats), then `mean(daily_avgs)` and `std(daily_avgs)`.

**Minimum data gate:** Require `n >= 3` days before emitting a baseline. Below threshold, return `null` for deviation.

**Metrics to baseline in Phase 2:**
- `sleep_duration_hours` (actual sleep)
- `time_in_bed_hours`
- `sleep_start_hour`
- `sleep_end_hour`
- `steps_today`

---

## Deviation Score

No composite score. Per-metric only.

```
deviation_sigma = (today_value - baseline_mean) / baseline_std
```

Return raw sigma + direction (`above`/`below`/`normal`). Thresholds:
- `|sigma| < 1.0` → `normal`
- `1.0 ≤ |sigma| < 2.0` → `notable`
- `|sigma| ≥ 2.0` → `anomaly`

These are classification labels only — no scoring, no weighting.

---

## New API Endpoints

### `GET /trends/{user_id}?metric=X&period=7`

Response:
```json
{
  "metric": "sleep_duration_hours",
  "period_days": 7,
  "baseline": {
    "mean": 6.12,
    "std": 0.43,
    "n": 7
  },
  "series": [
    {"date": "2026-06-06", "value": 5.70, "deviation_sigma": -0.98, "label": "normal"},
    ...
  ]
}
```

### `GET /baselines/{user_id}` (optional convenience)

Returns all current baselines for the user.

---

## What Phase 2 Does NOT Include

- No recovery score
- No circadian phase detection
- No composite multi-metric index
- No sleep quality score
- No readiness metric
- No AI/LLM interpretation
- No push notifications
- No UI redesign

These belong to Phase 3+.

---

## Android Changes (Phase 2)

None required for data collection — pipeline is already correct. The only potential Android change: display trend context on dashboard (optional, low priority).

---

## Phase 2 Entry Criteria (unchanged)

1. ✅ INV-001 resolved
2. ≥7 days real observations in Postgres (~2026-06-13)
3. BUG-001 fixed ✅ (2026-06-06)
4. BUG-006 decision made (resting HR fallback)

---

## Implementation Order

1. Alembic migration: create `baselines` table
2. `baseline_service.py`: compute and upsert baseline from observations window
3. Hook baseline recompute into POST /ingest (after insert)
4. `GET /trends/{user_id}` endpoint
5. Unit tests: baseline computation, deviation labeling, insufficient-data gate
6. Verify against device observations

Do not start until ~2026-06-13 gate is met.
