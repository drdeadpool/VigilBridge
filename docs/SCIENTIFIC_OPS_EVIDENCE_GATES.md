# Vigil — Evidence Gates Specification

**Version:** 1.0
**Date:** 2026-06-26
**Status:** Active — governs all future engineering work

---

## Purpose

No feature work begins without a gate condition being met. This specification defines the evidence required to trigger each major phase of future development. Gates are not calendar-based. They are evidence-based.

A gate is met when operational data — not engineering judgment, not product intuition — demonstrates that a specific threshold has been crossed.

---

## Gate Authority

Gate conditions are verified by the Lead Engineer using production data from `GET /agreement/{user_id}` and `GET /validation`. Disagreements about whether a gate is met must be resolved with data, not discussion.

---

## Gate 1 — Minimal Operational Evidence

**Condition:** ≥30 consecutive days of operator-assessed validation records with `pending_rate < 0.10`

**Why 30 days:** Minimum window for weekly pattern detection (≥4 full cycles). Below 30 days, agreement statistics are too sparse to distinguish signal from noise.

**Why pending_rate < 0.10:** Missing assessments bias agreement_rate upward (pending records are excluded from agreement calculation). Gaps must be < 10% to maintain validity.

**Verified by:**
```bash
curl "https://vigilbridge.onrender.com/agreement/37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
# Check: total >= 30, pending_rate < 0.10
```

**What it unlocks:**
- All QUARTERLY engineering items in ENGINEERING_FREEZE_REPORT.md
- Meaningful interpretation of agreement_rate, disagreement_rate
- First pass of Risk Register review (all MEDIUM+ risks evaluable)
- Gate 2 and Gate 3 become evaluable

**Current status:** NOT MET (total: ~1, pending_rate: 1.0)

**Estimated timeline:** 30 days from first consistent daily assessment

---

## Gate 2 — Agreement Rate Threshold

**Condition:** `agreement_rate ≥ 0.70` over ≥30 assessed days

**Why 0.70:** Below 70% agreement, more than 30% of inferences are being rejected by the operator. At this level, the system's reliability is insufficient for clinical context (surgical resident decision support). The threshold is deliberately set at 70% as the minimum acceptable floor, not a target.

**Interpretation:**
- agreement_rate ≥ 0.70: Human State Engine is performing at minimum acceptable accuracy
- agreement_rate ≥ 0.80: Strong operational performance; engineering review may proceed with smaller scope
- agreement_rate < 0.70: Engineering review triggered — identify root cause before any other feature work

**Verified by:**
```bash
curl "https://vigilbridge.onrender.com/agreement/37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
# Check: agreement_rate >= 0.70
```

**What it unlocks:**
- Insight Engine v0.1 development (evidence shows the engine is worth analyzing further)
- 7-day baseline evaluation (evidence justifies experimenting with shorter windows)
- Confidence calibration analysis (Gate 3)

**Current status:** NOT MET (agreement_rate: null)

---

## Gate 3 — Confidence Calibration Evaluated

**Condition:** ≥30 assessed records + Pearson correlation between confidence and correct_inference computed, result documented

**This gate does not require a specific correlation value** — it requires that calibration has been measured and the result documented. The measurement itself is the gate. The result informs future engineering.

**How to evaluate:**
1. Extract from validation_records: `(confidence, is_correct)` pairs where `is_correct = 1 if validation_status='confirmed' else 0`
2. Compute Pearson r and p-value
3. Document in the Risk Register (RISK-003) and propose next action based on result

**Possible outcomes:**
- r > 0, p < 0.05: Confidence correctly tracks accuracy → ACCEPTABLE, no immediate action
- r ≈ 0: Confidence uncorrelated with accuracy → INVESTIGATE, consider confidence formula revision (requires ADR)
- r < 0, p < 0.05: Confidence anti-calibrated → CRITICAL, engineering review triggered immediately

**What it unlocks:**
- Confidence formula improvements (if evidence demands it)
- Phase 3 planning (Circadian Engine needs calibrated confidence infrastructure)

**Current status:** NOT MET (requires Gate 1 first)

---

## Gate 4 — Failure Mode Analysis Completed

**Condition:** ≥30 assessed records + systematic analysis of all `rejected` records completed, with at least one identified failure pattern (or confirmed absence of pattern)

**Analysis procedure:**
1. Extract all `rejected` validation records
2. Group by `inferred_state`
3. For each group: list contributing_constraints, today_values, operator_assessment text
4. Identify: is there a recurring pattern (same constraint always wrong? same state always rejected? specific sensor condition predicts rejection)?
5. Document findings as either: "pattern found: [description]" OR "no systematic pattern detected at current N"

