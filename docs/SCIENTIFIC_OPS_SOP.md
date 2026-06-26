# Vigil — Scientific Operations Standard Operating Procedure

**Version:** 1.0
**Date:** 2026-06-26
**Status:** Active — Scientific Operations Phase

This SOP governs daily operation of Vigil as a production Human State Intelligence platform. The goal is not to collect data — it is to generate trustworthy evidence about the accuracy and failure modes of the Human State Engine.

---

## Core Principle

Every operator assessment is a scientific observation. Record it with the same discipline you apply to clinical notes. Vague assessments produce vague evidence.

---

## Morning Protocol (≤10 minutes)

### 1. Verify Overnight Sync

Check that WorkManager fired and data reached the backend.

```bash
# Backend alive?
curl https://vigilbridge.onrender.com/health
# Expected: {"status":"ok","database":"connected"}
# If 30s delay: free-tier cold start — wait and retry

# New observations since last check?
curl https://vigilbridge.onrender.com/stats \
  -H "X-Api-Key: $READ_API_KEY"
# Check: total_observations increased vs yesterday
```

If observation count did not increase: check Android logcat for OutboxUploadWorker errors. Common causes: device offline, background-sync restricted by battery optimizer.

### 2. Verify Ingestion Health

```bash
curl https://vigilbridge.onrender.com/observations/recent \
  -H "X-Api-Key: $READ_API_KEY"
# Check: latest_timestamp is within the last 2 hours
# Check: valid observations present for sleep, steps, resting_hr_bpm
```

**Flags to note in daily log:**
- Missing sleep data (device not worn overnight)
- Missing RHR (no HeartRateRecord in 02:00–06:00 window — common on low-activity nights)
- Observation count anomalies

### 3. Check Data Quality

```bash
curl "https://vigilbridge.onrender.com/baselines/37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
# Check: valid_days ≥ 3 for sleep_duration_hours, steps_today, resting_hr_bpm
# If valid_days < 3: Human State will be data_gap — expected behavior
```

---

## Evening Protocol (≤15 minutes)

### 4. Review Inferred Human State

```bash
curl "https://vigilbridge.onrender.com/state/37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
```

Note:
- `inferred_state` — what Vigil concluded
- `contributing_constraints` — which rules fired
- `confidence` — 0.0 to 1.0 (scales with valid_days / 14)
- `evidence_refs.today_values` — actual sensor readings used

Compare the inferred state to your subjective experience of the day. This is the scientific judgment you are about to record.

### 5. Complete Operator Assessment

Get the pending validation record for today:

```bash
curl "https://vigilbridge.onrender.com/validation?user_id=37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
# Find the record with validation_status="pending" for today's date
# Note the {id}
```

Record your assessment:

```bash
curl -X PATCH "https://vigilbridge.onrender.com/validation/{id}" \
  -H "X-Api-Key: $READ_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "validation_status": "confirmed",
    "operator_assessment": "Subjective state agrees. Sleep was genuinely short and HR was elevated from evening exercise.",
    "notes": "Constraint sleep_short + rhr_elevated both correct. Felt fatigued this morning."
  }'
```

**Assessment vocabulary:**
- `confirmed` — Vigil's inference agrees with your subjective state
- `rejected` — Vigil's inference does not reflect your experienced state; explain why
- `needs_review` — Uncertain; flag for later review with more context

**Write quality operator assessments.** One sentence of reasoning is the minimum. Examples:
- ✅ "Confirmed. Short sleep (5.5h) due to night call. RHR elevated to 68 — physiologically correct."
- ✅ "Rejected. Vigil inferred recovery_deficit but I felt rested. Steps low due to scheduled rest day, not fatigue. RHR normal."
- ❌ "Correct." (no reasoning — low scientific value)
- ❌ "Wrong." (no reasoning — low scientific value)

### 6. Record Anomalies

If anything unexpected occurred, record it as a note on the validation record. Examples:
- Device not worn during sleep → `"notes": "Watch not worn — sleep and RHR missing. Steps from pocket carry only."`
- Illness, travel, high stress → `"notes": "Travel day. Steps inflated by airport walking. Not a typical active day."`
- Sensor anomaly → `"notes": "Heart rate sensor produced outlier readings 03:00–04:00. BPM_MIN may be affected."`

Anomaly notes are scientific observations. They help distinguish signal from noise during agreement analysis.

### 7. Review Agreement / Confidence

```bash
curl "https://vigilbridge.onrender.com/agreement/37c5d374-d624-404f-ae6f-50a6781601bf" \
  -H "X-Api-Key: $READ_API_KEY"
```

**Meaningful milestones:**
- ≥5 assessments: first directional signal on agreement_rate
- ≥14 assessments: weekly pattern detectable
- ≥30 assessments: statistically meaningful; triggers first engineering review

---

