# ADR-005: Recovery Inference — Deterministic Priority Cascade

**Status:** Accepted  
**Date:** 2026-06-26  
**Deciders:** Engineering (Sprint 1)  
**Supersedes:** —  
**Superseded by:** — (pending Phase 4 Recovery Engine)

---

## Context

Phase 1 (reliable ingestion) and Phase 2 Baseline Engine v1 are complete. The system collects three daily-reduced biometric signals:

| Metric | Daily reduction | Source |
|---|---|---|
| `sleep_duration_hours` | `sum(actualSleepMinutes)/60` | HC SleepSessionRecord |
| `steps_today` | `max(value)` over local day | HC StepsRecord aggregate |
| `resting_hr_bpm` | `min(HeartRateRecord.BPM)` 02:00–06:00 window | HC HeartRateRecord (fallback; Samsung Health omits RestingHeartRateRecord on S24 Ultra) |

The Baseline Engine (commit c3c305c) computes per-metric mean/std/n over 7/14/30-day windows. Sprint 1 goal: build the first end-to-end human state inference layer on top of this without waiting for Phase 4 full Recovery Engine.

### Forces

- **Insufficient data for ML**: 13–16 valid days at sprint start. No training set.
- **Interpretability requirement**: Target users are medical professionals. A state label without traceable evidence is not useful.
- **CLAUDE.md principle**: "Working over perfect." A deterministic layer that fires today is better than a probabilistic model that requires 90+ days of data.
- **Phase gate discipline**: The priority order (ingestion → baselines → trends → circadian → recovery → intelligence) must not be skipped. This ADR covers the _deterministic precursor_ to Phase 4 Recovery Engine, not a replacement for it.

---

## Decision

Implement a **two-layer deterministic system**:

1. **Constraint Engine v0.1** — evaluates six z-score rules over (today_value, baseline_mean, baseline_std). Each rule produces `{fires, severity, confidence, evidence}`.
2. **Human State Estimator v0.1** — composes fired constraints via a fixed priority cascade into a discrete state label.

### Constraint Engine (6 rules)

Firing condition: `|z| >= 1` AND value on the directionally correct side of the mean.

| Rule | Metric | Direction | Fires when |
|---|---|---|---|
| `sleep_short` | `sleep_duration_hours` | −1 | today < mean − 1SD |
| `sleep_long` | `sleep_duration_hours` | +1 | today > mean + 1SD |
| `steps_low` | `steps_today` | −1 | today < mean − 1SD |
| `steps_high` | `steps_today` | +1 | today > mean + 1SD |
| `rhr_elevated` | `resting_hr_bpm` | +1 | today > mean + 1SD |
| `rhr_suppressed` | `resting_hr_bpm` | −1 | today < mean − 1SD |

Severity levels (reused from Baseline Engine `severity()`): 0=normal (<1SD), 1=mild (1–2SD), 2=moderate (2–3SD), 3=severe (>3SD).

**Confidence formula:** `min(1.0, valid_days / 14)`. Confidence reflects evidence completeness (how many valid baseline days back the inference), not firing probability. At 14+ valid days, confidence = 1.0.

### State Cascade (priority order, first match wins)

```
1. data_gap          : valid_days < 3  OR  any BASELINE_METRIC absent today
2. recovery_deficit  : sleep_short ∧ rhr_elevated
3. strain_overshoot  : steps_high ∧ rhr_elevated ∧ ¬sleep_long
4. active_recovery   : steps_low ∧ sleep_long
5. normal            : otherwise
```

Priority ordering rationale:
- `data_gap` first — prevents false `normal` when evidence is insufficient.
- Pathological states (`recovery_deficit`, `strain_overshoot`) before behavioral states (`active_recovery`) — a physiological signal (elevated RHR) carries more clinical weight than activity pattern alone.
- `normal` is a catch-all residual, not an explicit assertion of wellness.

### Storage

