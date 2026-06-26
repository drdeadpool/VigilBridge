# Vigil — Engineering Transition Report

**Date:** 2026-06-26
**Version:** 1.0
**Status:** OFFICIAL BASELINE — Vigil v1.0
**Author:** Engineering (Sprint 1–3)

This report is the official handoff from Engineering Foundation to Scientific Operations. It constitutes the permanent record of what was built, what was verified, what risks remain, and what comes next.

---

## 1. Current Architecture

```
Samsung Galaxy S24 Ultra
  └─ Samsung Health → Health Connect (on-device)
       └─ VigilBridge Android App
            ├─ HealthRepository: reads HC metrics
            ├─ SleepMerger: merges split sessions, actual sleep from stages
            ├─ resting HR: BPM_MIN 02:00–06:00 fallback (Samsung OEM siloing)
            ├─ SnapshotCaptureStore: Room snapshot + outbox (one transaction)
            └─ OutboxUploadWorker: POST /ingest [network-constrained, retry]
                                              │
                    vigilbridge.onrender.com ◄─┘
                    FastAPI + uvicorn (Render free tier)
                              │
                         POST /ingest
                              │
                    ┌─────────┼─────────────┐
                    ▼         ▼             ▼
             observations  baselines   constraints
             (1126 rows)  (3–9 rows)  (6 rules/day)
                                           │
                                  state_estimates
                                  (1 row/day)
                                           │
                                 validation_records
                                 (1 row/day, versioned)
                                           │
                              Agreement Analytics (read-only SQL)
                                           │
                             [Future: Insight Engine]
                             [Future: Circadian Engine]
                             [Future: Recovery Engine]
                             [Future: Intelligence Layer]
```

**Evidence provenance chain:**
```
observation.raw_payload → constraint.evidence → state_estimate.evidence_refs
  → validation_record.evidence_provenance → agreement_service aggregations
```

Full traceability from raw sensor byte to agreement rate. No inference is opaque.

---

## 2. Current Production Status

| Metric | Value |
|---|---|
| Backend | Live — vigilbridge.onrender.com |
| Database | Live — PostgreSQL 16 (Render managed) |
| Observations | 1126 total |
| Migrations applied | 7 (head: `a9f4e2d1b6c8`) |
| Endpoints | 16 (all registered, auth-gated) |
| Tests | 146/146 passing |
| Last commit | 2182269 |
| Deploy | Render auto-deploy from `drdeadpool/VigilBridge:main` |
| User UUID | `37c5d374-d624-404f-ae6f-50a6781601bf` |

### Observation breakdown (2026-06-26)

| Metric | Count |
|---|---|
| steps_today | 305 |
| steps_7d | 364 |
| steps_30d | 364 |
| sleep_duration_hours | 16 |
| sleep_start_hour | 16 |
| sleep_end_hour | 16 |
| sleep_sessions_count | 16 |
| time_in_bed_hours | 16 |
| resting_hr_bpm | 9 |

### Endpoint verification (data-level, 2026-06-26)

| Endpoint | Status | Verified Output |
|---|---|---|
| GET /health | ✅ | `{"status":"ok","database":"connected"}` |
| POST /ingest | ✅ | User UUID in response, observations persisted |
| GET /stats | ✅ | 1126 observations, 10 metric types |
| GET /observations/recent | ✅ | Valid observations returned |
| GET /baselines/{user_id} | ✅ | Returns baselines (empty for new user — correct) |
| GET /state/{user_id} | ✅ | State, confidence, 6 constraints, evidence_refs |
| GET /state/{user_id}/history | ✅ | 1 entry per assessed day |
| GET /validation?user_id= | ✅ | Records with 3 version tags, evidence_provenance |
| GET /agreement/{user_id} | ✅ | 17-key summary, null rates (no assessments yet) |
| GET /agreement/{user_id}/by-state | ✅ | Per-state breakdown |
| Auth gates | ✅ | All endpoints return 401 without key, not 404 |

---

## 3. Completed Phases

| Phase | Completed | Key Deliverable |
|---|---|---|
| Science Phase 1 — Human State Science | 2026-06 | Human State Ontology, 5-state cascade specification |
| Phase 1 — Reliable Ingestion | 2026-06-06 | Android → Postgres pipeline, WorkManager sync proven |
| Phase 2 — Trend + Baseline Engine | 2026-06-24 | Baseline Engine v1, Trend Engine, BUG-006 fix |
| Sprint 1 — Human State Engine v1.0 | 2026-06-26 | Constraint Engine + State Estimator, ADR-005 |
| Sprint 2 — Validation Engine v1.0 | 2026-06-26 | Versioned inference records, operator assessment flow |
| Sprint 2A — Agreement Engine v1.0 | 2026-06-26 | Read-only analytics, 17-key summary, by-state breakdown |
| Sprint 2B — Persistence Audit | 2026-06-26 | Schema confirmed sufficient for future Insight Engine |
| Sprint 3 — Production Deployment + Freeze | 2026-06-26 | E2E verification, freeze declaration |

