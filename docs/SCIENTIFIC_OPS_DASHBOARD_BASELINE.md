# Scientific Operations — Operational Dashboard Baseline (Day 0)

**Date:** 2026-06-26
**Sprint:** Scientific Operations Sprint 0
**Purpose:** Day 0 baseline for all Scientific Operations KPIs. All future weekly reviews compare against this baseline.

---

## Platform Health

| Metric | Day 0 Value | Source |
|---|---|---|
| Backend status | `{"status":"ok","database":"connected"}` | `GET /health` (2026-06-26, post-push) |
| Deployment version | d5def80 | git log |
| Render tier | Free (cold start ~30s after idle) | render.yaml |
| Migrations applied | 7 (head: `a9f4e2d1b6c8`) | Alembic |
| Tests passing | 146/146 | pytest (Python 3.14.5) |
| API endpoints | 16 (all auth-gated) | Sprint 3 verification |
| Database tables | 7 | Schema |
| GitHub auto-deploy | Active (drdeadpool/VigilBridge, main) | GitHub Actions |
| Database backups | 0 run — CRITICAL GAP | Manual |

---

## Data Collection

| Metric | Day 0 Value | Target (30d) | Notes |
|---|---|---|---|
| Total observations | 1,166 | Growing | All time |
| Valid observations | 1,144 | ≥98% valid | 98.1% valid rate |
| Flagged observations | 22 | < 2% | Legacy/probe/superseded |
| UTC compliance | 100% | 100% | All 1,166 rows |
| Exact timestamp duplicates | 0 | 0 | Deduplication working |
| Collection days (steps) | 21 | Growing | 100% coverage |
| Collection days (sleep) | 15 of 20 | ≥70% | 75% coverage, 5 gap days |
| Collection days (RHR) | 9 of 21 | ≥50% | 43% coverage, hardware limit |
| Active energy days | 0 | 0 (OEM blocked) | Samsung siloing — no fix |
| Missing data rate (steps) | 0% | < 10% | Excellent |
| Missing data rate (sleep) | 25% | < 30% | Acceptable |
| Missing data rate (RHR) | 57% | < 50% | Below target — hardware |
| Steps per day range | 20–36 obs/day | Stable | WorkManager 15-min interval |

---

## Statistical Baselines

| Metric | 30d Baseline (approx) | Valid Days | Status |
|---|---|---|---|
| sleep_duration_hours | ~6.5h mean | 15 days | Active — sufficient for z-score |
| steps_today | Active | 21 days | Active — sufficient for z-score |
| resting_hr_bpm | ~57 bpm mean (min 50, max 70) | 9 days | Active — sufficient for z-score |

MIN_VALID_DAYS=3 — all three BASELINE_METRICS above threshold for legacy data. Canonical user `37c5d374` registered 2026-06-26; baselines will build over next 3–7 days.

---

## Human State Engine

| Metric | Day 0 Value | Notes |
|---|---|---|
| Active inference days | ~21 | Based on legacy user data |
| Current state (canonical user) | `data_gap` | Correct — new user, 0 valid baseline days |
| State distribution (all history) | data_gap dominant | Will shift as canonical user builds baseline |
| Confidence (canonical user) | ~0.07 | `min(1.0, 1/14)` — 1 valid day |
| FULL_CONFIDENCE_DAYS | 14 | Confidence = 1.0 after 14 valid days |
| Constraint firing (canonical user) | 0 rules | No valid baselines yet |
| Evidence chain | Intact | observation → constraint → state → validation provenance |

**Expected trajectory:** Non-gap states begin appearing within 3–7 days. Confidence reaches 0.50 at 7 valid days. Confidence reaches 1.0 at 14 valid days.

---

## Validation & Agreement

| Metric | Day 0 Value | Target (30d) | Notes |
|---|---|---|---|
| Validation records total | ~21 | ≥30 | Per-day, auto-created |
| Operator assessments | 0 | ≥30 | BLOCKING — must start today |
| `confirmed` | 0 | — | — |
| `rejected` | 0 | — | — |
| `needs_review` | 0 | — | — |
| `pending` | ~21 | < 3 | All records pending |
| pending_rate | 1.0 | < 0.10 | Gate 1 threshold |
| agreement_rate | null | ≥ 0.70 | Gate 2 threshold |
| disagreement_rate | null | < 0.30 | — |
| mean_confidence | varies | ≥ 0.50 | — |
| agreement_rate by state | null (all) | — | All states pending |
| inference_by_version | `"0.1": N` | — | Single version |

---

## Evidence Gate Progress

| Gate | Condition | Progress | Status |
|---|---|---|---|
| Gate 1 | ≥30 assessed, pending_rate < 0.10 | 0/30 days | ❌ |
| Gate 2 | agreement_rate ≥ 0.70 | null | ❌ |
| Gate 3 | Calibration evaluated | Not started | ❌ |
| Gate 4 | Failure analysis complete | Not started | ❌ |
| Gate 5 | Competitive benchmark | SAP-001 planned | ❌ |

---

## Scientific Risk Register Summary (Day 0)

| Risk | Likelihood | Impact | Status |
|---|---|---|---|
| RISK-001 Sparse validation data | HIGH | CRITICAL | Active |
| RISK-002 Operator bias | MEDIUM | HIGH | Latent |
| RISK-003 Confidence miscalibration | MEDIUM | HIGH | Not evaluable |
| RISK-004 Constraint threshold | MEDIUM | MEDIUM | Not evaluable |
| RISK-005 Missing signals | HIGH | MEDIUM | Permanent |
| RISK-006 Sleep dating (BUG-009) | HIGH | MEDIUM | Deferred |
| RISK-007 Single-user generalization | CERTAIN | HIGH (future) | Accepted |
| RISK-008 RHR coverage gap | HIGH | MEDIUM | Monitored |

---

## Weekly KPI Tracking Template

Copy this section each week and fill in current values.

**Week of: [DATE]**

| KPI | Day 0 | Week N | Δ | Notes |
|---|---|---|---|---|
| Total observations | 1,166 | | | |
| Valid observations | 1,144 | | | |
| Steps coverage % | 100% | | | |
| Sleep coverage % | 75% | | | |
| RHR coverage % | 43% | | | |
| Operator assessments total | 0 | | | |
| pending_rate | 1.0 | | | |
| agreement_rate | null | | | |
| disagreement_rate | null | | | |
| mean_confidence | — | | | |
| Non-data-gap state days | 0 | | | |
| Constraint firing events | 0 | | | |
| DB backups run | 0 | | | |

---

## Infrastructure Costs (Day 0)

| Resource | Tier | Cost | Limit |
|---|---|---|---|
| Render Web Service | Free | $0/mo | Spins down after 15min idle |
| Render PostgreSQL | Free | $0/mo | No automatic backups; 1GB storage |
| GitHub | Free | $0/mo | Public repo |
| Android device | S24 Ultra | Already owned | Debug APK only |

**Upgrade trigger:** Multi-user phase (Phase 6) — switch to Render paid tier for persistent web service + automatic database backups.