## Weekly Protocol (≤30 minutes, recommend Sunday)

### 8. Review Agreement Trends

```bash
curl "https://vigilbridge.onrender.com/agreement/37c5d374-d624-404f-ae6f-50a6781601bf/by-state" \
  -H "X-Api-Key: $READ_API_KEY"
```

Note per-state agreement rates. Which states show the most disagreement? Which constraints most often appear in rejected records?

### 9. Review Constraint Performance

```bash
curl "https://vigilbridge.onrender.com/state/37c5d374-d624-404f-ae6f-50a6781601bf/history" \
  -H "X-Api-Key: $READ_API_KEY"
```

Questions to answer:
- Which states appeared this week? Was the distribution expected?
- Were any constraints misfiring (appear in rejected records repeatedly)?
- Did confidence track felt-certainty about the inferred state?

### 10. Run Database Backup

```bash
export VIGIL_DB_URL="postgresql://..."
cd C:\Users\kaliv\AndroidStudioProjects\VigilBridge
python backend/scripts/backup_db.py
# Verify: output shows row counts for all 7 tables
# Verify: MANIFEST.json created in backup dir
```

Store backup output directory. Keep ≥4 weeks of backups locally.

### 11. Review Health Check

```bash
curl https://vigilbridge.onrender.com/health
```

Log response. If database shows disconnected: check Render dashboard for database status.

---

## Monthly Protocol (≤2 hours)

### 12. Competitive Intelligence Review

Review any new publications or product changes from:
- WHOOP, Oura Ring, Garmin Firstbeat — algorithm updates, new health features
- Google PHA — Health Connect API changes, new record types
- Samsung Health — any change to OEM siloing behavior (active_energy, native RHR)

Note: if Samsung begins writing `ActiveCaloriesBurnedRecord` or `RestingHeartRateRecord` to Health Connect, this is an actionable event. Revisit the ARCHIVE classification for those capabilities.

### 13. Scientific Literature Review

One paper per month minimum. Focus areas:
- Physiological cascades: sleep × HRV × load interactions
- Wearable accuracy studies: how well do consumer wearables track sleep stages, HRV, RHR?
- State inference: latent state models, circadian disruption markers
- Recovery science: what does "recovery" actually mean physiologically?

Log findings against the assumption register. Each paper either strengthens or weakens existing assumptions.

### 14. Evidence-Driven Engineering Review

Prerequisite: ≥30 operator-assessed days.

Gather:
- Agreement rate per state (confirmed vs. rejected breakdown)
- Confidence distribution vs. correctness correlation
- Constraint firing patterns (which rules fire most? which appear in rejected records?)
- Any systematic failure pattern meeting the engineering review triggers from CLAUDE.md

Ask: **What operational evidence justifies any proposed change?**

If no pattern meets the threshold: note the week's observations and defer. The engine does not change based on instinct.

---

## Engineering Review Triggers (Reference)

A full engineering review is warranted when any of these thresholds are met:

| Trigger | Threshold |
|---|---|
| Consistent failure pattern | ≥5 consecutive `rejected` records, same inferred_state |
| Systematic constraint misfiring | ≥10 `rejected` records sharing same contributing_constraint |
| Confidence-accuracy anticorrelation | Statistically significant (p < 0.05) over ≥30 assessed days |
| OEM sensor change | Any — verify fallbacks still work |
| New sensor data available (HRV, SpO2) | Any — evaluate against Phase 3/4 entry criteria |

---

## Data Quality Red Flags

Log these in the weekly review:

| Condition | Action |
|---|---|
| observation count did not increase overnight | Check WorkManager / OutboxUploadWorker |
| sleep data missing for ≥3 consecutive days | Note in validation records; affects Human State baseline |
| RHR missing for ≥7 consecutive days | Note; affects rhr_elevated/rhr_suppressed constraint quality |
| state_estimate shows data_gap despite ≥3 days of data | Investigate baseline recompute — check /baselines endpoint |
| validation record count does not match ingest days | Check ingest → state → validation hooks |

---

## Emergency Procedures

### Backend Unresponsive

1. `curl https://vigilbridge.onrender.com/health`
2. If timeout: Render may be spinning up (free tier, ~30s cold start). Wait 60s and retry.
3. If still failing: check Render dashboard for service status / recent deploy failures
4. If deploy failed: check GitHub Action / Render build logs. Last known-good commit: see CLAUDE.md session start protocol.

### Database Connection Error

Check Render Postgres dashboard. Free-tier databases can experience transient connectivity issues. If persistent, check connection limit (free tier: 25 connections max).

### Data Loss Scenario

1. Stop all ingestion (disable WorkManager on device if needed)
2. Run `backend/scripts/backup_db.py` immediately to capture current state
3. Assess what was lost and when
4. Do not attempt migration or recovery without a verified backup
