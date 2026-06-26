# Vigil — Capability Matrix

**Version:** 1.0
**Date:** 2026-06-26 (Engineering Hardening Sprint)
**Status:** Canonical maturity dashboard. Update as evidence accumulates.

This is the authoritative record of what Vigil can do, at what maturity level, and what evidence supports each capability.

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Complete / confirmed |
| ⚠️ | Partial / known gap |
| ❌ | Not present |
| 🔒 | Frozen — changes require ADR + evidence |
| 🔬 | Awaiting scientific validation |
| — | Not applicable |

---

## Layer 0 — Data Collection

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| Health Connect integration (S24 Ultra) | ✅ | ✅ | Manual on-device | ✅ | ✅ | 🔬 Pending | 21 days step coverage (100%), 16 sleep sessions, 9 RHR days | OEM limited — no code path to improve |
| Steps aggregation (today / 7d / 30d) | ✅ | ✅ | Manual | ✅ | ✅ | 🔬 Pending | 311–370 valid observations, 100% daily coverage, 21 days | None — OEM aggregate API is stable |
| Sleep capture (SleepMerger + stage extraction) | ✅ | ✅ | 11 unit (SleepMergerTest) | ✅ | ✅ | 🔬 Pending | 16 valid sessions, 75% coverage (5 gaps in 20 days) | BUG-009: physiological-night anchoring (deferred Phase 3) |
| Resting HR (BPM_MIN 02:00–06:00 fallback) | ✅ | ✅ | 9 unit (ExtractorRestingHrTest) | ✅ | ✅ | 🔬 Pending | 9 valid days, min=50 max=70 mean=57 bpm | Fallback only — Samsung siloing blocks native RestingHR |
| Active Energy | ✅ | ✅ | 5 unit (ExtractorActiveEnergyTest) | ✅ | ❌ Not firing | ❌ Not collectible | 0 observations — Samsung Health `ActiveCaloriesBurnedRecord` not written to HC on S24 Ultra | OEM change required — no code fix possible |
| Background sync (WorkManager 15-min) | ✅ | ✅ | Manual (WorkManager proven) | ✅ | ✅ | — | 21 days continuous background sync, no failures logged | None |
| Outbox with retry (OutboxUploadWorker) | ✅ | ✅ | Manual | ✅ | ✅ | — | Exponential backoff, network-constrained | None |
| HC permission management | ✅ | ✅ | Manual | ✅ | ✅ | — | 5 permissions granted, onResume recheck in place | None |

---

## Layer 1 — Ingestion & Persistence

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| POST /ingest endpoint | ✅ 🔒 | ✅ | Integration (146/146) | ✅ | ✅ | — | 1,166 total observations received, 0 ingest errors logged | None |
| Observation deduplication (ON CONFLICT DO UPDATE) | ✅ 🔒 | ✅ | Unit + Integration | ✅ | ✅ | — | 0 exact timestamp duplicates in production | None |
| FHIR-mappable flat schema | ✅ 🔒 | ✅ | Implicit | ✅ | ✅ | — | New metric types added without schema changes | None |
| Data quality classification (valid/probe/legacy/superseded) | ✅ 🔒 | ⚠️ Partial | Implicit | ✅ | ✅ | — | 1,144 valid / 22 flagged; `unknown` null rows marked `valid` incorrectly | Fix: `unknown` type → `probe` quality status |
| UTC storage + IST bucketing | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | 1,166/1,166 rows stored UTC | None |
| User/device registry (upsert on external_id) | ✅ 🔒 | ✅ | Integration | ✅ | ✅ | — | 1 active user + 3 legacy/test rows | None |
| Raw payload preservation (JSONB) | ✅ 🔒 | ✅ | Implicit | ✅ | ✅ | — | Every observation carries `raw_payload` JSONB | None |
| 7 Alembic migrations (applied) | ✅ 🔒 | ✅ | Migration tests | ✅ | ✅ | — | Head: `a9f4e2d1b6c8`. All migrations run on deploy startup | None |

---

## Layer 2 — Statistical Baselines

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| Baseline Engine (mean/std/n per metric × period) | ✅ 🔒 | ✅ | 14/14 unit | ✅ | ✅ | 🔬 Pending | 3 metrics with valid baselines (sleep 15 days, steps 21 days, RHR 9 days) | 7-day rolling window baseline (currently 30d only) |
| MIN_VALID_DAYS=3 gate | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | New user correctly shows `data_gap` | None |
| 30-day baseline period | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | Active for 21 days | Evidence needed before adding shorter windows |
| Automatic recompute on ingest | ✅ 🔒 | ✅ | Integration | ✅ | ✅ | — | Fires on every POST /ingest when BASELINE_METRICS present | None |
| GET /baselines/{user_id} | ✅ 🔒 | ✅ | 5/5 API | ✅ | ✅ | — | Returns current computed baselines | None |

---

## Layer 3 — Constraint Evaluation

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| 6 constraint rules (sleep/steps/RHR directional z-score) | ✅ 🔒 | ✅ | 16/16 unit | ✅ | ✅ | 🔬 Pending | 0 rules currently firing (new canonical user has 0 valid baseline days) | Wait for 3+ valid days before constraints can fire |
| Evidence JSONB per constraint | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | `{metric, direction, today, baseline_mean, baseline_std, z, valid_days}` captured | None |
| Severity (SD bands 1–3) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | 1SD threshold = 1SD firing threshold | Evidence needed before changing thresholds |
| Confidence formula (valid_days / 14) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | `confidence = min(1.0, valid_days / FULL_CONFIDENCE_DAYS)` | Evidence needed |
| Upsert per (user, day, rule) | ✅ 🔒 | ✅ | Integration | ✅ | ✅ | — | 6 constraint rows per ingest day, idempotent | None |