---

## 4. Frozen Components

All components listed below are frozen at v1.0. Changes require:
1. Operational evidence (≥30 days of assessed records minimum)
2. Measurable failure mode or improvement opportunity
3. ADR documenting decision, alternatives considered, and justification

| Component | Version | Frozen | Files |
|---|---|---|---|
| Observation Schema | v1.0 | Sprint 3 | 3 migrations (initial + quality + resting HR anchor) |
| Evidence Model | v1.0 | Sprint 3 | `constraint.py`, `state_estimate.py`, evidence JSONB columns |
| Baseline Engine | v1.0 | Sprint 3 | `baseline_service.py` |
| Trend Engine | v1.0 | Sprint 3 | `trend_service.py`, `api/v1/trends.py` |
| Constraint Engine | v1.0 | Sprint 1 | `constraint_engine.py` (6 rules, 1SD threshold) |
| Human State Estimator | v1.0 | Sprint 1 | `state_service.py` (5-state priority cascade) |
| Validation Engine | v1.0 | Sprint 2 | `validation_service.py`, `api/v1/validation.py` |
| Agreement Engine | v1.0 | Sprint 2A | `agreement_service.py`, `api/v1/agreement.py` |
| Persistence Model | v1.0 | Sprint 3 | 7 migrations, 7 tables |
| API | v1.0 | Sprint 3 | 16 endpoints, auth pattern |

**Permanently off-limits (no evidence threshold will justify these):**
- ML/LLM inference into Human State estimation (use deterministic cascade only)
- Redesign of architecture or persistence model
- Introduction of new physiological states without Phase 4 Recovery Engine evidence
- Prediction or personalization analytics

---

## 5. Remaining Scientific Risks

| Risk | Severity | Impact | Mitigation |
|---|---|---|---|
| **BUG-009: sleep dated by sleep-start** | Medium | Pre-midnight bedtimes counted on wrong day → `valid_days` miscounting → incorrect state inferences | Deferred. Operator assessments will surface this as a `rejected` pattern. Fix before Phase 3 Circadian Engine. |
| **resting_hr_bpm via fallback only** | Medium | `HeartRateRecord.BPM_MIN` 02:00–06:00 approximates, not equals, true resting HR. Elevations from sleep-phase HR spikes could falsely fire `rhr_elevated`. | No code fix possible (Samsung OEM). Operator assessments will surface false positives. |
| **active_energy absent** | Medium | `steps_high` constraint fires without `active_energy` context. High steps + no active energy record → incomplete physiological picture. | No code fix possible (Samsung OEM). Limits `strain_overshoot` precision. |
| **1SD fixed threshold** | Low–Medium | Low-variance individual fires constraints more easily. High-variance individual may miss real anomalies. | Threshold rigidity is known and documented in ADR-005. Requires evidence before adjusting. |
| **No temporal context** | Low–Medium | Each day evaluated independently. Consecutive `recovery_deficit` days carry no more weight than a single day. | Addressed in Phase 4 Recovery Engine via consecutive-day weighting. |
| **3 metrics only** | Medium | State space discriminability limited. `normal` is the residual — it includes "no anomaly in tracked metrics" not "no physiological anomaly." | Requires new sensor data or Phase 4 HRV integration. |
| **data_gap rate** | High initially | With `valid_days=0` on first use, every inference is `data_gap` until 3 days accumulate. Expected behavior but operator must be aware. | Documented. Baseline accumulates within 3 ingest cycles. |

---

## 6. Current Operational Bottlenecks

| Bottleneck | Impact | Resolution Path |
|---|---|---|
| **Zero operator assessments** | Agreement rate = null across all endpoints. No correctness signal yet. | Operator must begin recording PATCH /validation/{id} for past inference days immediately. |
| **Render free tier cold starts** | ~30s response on first request after 15-min idle. Ingest from Android may time out if device is first caller after idle. | OutboxUploadWorker retry behavior handles this. Low impact in practice. Upgrade Render tier when multi-user phase begins. |
| **No web UI for operator assessment** | Operator must use curl/HTTP client to PATCH /validation/{id}. Friction slows assessment velocity. | PATCH endpoint is complete. A minimal assessment UI (read-only dashboard + status buttons) is the highest-ROI future feature. |
| **BUG-009 (sleep dating)** | Occasional day miscounting inflates or deflates valid_days. Affects state inference correctness indirectly. | Operator assessments will surface the pattern. Fix before Phase 3. |
| **active_energy absent** | `strain_overshoot` requires steps_high + rhr_elevated; without active_energy corroboration, false positives possible. | OEM-dependent. No engineering action available. |

---

## 7. Recommended Cadence for Future Engineering Reviews

