# Task 7 — Engineering Freeze Report

**Date:** 2026-06-26
**Sprint:** Engineering Hardening (Final Engineering Sprint)

This document is the canonical classification of all remaining engineering tasks. It replaces ad-hoc task lists. Update only with operational evidence.

---

## Freeze Principles

1. **No implementation without evidence.** Evidence = ≥30 operator-assessed validation records with a measurable disagreement pattern.
2. **Frozen systems cannot change without ADR + evidence.** See CLAUDE.md for the frozen list.
3. **Bug fixes are permitted** with test evidence. They do not require the 30-day evidence gate.
4. **New read-only analytics endpoints** are permitted with test evidence.
5. **No ML, LLM, prediction, or personalization** at any time during Scientific Operations.

---

## Classification Legend

| Class | Meaning | Can start without evidence? |
|---|---|---|
| **IMMEDIATE** | Do now — operational risk or safety | Yes |
| **QUARTERLY** | Do after ≥30 days of operational evidence | No |
| **FUTURE** | Do after specific phase prerequisites | No |
| **FROZEN** | Do not implement — requires ADR + evidence | No |
| **ARCHIVE** | Will not implement — externally blocked or superseded | Never |

---

## IMMEDIATE (Do Now — No Evidence Gate)

These are pre-conditions for clean Scientific Operations. Not features.

| Task | Reason | Owner |
|---|---|---|
| Run `backend/scripts/backup_db.py` and confirm output | Data loss risk — no backups exist | Operator |
| Begin operator assessments (PATCH /validation/{id}) | Agreement engine is null until first assessment | Operator |
| Set `VIGIL_DB_URL` env var in local shell profile | Scripts sanitized this sprint — set the var | Operator |
| Daily: `curl https://vigilbridge.onrender.com/health` | Manual monitoring — no automated alternative | Operator |
| (Optional) Rotate DB password in Render dashboard | Credential appeared in session context this sprint | Operator |

---

## Bug Fixes — Permitted Without Evidence Gate (Test Required)

| Bug | ID | Priority | Resolution |
|---|---|---|---|
| UnavailableScreen magic int literals | BUG-003 | Low | Use `HealthConnectClient.SDK_UNAVAILABLE` constants. 2-line fix. |
| `collectAsState()` lifecycle waste | BUG-005 | Low | Add `lifecycle-runtime-compose` dep, replace call. Negligible impact. |
| versionName = "1.0" cosmetic mismatch | BUG-007 | Cosmetic | Update `versionCode`/`versionName` in `build.gradle.kts` |
| `unknown` null rows marked `valid` | New (this sprint) | Low | Extractor fallback: set `data_quality_status="probe"` for unrecognized types |

**BUG-009 and BUG-010 remain deferred.** See below.

---

## QUARTERLY (After ≥30 Days of Operator-Assessed Records)

These require measurable operational evidence before implementation is justified.

| Task | Evidence Required | What to Look For |
|---|---|---|
| Insight Engine v0.1 (read-only analytics) | ≥30 assessed records, measurable agreement/disagreement patterns | Which constraint rules most often produce incorrect inferences |
| 7-day baseline period (in addition to 30d) | ≥14 assessed records showing baseline sensitivity difference | Does 7d baseline produce better agreement than 30d? |
| BUG-009 sleep dating (physiological-night anchor) | ≥21 days of sleep data; confirm date attribution errors affect Human State output | Disagreements traceable to wrong-day attribution |
| BUG-010 sleep UX (time-in-bed on dashboard) | User feedback or operator assessment noting confusion | Dashboard misreads leading to disagreements |
| Coverage improvement for RHR | Identify specific days with missing RHR; trace to device sleep pattern | RHR gaps causing `data_gap` states that should be `normal` |
| Trend analytics in operator review | After Insight Engine shows trend-agreement correlation | Trend data improves inference agreement |

---

## FUTURE (Phase-Gated)

These are gated on specific future phases. Do not design or implement early.

| Task | Phase Gate | Prerequisite |
|---|---|---|
| Circadian Engine (SRI, social jetlag, DLMO proxy) | Phase 3 | BUG-009 resolved + ≥21 days `sleep_start_hour` data |
| Sleep phase shift detection | Phase 3 | Circadian Engine data validated |
| Recovery Engine (severity-weighted cascade, consecutive-day weighting) | Phase 4 | Circadian Engine live + HRV metric available |
| HRV-gated confidence | Phase 4 | Hardware confirms HRV export via HC |
| Composite recovery score (0–100) | Phase 4 | Recovery Engine validated |
| Intelligence Layer (Claude API narrative summaries) | Phase 5 | Recovery Engine validated on ≥30 confirmed records |
| Multi-user auth (JWT, user registration, data isolation) | Phase 6 | Intelligence layer validated on single user |
| FHIR export | Future | Multi-user confirmed + healthcare integration required |

---

## FROZEN (Architecture — Do Not Change Without ADR + Evidence)

These components are frozen. No modifications, extensions, or rewrites without:
1. Operational evidence of a specific failure mode
2. A written ADR with the proposed change and justification
3. Peer review

| System | Frozen | What Frozen Means |
|---|---|---|
| Constraint Engine (6 rules) | v0.1 | No new rules, no threshold changes, no direction changes |
| Human State Estimator (5-state cascade) | v0.1 | No new states, no cascade order changes |
| Validation Engine | v0.1 | No new status vocabulary, no operator flow changes |
| Agreement Engine | v0.1 | No formula changes, no new dimensions without test evidence |
| Persistence Model (7 tables, 7 migrations) | v1.0 | No new tables without ADR, no breaking schema changes |
| API v1.0 (16 endpoints) | v1.0 | No breaking changes; additive read-only permitted with tests |
| Evidence Model (JSONB structure) | v1.0 | No restructuring of constraint.evidence or evidence_provenance |
| Version constants (engine=0.1, constraint=0.1, evidence=0.1) | v0.1 | No increment without deliberate version bump decision |

---

## ARCHIVE (Will Not Implement)

These tasks are permanently deferred or externally blocked.

| Task | Reason |
|---|---|
| Fix `active_energy` absence | Samsung Health `ActiveCaloriesBurnedRecord` OEM siloing — no code fix possible. Only resolvable by Samsung |
| Fix native `RestingHeartRateRecord` | Samsung Health does not write `RestingHeartRateRecord` to HC on S24 Ultra. Fallback (BPM_MIN) is the permanent solution until Samsung changes behavior |
| `pm grant` for HC permissions | Android security model prohibits this. Permissions require manual user grant — by design |
| Background HC reads without `READ_HEALTH_DATA_IN_BACKGROUND` | OS security requirement — cannot bypass |
| Remove corrupt `StepsRecord` from HC | HC does not expose delete-by-ID API to apps. Only user action via HC settings can delete it |

---

## Summary

| Class | Count |
|---|---|
| IMMEDIATE (do now) | 5 items |
| Bug fixes permitted | 4 bugs |
| QUARTERLY (evidence-gated) | 6 items |
| FUTURE (phase-gated) | 8 items |
| FROZEN | 8 systems |
| ARCHIVE | 5 items |

**The path forward is clear: operate first, improve later, with evidence.**
