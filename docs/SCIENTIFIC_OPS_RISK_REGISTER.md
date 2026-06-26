# Vigil — Scientific Risk Register

**Version:** 1.0
**Date:** 2026-06-26
**Status:** Active — update as operational evidence accumulates

This register tracks scientific risks to the validity of Vigil's Human State inferences. A risk is a condition that could systematically undermine the correctness or trustworthiness of the evidence Vigil generates. Each risk includes the evidence required to resolve or reclassify it.

---

## Risk Classification

| Likelihood | Meaning |
|---|---|
| HIGH | Likely to occur or already observed |
| MEDIUM | Plausible; could occur under common conditions |
| LOW | Possible but requires specific circumstances |

| Impact | Meaning |
|---|---|
| CRITICAL | Invalidates core inference claims |
| HIGH | Systematically biases agreement/disagreement findings |
| MEDIUM | Affects a subset of states or constraint evaluations |
| LOW | Cosmetic or minor data quality issue |

---

## RISK-001 — Sparse Validation Data

**Description:** Scientific Operations requires operator-assessed validation records to produce evidence. If the operator fails to assess consistently, the agreement dataset will be too sparse to support statistical conclusions.

**Likelihood:** HIGH (0 assessments recorded at Day 0)

**Impact:** CRITICAL — without assessments, agreement_rate stays null and no findings are possible

**Current state:** 0 assessments, all records `pending`

**Mitigation:**
- Daily SOP in `docs/SCIENTIFIC_OPS_SOP.md` — assessment is evening protocol step 5
- Validation workflow is ≤5 minutes per day
- Priority 1 in Operational Priorities (Current Phase Notion page)

**Evidence to resolve:** ≥30 consecutive days of operator-assessed records with < 10% pending rate

**Review trigger:** If < 5 assessments after 14 days of operation → escalate urgency

---

## RISK-002 — Operator Bias in Assessments

**Description:** The operator (who is also the subject) may unconsciously bias assessments toward `confirmed` to validate the system, or toward `rejected` due to over-familiarity with their own state vs. the sensor-derived view. Either bias corrupts the agreement signal.

**Likelihood:** MEDIUM

**Impact:** HIGH — systematic bias makes agreement_rate meaningless as a calibration metric

**Current state:** No assessments yet; bias risk is latent

**Mitigation:**
- Assessment protocol requires explicit reasoning in `operator_assessment` text field
- Vague assessments ("Correct", "Wrong") are flagged in SOP as low scientific value
- Blind to prior assessments during daily review (check state first, assess, then look at history)
- Monthly review compares assessment reasoning quality over time

**Evidence to resolve:** Qualitative review of assessment text at ≥30 records — are reasons consistent with the sensor evidence? Are confirmations and rejections both explained? Seek external review of ≥10 records by a colleague.

---

## RISK-003 — Confidence Miscalibration

**Description:** The Human State Engine scales confidence as `min(1.0, valid_days / FULL_CONFIDENCE_DAYS)`. This formula assumes confidence should grow linearly with baseline history, but higher confidence could still correlate with *lower* agreement if the baseline period captures an atypical period.

**Likelihood:** MEDIUM

**Impact:** HIGH — if high-confidence inferences are systematically wrong, confidence is anti-calibrated

**Current state:** Not evaluable — no agreement data

**Mitigation:**
- Confidence distribution tracked in agreement summary (4 buckets: high ≥0.75, medium ≥0.5, low ≥0.25, very_low < 0.25)
- Engineering review trigger: "confidence-accuracy anticorrelation statistically significant (p < 0.05) over ≥30 assessed days"

**Evidence to resolve:** ≥30 assessed records → compute Pearson correlation between confidence and correct_inference (0/1). If r < 0 and p < 0.05: reclassify to CRITICAL and open engineering review.

---

## RISK-004 — Constraint Threshold Accuracy

**Description:** The 6 constraint rules fire at |z| ≥ 1 SD from personal baseline. The 1-SD threshold was chosen as reasonable for a single-user system, but may be too sensitive (many false positives) or too coarse (misses meaningful deviations).

**Likelihood:** MEDIUM

**Impact:** MEDIUM — wrong threshold produces wrong contributing_constraints → wrong state in borderline cases

**Current state:** 0 constraints firing for canonical user (no valid baselines yet). Legacy user shows constraint history.

**Mitigation:**
- Threshold documented and frozen at v0.1 — changes require ADR + evidence
- Operator assessments note which constraints appeared in rejected records
- Agreement Engine tracks per-state breakdown (potential to identify which states have highest disagreement)

**Evidence to resolve:** ≥30 assessed records → identify which contributing_constraints appear most frequently in `rejected` records. If a single constraint is responsible for ≥30% of disagreements → open ADR for threshold review.

---

## RISK-005 — Missing Physiological Signals

**Description:** Active energy (calories burned) is absent due to Samsung OEM siloing. HRV is not collected. The Human State Engine uses only sleep duration, steps, and resting HR. These three signals may be insufficient to distinguish physiologically similar states (e.g., `normal` vs. early `recovery_deficit`).

**Likelihood:** HIGH (active_energy permanently absent on current hardware)

**Impact:** MEDIUM — reduces discriminating power between adjacent states; some `normal` inferences may be `recovery_deficit` at low energy deficit