### Daily (operational, not engineering)
- Verify backend health: `GET /health`
- Check observation count is growing: `GET /stats`
- Record operator assessment for previous day's state: `PATCH /validation/{id}`

### Weekly
- Review agreement metrics: `GET /agreement/{user_id}`
- Check for systematic failure patterns (same state always `rejected`)
- Review `pending_rate` — if accumulating, investigate assessment velocity

### Monthly
- Review `inference_by_version` — confirms engine version consistency
- Review `confidence_distribution` — check for systematic low-confidence days
- Review `agreement_by_state` — identify which states have highest disagreement

### Engineering review trigger (not calendar-based)
Engineering review is triggered by evidence, not schedule:

| Trigger | Minimum threshold |
|---|---|
| Consistent failure pattern | ≥5 consecutive `rejected` records with same inferred_state |
| Systematic constraint misfiring | ≥10 `rejected` records all sharing same contributing_constraint |
| Confidence-accuracy anticorrelation | Statistically significant (p < 0.05) over ≥30 assessed days |
| OEM sensor change (Samsung Health update) | Any — verify existing fallbacks still work |
| New sensor data available (HRV, SpO2) | Any — evaluate against Phase 4 entry criteria |

---

## 8. Updated Project Completion Estimate

| Phase | Status | Estimated Start | Notes |
|---|---|---|---|
| Engineering Foundation | ✅ COMPLETE | — | Frozen v1.0 |
| Scientific Operations | ACTIVE | 2026-06-26 | Collecting validation data |
| Insight Engine v0.1 | Not started | ~2026-08 (≥30 assessed days) | Read-only analytics; no schema changes needed |
| Phase 3: Circadian Engine | Not started | ~2026-09 (post-BUG-009 fix + ≥21 sleep days) | Requires BUG-009 resolution |
| Phase 4: Recovery Engine | Not started | ~2026-11 (post-circadian validation) | Requires HRV data or circadian engine |
| Phase 5: Intelligence Layer | Not started | ~2027-Q1 | Claude API integration |
| Phase 6: Multi-User + Auth | Not started | ~2027-Q2 | JWT auth, user registration |

These are evidence-gated estimates. Each gate is a minimum — actual timing depends on what operational data reveals.

---

## 9. Next Recommended Milestone: Insight Engine v0.1

**Trigger:** ≥30 days of operator-assessed validation records with measurable agreement and disagreement patterns.

**What it is:** A read-only analytics layer over existing tables. Same architectural pattern as Agreement Engine — pure SQL, no writes, no new schema.

**What it answers (all answerable from current schema per Sprint 2B audit):**

| Question | SQL approach |
|---|---|
| Which constraints most frequently produce incorrect inferences? | JOIN constraints ON (user_id, day) + validation_records WHERE status='rejected' |
| Which evidence combinations associate with disagreement? | validation_records.contributing_constraints WHERE status='rejected' |
| Does confidence correlate with correctness? | validation_records.confidence vs validation_status GROUP BY confidence bucket |
| Which engine versions improve agreement? | validation_records.engine_version + validation_status (already in agreement_service) |
| Which constraints co-occur most often? | constraints WHERE fires=true GROUP BY (user_id, day), pairwise |
| Consecutive-day state patterns | LAG(state) OVER (PARTITION BY user_id ORDER BY day) |

**Implementation approach:**
1. No schema changes (confirmed by Sprint 2B audit)
2. New `insight_service.py` with pure SQL analytics
3. New `api/v1/insight.py` with read-only endpoints
4. Full test coverage (same pattern as agreement tests)
5. ADR documenting which patterns justified which analytics

**Prerequisite evidence required before starting:**
- Operator-assessed validation records covering ≥30 distinct days
- At least one constraint with ≥5 `rejected` records (a real pattern to analyze)
- Agreement rate not persistently null

---

## Vigil v1.0 — Final Architecture Confidence Assessment

```
╔══════════════════════════════════════════════════════════════╗
║               VIGIL v1.0 — OFFICIAL BASELINE                 ║
║                                                              ║
║  Architecture:    COHERENT ✅                                 ║
║  Provenance:      COMPLETE ✅                                 ║
║  Persistence:     SUFFICIENT FOR INSIGHT ENGINE ✅           ║
║  Validation:      OPERATIONAL ✅                             ║
║  Agreement:       OPERATIONAL ✅                             ║
║  E2E Pipeline:    VERIFIED ✅                                ║
║  Tests:           146/146 ✅                                  ║
║  Production:      LIVE ✅                                     ║
║                                                              ║
║  Phase:     Scientific Operations                            ║
║  Asset:     Validation dataset (not code)                    ║
║  Next gate: ≥30 operator-assessed days                       ║
║                                                              ║
║  Engineering confidence: HIGH                                ║
║  Scientific evidence: ACCUMULATING                           ║
╚══════════════════════════════════════════════════════════════╝
```

---

*End of Engineering Transition Report. This document is frozen. Amendments require a new ADR.*
