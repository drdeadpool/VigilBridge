# Vigil — Roadmap

Last updated: 2026-06-26. Reflects v1.0 frozen state.

---

## Engineering Loop (Scientific Operations Mode)

Vigil is no longer in active engineering. The loop is:

```
Operate → Collect Evidence → Validate → Measure → Review → Implement Small Improvements → Benchmark → Deploy
```

New engineering work begins only when operational evidence justifies it.

---

## Phase Status

| Phase | Status | Completed |
|---|---|---|
| Science Phase 1 — Human State Science | ✅ COMPLETE | 2026-06 |
| Phase 1 — Reliable Ingestion | ✅ COMPLETE | 2026-06-06 |
| Phase 2 — Trend + Baseline Engine | ✅ COMPLETE | 2026-06-24 |
| Sprint 1 — Human State Engine v1.0 | ✅ COMPLETE | 2026-06-26 |
| Sprint 2 — Validation Engine v1.0 | ✅ COMPLETE | 2026-06-26 |
| Sprint 2A — Agreement Engine v1.0 | ✅ COMPLETE | 2026-06-26 |
| Sprint 2B — Persistence Audit | ✅ COMPLETE | 2026-06-26 |
| Sprint 3 — Production Deployment + Freeze | ✅ COMPLETE | 2026-06-26 |
| **Scientific Operations** | **ACTIVE** | 2026-06-26 → |

---

## ✅ Phase 1 COMPLETE — 2026-06-06

Samsung Health ingestion via Health Connect. Android app + WorkManager background sync. FastAPI backend. PostgreSQL persistence. Deduplication. IST-correct sleep timing.

**Evidence:** `POST /ingest` → 202, WorkManager autonomous sync proven, DB 40→56.

---

## ✅ Phase 2 COMPLETE — 2026-06-24

Baseline Engine v1 (per-metric mean/std/n/min/max over 7/14/30-day windows). Trend Engine. Resting HR fallback (BPM_MIN 02:00–06:00). Sleep merge fix (INV-001).

**Evidence:** 32/32 tests, baseline rows in Postgres, trend endpoints verified.

---

## ✅ Sprint 1 COMPLETE — 2026-06-26

Constraint Engine v0.1 (6 z-score rules). Human State Engine v0.1 (5-state priority cascade). Version constants. ADR-005 accepted. 146/146 tests.

**Evidence:** Commit d2cd36c. State endpoint returns real inference from production data.

---

## ✅ Sprint 2 COMPLETE — 2026-06-26

Validation Engine v0.1. ValidationRecord model + migration `a9f4e2d1b6c8`. create_or_update with ON CONFLICT DO UPDATE preserving operator columns. Integration hooks in ingest.py and state.py. 16 validation API tests.

**Evidence:** Commit 4852fad. Validation records persisting in production with 3 version tags.

---

## ✅ Sprint 2A COMPLETE — 2026-06-26

Agreement Engine v0.1. Read-only SQL analytics (FILTER aggregation). 17-key summary + per-state breakdown. 12 API tests + 13 service tests.

**Evidence:** Commit 6704f58. GET /agreement/{user_id} returns structured analytics.

---

## ✅ Sprint 2B COMPLETE — 2026-06-26

Scientific persistence audit. All 13 future Insight Engine questions answerable from current schema. No schema changes required.

**Evidence:** Commit c38c380. docs/SPRINT_2B_PERSISTENCE_AUDIT.md.

---

## ✅ Sprint 3 COMPLETE — 2026-06-26

Production deployment verified. 10/16 endpoints data-level confirmed with real production data. User UUID `37c5d374-d624-404f-ae6f-50a6781601bf` discovered. Freeze declared.

**Evidence:** Commit 2182269. docs/SPRINT_3_OPERATIONAL_READINESS.md.

---

## Current: Scientific Operations — ACTIVE

**Entry date:** 2026-06-26

**Objectives:**
1. Verify production daily
2. Run Human State Engine continuously (automatic via ingest)
3. Collect validation records (automatic)
4. Record operator assessments via PATCH /validation/{id}
5. Review agreement metrics periodically
6. Build ≥30 days of operator-assessed records
7. Identify statistically meaningful failure patterns