**Why this gates future work:** Feature additions to a system with an unknown failure mode risk masking that failure mode. The failure analysis must precede new capability development.

**What it unlocks:**
- BUG-009 fix (if rejection analysis shows sleep dating errors)
- RHR coverage improvement investigation (if rejection analysis shows RHR gaps predict rejection)
- Constraint threshold review (if specific constraint appears in ≥30% of rejections)
- Phase 3 (Circadian Engine) planning

**Current status:** NOT MET (requires Gate 1 first)

---

## Gate 5 — Competitive Benchmark Review Completed

**Condition:** ≥1 structured review of WHOOP/Oura/PHA/Firstbeat inference methodology since Scientific Operations launch, documented with specific takeaways for Vigil constraint or state design

**What "structured" means:** Not casual reading. A TAP-style review answering: What signals do they use? What states do they infer? What thresholds do they publish? What does their validation evidence show? What would this imply for Vigil's constraint rules?

**This gate is not a minimum to start operations.** It is a prerequisite before any significant redesign of the Constraint Engine or Human State Engine (which are currently frozen).

**What it unlocks:**
- ADR consideration for constraint changes (requires benchmark evidence)
- Phase 4 Recovery Engine design (must be informed by how competitive systems handle recovery)
- Phase 5 Intelligence Layer design

**Current status:** NOT MET. SAP-001 (Google PHA analysis) was initiated but is pending completion. SAP-002 (WHOOP), SAP-003 (Oura) are planned.

---

## Gate 6 — Phase 3 Readiness (Circadian Engine)

**Condition:** ALL of the following:
- Gate 1 met (≥30 assessed days)
- Gate 4 met (failure analysis completed)
- BUG-009 (sleep dating) fixed and tested
- ≥21 consecutive days of `sleep_start_hour` data in observations table
- At least one Scientific Operations monthly literature review completed (circadian science)

**What it unlocks:** Phase 3 — Circadian Engine development (SRI, social jetlag, DLMO proxy)

**Current status:** NOT MET

---

## Gate 7 — Phase 4 Readiness (Recovery Engine)

**Condition:** ALL of the following:
- Gate 6 met (Phase 3 complete)
- Circadian Engine validated with ≥30 assessed days including circadian signal
- HRV data available via Health Connect (hardware capability confirmed)
- Gate 5 met (competitive benchmark review)
- ADR written and accepted for recovery scoring methodology

**What it unlocks:** Phase 4 — Recovery Engine (severity-weighted cascade, consecutive-day weighting, composite recovery score)

**Current status:** NOT MET

---

## Gate 8 — Phase 5 Readiness (Intelligence Layer)

**Condition:** ALL of the following:
- Gate 7 met (Phase 4 complete — Recovery Engine validated)
- ≥30 confirmed recovery scores
- Claude API integration design reviewed and ADR written
- Operator has provided ≥5 examples of desired narrative output format

**What it unlocks:** Phase 5 — Intelligence Layer (narrative summaries, decision context, daily brief)

**Current status:** NOT MET

---

## Gate Summary

| Gate | Condition | Status | Unlocks |
|---|---|---|---|
| Gate 1 | ≥30 assessed days, pending_rate < 0.10 | ❌ NOT MET | All QUARTERLY work |
| Gate 2 | agreement_rate ≥ 0.70 | ❌ NOT MET | Insight Engine, 7d baseline |
| Gate 3 | Confidence calibration measured | ❌ NOT MET (needs Gate 1) | Confidence improvements |
| Gate 4 | Failure mode analysis complete | ❌ NOT MET (needs Gate 1) | BUG-009, constraint review |
| Gate 5 | Competitive benchmark review | ❌ NOT MET | ADR for redesign work |
| Gate 6 | Phase 3 readiness | ❌ NOT MET | Circadian Engine |
| Gate 7 | Phase 4 readiness | ❌ NOT MET | Recovery Engine |
| Gate 8 | Phase 5 readiness | ❌ NOT MET | Intelligence Layer |

**Current priority:** Close Gate 1. Nothing else moves until 30 days of assessed records exist.

---

## Gate Bypass Protocol

No gate may be bypassed without:
1. A written justification referencing operational evidence
2. An ADR documenting the risk of bypassing
3. Explicit decision logged in the Project Decision Log

"We think it would be useful" does not meet the bypass threshold. Operational evidence does.