- `constraints` table: one row per `(user_id, day, name)`, upserted on recompute.
- `state_estimates` table: one row per `(user_id, day)`, upserted on recompute.
- Both tables carry `evidence JSONB` / `evidence_refs JSONB` columns for full audit trail.
- Recompute triggered automatically after every `POST /ingest` (in `ingest.py`, try/except, never blocks ingest response).

### Why not ML / LLM

- No training labels. Subjective recovery ratings would require weeks of parallel data collection before a model is useful.
- LLM inference on raw biometric time-series would be opaque to medical professionals and expensive per-query.
- The signal space (3 metrics × 5 states) is deterministically coverable with threshold rules. An ML layer adds latency and maintenance overhead with no accuracy benefit at this data scale.

---

## Consequences

### What this enables

- Discrete state label per local day, available immediately after each ingest.
- Fully auditable: every state traces to named constraints, which trace to `(today_value, baseline_mean, baseline_std, z)`.
- API surface: `GET /state/{user_id}`, `GET /state/{user_id}/history`, `POST /state/{user_id}/recompute`.
- Foundation for Sprint 2 trends-over-states analysis and Phase 4 Recovery Engine.

### Limitations (known at adoption)

- **Coverage gap**: `active_energy` (activeEnergyBurned) not in BASELINE_METRICS because Samsung Health does not write `ActiveCaloriesBurnedRecord` to Health Connect on S24 Ultra (same OEM siloing confirmed for `RestingHeartRateRecord` via BUG-006). If a future device or Samsung Health update writes this, the metric can be added to BASELINE_METRICS and two new rules added to the Constraint Engine.
- **Threshold rigidity**: 1SD fixed threshold ignores individual signal noise. A low-sleep-variance individual will fire `sleep_short` more easily than a high-variance individual.
- **No temporal context**: Each day is evaluated independently. Consecutive days of `recovery_deficit` carry no more weight than a single day.
- **Missing physiological signals**: HRV, SpO2, respiratory rate, circadian phase are all absent. These would reduce `data_gap` rate and increase state discriminability.
- **Binary constraint firing**: Severity is recorded but not used in state selection. A severity-weighted cascade is a natural Phase 4 evolution.

### Evolution path toward Phase 4 Recovery Engine

| Phase 4 capability | Prerequisite |
|---|---|
| HRV-gated confidence | `READ_HEART_RATE` + aggregate HRV metric via successive-difference formula |
| Circadian phase correction | Circadian Engine (sleep timing patterns, `sleep_start_hour`, `sleep_end_hour`) |
| Consecutive-day weighting | State history table already present; state sequence analysis layer |
| Active energy integration | Samsung Health writing `ActiveCaloriesBurnedRecord` to HC (OEM change, no code change needed) |
| Severity-weighted cascade | Replace first-match priority with scoring over `severity × confidence` per constraint |

---

## Alternatives Considered

| Alternative | Rejected reason |
|---|---|
| Numeric recovery score (0–100) | Continuous score implies precision we don't have with 3 metrics; discrete states are more interpretable to medical professionals |
| LLM synthesis per user | Opaque, expensive per call, no training context; premature at Phase 2 |
| Wait for Phase 4 before any inference | "Working over perfect" — deterministic layer ships real signal today and provides structural scaffolding for Phase 4 |
| 2SD threshold | 1SD chosen to fire on mild deviations; medical context favors sensitivity over specificity at this stage |

---

## Implementation Reference

| Artifact | Path |
|---|---|
| Constraint Engine | `backend/app/services/constraint_engine.py` |
| State Estimator | `backend/app/services/state_service.py` |
| Models | `backend/app/models/constraint.py`, `state_estimate.py` |
| Migration | `backend/alembic/versions/f2b3c8d5a1e9_create_state_engine_tables.py` |
| API | `backend/app/api/v1/state.py` |
| Tests | `backend/tests/test_constraint_engine.py` (16 tests), `test_state_service.py` (10 tests) |
| Ingest hook | `backend/app/api/v1/ingest.py` — `compute_and_store_state()` after baseline recompute |