**Current state:** `active_energy` 0 observations (ARCHIVE). HRV not collected. SpO2 not collected.

**Mitigation:**
- strain_overshoot requires steps_high — partially compensates for absent caloric data
- Operator assessments can identify cases where "steps were high but I wasn't straining"
- RHR fallback (BPM_MIN 02:00–06:00) partially compensates for absent RestingHR

**Evidence to resolve:**
- For active_energy: monitor Samsung Health API changelog for behavior change
- For HRV: when Samsung Health starts writing HRV to Health Connect → evaluate Phase 4 entry criteria
- For missing signal impact: ≥30 assessments → identify how often `normal` is rejected with operator note suggesting undetected strain

---

## RISK-006 — Sleep Dating Ambiguity (BUG-009)

**Description:** Sleep records are currently dated by sleep-start timestamp, not physiological-night anchor (the night they belong to). Sleep ending at 08:00 on Tuesday gets attributed to Tuesday rather than the Monday night it represents. This can cause duplicate or missing sleep metrics on adjacent days.

**Likelihood:** HIGH (confirmed bug)

**Impact:** MEDIUM — affects sleep-based constraints on edge-case days; `sleep_short` / `sleep_long` may fire on the wrong day

**Current state:** BUG-009 OPEN, deferred to Phase 3

**Mitigation:**
- Deferred because impact on agreement has not been demonstrated
- 75% sleep coverage suggests sleep data is generally present — ambiguity affects edge cases
- Operator notes should flag "sleep attribution seemed off" in validation records

**Evidence to resolve:** ≥14 assessed records → identify any `rejected` records where the operator's note references incorrect sleep day attribution. If ≥3 such records found → promote BUG-009 to evidence-gated fix with concrete case evidence.

---

## RISK-007 — Single-User Generalization Risk

**Description:** All Vigil findings are based on data from a single operator-subject (surgical resident, S24 Ultra, specific lifestyle). Thresholds, constraint weights, and cascade priorities may not generalize to other users.

**Likelihood:** CERTAIN (by design — single-user phase)

**Impact:** HIGH for future multi-user claims; LOW for current single-user scientific operations

**Current state:** Explicitly accepted — Phase 6 (multi-user) is gated on full Intelligence Layer validation

**Mitigation:**
- All findings are explicitly framed as "single-user evidence" during Scientific Operations phase
- Evidence Gates require single-user validation before multi-user expansion
- Constraint Engine and HSE are designed for personalization (baseline is per-user)

**Evidence to resolve:** Out of scope for Scientific Operations. Gate is Phase 6 (multi-user validation).

---

## RISK-008 — RHR Fallback Coverage Gap

**Description:** Resting HR is computed via BPM_MIN (minimum HeartRateRecord between 02:00–06:00). If the user does not wear the watch during sleep, or if heart rate is not recorded in that window, RHR is absent. Current coverage: 43% (9/21 days).

**Likelihood:** HIGH (43% gap rate confirmed)

**Impact:** MEDIUM — `data_gap` state fires on days where RHR is missing (if it's a BASELINE_METRIC)

**Current state:** 43% coverage. No improvement path available (hardware limitation for native RestingHR; BPM_MIN is the permanent fallback).

**Mitigation:**
- Wearing watch consistently during sleep is the only mitigation available
- Operator should note "watch not worn" in validation records on gap days
- RHR threshold for BASELINE_METRIC: MIN_VALID_DAYS=3 (low bar)

**Evidence to resolve:** Track whether RHR coverage improves with consistent watch-wearing behavior. If coverage reaches ≥70% of days → risk reclassified to LOW. If stays ≤43% with consistent wear → may indicate physiological gap (no HR in 02:00–06:00 window on light-sleep nights).

---

## Risk Summary Table

| Risk | Likelihood | Impact | Status | Gating Evidence |
|---|---|---|---|---|
| RISK-001 Sparse validation data | HIGH | CRITICAL | Active — BLOCKING | ≥30 assessed days |
| RISK-002 Operator bias | MEDIUM | HIGH | Latent — watch | ≥30 records + external review |
| RISK-003 Confidence miscalibration | MEDIUM | HIGH | Not evaluable | ≥30 records + correlation test |
| RISK-004 Constraint threshold | MEDIUM | MEDIUM | Not evaluable | ≥30 records + rejection analysis |
| RISK-005 Missing signals | HIGH | MEDIUM | Permanent (OEM) | Monitor Samsung API |
| RISK-006 Sleep dating (BUG-009) | HIGH | MEDIUM | Open — deferred | ≥14 records + attribution errors |
| RISK-007 Single-user generalization | CERTAIN | HIGH (future) | Accepted by design | Phase 6 scope |
| RISK-008 RHR coverage gap | HIGH | MEDIUM | Monitored | ≥70% coverage target |

---

## Register Maintenance

Update after each monthly engineering review:
- Reclassify likelihood based on accumulated evidence
- Reclassify impact based on observed disagreement patterns
- Add new risks discovered through operational data
- Close risks with sufficient mitigating evidence (move to RESOLVED section)

**First update checkpoint:** After 30 operator-assessed days. Review all MEDIUM+ risks against actual agreement data.