---

## Layer 4 — Human State Inference

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| 5-state cascade (data_gap, recovery_deficit, strain_overshoot, active_recovery, normal) | ✅ 🔒 | ✅ | 10/10 unit | ✅ | ✅ | 🔬 Pending | `data_gap` correctly inferred for new canonical user | 0 non-gap inferences so far on canonical user |
| Priority cascade (first-match wins, deterministic) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | All legacy user data from `0812485a` shows non-gap states | Scientific validation requires operator assessments |
| Contributing constraints JSONB | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | `["sleep_short", "rhr_elevated"]` pattern | None |
| Evidence refs JSONB | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | Today values + baselines used captured per inference | None |
| Automatic recompute on ingest | ✅ 🔒 | ✅ | Integration | ✅ | ✅ | — | Fires on every POST /ingest when BASELINE_METRICS present | None |
| State history endpoint | ✅ 🔒 | ✅ | Integration | ✅ | ✅ | — | GET /state/{user_id}/history → time series | None |

---

## Layer 5 — Validation & Operator Assessment

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| Automatic validation record creation | ✅ 🔒 | ✅ | 16/16 API + 11 service | ✅ | ✅ | — | Fires after every state inference; `validation_status=pending` | None |
| Version tagging (engine/constraint/evidence_model) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | All 3 version tags: `0.1 / 0.1 / 0.1` | None |
| Evidence provenance preservation | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | `evidence_provenance` JSONB immutable snapshot | None |
| Operator assessment (PATCH /validation/{id}) | ✅ 🔒 | ✅ | 16/16 API | ✅ | ❌ Not used | 🔬 Pending | **0 operator assessments recorded to date** | Operator must start using this immediately |
| Operator column preservation on re-inference | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | ON CONFLICT excludes `operator_assessment`, `validation_status`, `validated_at` | None |
| Status vocabulary (pending/confirmed/rejected/needs_review) | ✅ 🔒 | ✅ | Unit | ✅ | ⚠️ All pending | — | All records pending until first assessment | None |

---

## Layer 6 — Agreement Analytics

| Capability | Design | Implemented | Tested | Production | Operational | Sci Validated | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|---|---|---|
| 17-key agreement summary | ✅ 🔒 | ✅ | 12/12 API + 13 service | ✅ | ✅ | 🔬 Pending | `agreement_rate: null` (correct — no assessments) | Begin operator assessments to unlock analytics |
| Per-state agreement breakdown | ✅ 🔒 | ✅ | API + service | ✅ | ✅ | 🔬 Pending | 1 state (`data_gap`) with `pending_rate: 1.0` | Same |
| Confidence distribution (4 buckets) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | 🔬 Pending | 1 record in `[0.75, 1.0]` bucket | Same |
| Inference by version tracking | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | `"0.1": N` version counts | None |
| Read-only SQL analytics (no writes) | ✅ 🔒 | ✅ | Unit | ✅ | ✅ | — | Pure aggregation, no side effects | None |

---

## Infrastructure

| Capability | Design | Implemented | Operational | Evidence Quality | Next Improvement |
|---|---|---|---|---|---|
| FastAPI backend (Render free tier) | ✅ | ✅ | ✅ | `{"status":"ok","database":"connected"}` live | Upgrade to paid when multi-user |
| Docker containerization | ✅ | ✅ | ✅ | Auto-deploy from main branch | None |
| API authentication (dual key) | ✅ | ✅ | ✅ | `secrets.compare_digest`, scoped | None |
| Database backups | ✅ (plan) | ⚠️ Manual script only | ❌ Not running | 0 backups taken | **Run `backup_db.py` immediately and weekly** |
| Production monitoring | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual | Daily curl /health | Automated alerting (paid tier) |
| Automated testing (146 tests) | ✅ | ✅ | ✅ | 146/146 passing, 8 subtests | Add ingest API tests, `unknown` type handling |

---

## Known Gaps (Not Blocking Operations)

| Gap | Layer | Impact | Resolution |
|---|---|---|---|
| `active_energy` absent | 0 | Constraint `steps_high` / `strain_overshoot` less discriminating without caloric context | OEM change required |
| `unknown` null rows marked `valid` | 1 | 4 non-informative rows pollute valid observation count | Fix quality_status in extractor fallback |
| 0 operator assessments | 5 | Agreement metrics all null; no scientific validation possible | Operator must begin PATCH /validation/{id} workflow |
| No automated monitoring | Infra | Pipeline failures undetected until manual check | Paid tier or external uptime monitor |
| No database backups (automated) | Infra | Data loss risk | Run backup_db.py weekly minimum |
| BUG-009 sleep dating | 0 | Occasional duplicate/missing sleep date | Deferred to Phase 3 |

---

## Scientific Validation Status

**Current state:** Pre-validation. All engines built, tested, and deployed. Zero operator assessments recorded.

Scientific validation begins when:
1. ≥1 operator assessment recorded (PATCH /validation/{id})
2. `agreement_rate` becomes non-null
3. Pattern analysis possible after ≥30 assessed days

No capability can claim "Scientifically Validated" until operator assessments exist.