**Exit criteria (for next engineering milestone):**
- ≥30 days of operator-assessed validation records
- Measurable agreement/disagreement patterns identified
- At least one failure mode with statistical significance (p < 0.05)

---

## Future Phases (gated on scientific evidence)

### Next Milestone: Insight Engine v0.1

**Prerequisite:** ≥30 days of operator assessments, measurable agreement patterns.

**Scope (read-only analytics, same pattern as Agreement Engine):**
- Constraint failure rate analysis (which rules most often produce incorrect inferences)
- Confidence-accuracy correlation (does confidence predict correctness?)
- Evidence pattern analysis (which physiological combinations associate with disagreement)
- Consecutive-day state pattern analysis (temporal context)

**What it is NOT:** Not ML, not prediction, not LLM integration. Pure SQL analytics over existing tables.

**Gate check:** Sprint 2B audit confirmed all 13 planned questions answerable from current schema. No schema changes needed to build the Insight Engine.

---

### Phase 3: Circadian Engine

**Prerequisite:** Insight Engine data confirms sleep timing signals are reliable + ≥21 days of `sleep_start_hour` data.

**Scope:**
- Sleep regularity index (SRI)
- Social jetlag (weekday vs weekend sleep timing)
- DLMO proxy from sleep midpoint time series
- Phase shift detection

**Gate:** BUG-009 (sleep dating) must be resolved before circadian phase analysis is meaningful.

---

### Phase 4: Recovery Engine

**Prerequisite:** Circadian Engine live + HRV metric available (hardware dependent).

**Scope:**
- Severity-weighted constraint cascade (replaces fixed priority)
- Consecutive-day state weighting
- HRV-gated confidence (if `READ_HEART_RATE` aggregate provides HRV)
- Composite recovery score (0-100)

---

### Phase 5: Intelligence Layer

**Prerequisite:** Recovery Engine validated + ≥30 days of recovery scores confirmed accurate.

**Scope:** Claude API integration. Clinician-readable narrative summaries. Read-only — no writes to DB.

---

### Phase 6: Multi-User + Auth

**Prerequisite:** Intelligence layer validated on single user.

**Scope:** JWT auth. User registration. Per-user data isolation.

---

## Known Open Bugs (not blocking operations)

| ID | Impact | Status |
|---|---|---|
| BUG-003 | Low (UX cosmetic) | Open |
| BUG-005 | Negligible | Open |
| BUG-007 | Cosmetic | Open |
| BUG-009 | Medium — sleep date attribution | Deferred (before Phase 3) |
| BUG-010 | Low (UX only) | Deferred (before Phase 5) |

---

## Technical Debt (not blocking)

| Item | Fix | Priority |
|---|---|---|
| `DashboardViewModel.init { refresh() }` fires pre-RESUME | Move to lifecycle observer | Low |
| `active_energy` absent (Samsung OEM siloing) | No code fix possible — OEM change needed | External |
| Sleep BPM_MIN fallback vs true RestingHR | No code fix possible — OEM siloing | External |

---

## Infrastructure State

| Component | State |
|---|---|
| Backend API | Live — vigilbridge.onrender.com, Render free tier |
| Postgres | Live — 7 tables, 1126 observations |
| Android APK | Installed — debug build, R5CXB2KE0VF |
| GitHub | drdeadpool/VigilBridge, auto-deploy from main |
| Migration head | a9f4e2d1b6c8 (Sprint 2) |
| Tests | 146/146 passing |

---

## Version History

| Version | Date | Description |
|---|---|---|
| v0.1 | 2026-06-02 | HC dashboard, corrupt record investigation |
| v0.2 | 2026-06-02 | MVVM, Room, WorkManager |
| v0.3 | 2026-06-03–06 | Backend + network, timezone fix, sleep timing, dedup, autonomous sync |
| v0.4 | 2026-06-24 | Baseline Engine v1, Trend Engine, BUG-006 fix, resting HR anchor |
| v1.0 | 2026-06-26 | Human State Engine, Validation Engine, Agreement Engine, freeze declared |
