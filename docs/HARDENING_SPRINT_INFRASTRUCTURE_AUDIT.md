# Task 3 — Infrastructure Audit

**Date:** 2026-06-26
**Sprint:** Engineering Hardening (Final Engineering Sprint)

---

## Summary

One critical gap: **no automatic database backups**. All other infrastructure components are correctly configured and operational.

---

## Component Audit

### Web Service (Render Free Tier)

| Item | Config | Assessment |
|---|---|---|
| Service type | Web (Docker) | ✅ Correct |
| Dockerfile | `backend/Dockerfile` | ✅ Present |
| Docker context | `backend/` | ✅ Correct |
| Plan | Free | ⚠️ Spins down after 15 min idle (~30s cold start) |
| Health check path | `/health` | ✅ Present and responding |
| Auto-deploy | GitHub main → Render | ✅ Active |
| Startup command | `alembic upgrade head && uvicorn ...` | ✅ Migrations run before traffic |

**Cold-start risk:** Render free tier suspends after 15 minutes of inactivity. First request experiences ~30s delay. For single-user scientific use this is acceptable. For production medical use, upgrade to a paid plan.

---

### Database (Render Free Tier PostgreSQL)

| Item | Status | Notes |
|---|---|---|
| Engine | PostgreSQL 16 (Render managed) | ✅ |
| Tables | 8 (7 app + alembic_version) | ✅ |
| Migrations applied | 7/7 at head `a9f4e2d1b6c8` | ✅ |
| Total observations | 1,166 (1,144 valid) | ✅ |
| Connection | `DATABASE_URL` from Render env injection | ✅ |
| Storage estimate | ~50MB (text-heavy JSONB) | Well within free 1GB limit |
| **Automatic backups** | **❌ NONE** | **CRITICAL GAP — see below** |

---

## CRITICAL GAP: No Automatic Database Backups

**Risk:** Total data loss on database corruption, accidental deletion, or Render infrastructure failure.

**Impact:** Loss of all biometric observations, baselines, constraints, state estimates, validation records, and the longitudinal scientific evidence built over the collection period.

**Root cause:** Render free tier PostgreSQL does not include automated point-in-time recovery or scheduled backups. This is a plan-tier limitation, not a configuration error.

### Immediate Mitigation

A backup script has been created at `backend/scripts/backup_db.py`. This exports all 7 tables to timestamped NDJSON files.

**Run immediately and on a scheduled basis:**

```powershell
# Set once in your environment or .env file
$env:VIGIL_DB_URL = "postgresql://vigil_db_6eiq_user:<password>@..."

# Run backup
python backend/scripts/backup_db.py
# Output: backups/vigil_backup_YYYYMMDD_HHMMSS/
```

**Recommended schedule:** Daily backup (manual or cron) until Render paid tier is justified.

### Long-Term Options

| Option | Cost | Backup SLA | Recommended When |
|---|---|---|---|
| Manual pg_dump (current workaround) | Free | Manual only | NOW — single user, scientific phase |
| Render PostgreSQL paid tier | $7/month | Daily automatic + PITR | When multi-user begins (Phase 6) |
| External backup to cloud storage | ~$1/month | Customizable via cron | If manual becomes burdensome |

---

### Environment Variables

| Variable | Source | Status |
|---|---|---|
| `DATABASE_URL` | Render-injected from `vigil-postgres` | ✅ Configured |
| `INGEST_API_KEY` | `generateValue: true` (Render) | ✅ Configured |
| `READ_API_KEY` | `generateValue: true` (Render) | ✅ Configured |
| `LOG_LEVEL` | `INFO` (render.yaml) | ✅ Configured |
| `ENABLE_DOCS` | `false` (render.yaml) | ✅ Configured — docs correctly disabled |

---

### API + Migration State

| Check | Status | Evidence |
|---|---|---|
| Health endpoint | ✅ `{"status":"ok","database":"connected"}` | Live 2026-06-26 |
| Last ingest | ✅ 2026-06-26 11:17:29 UTC | Production DB |
| Migration head | ✅ `a9f4e2d1b6c8` (7/7 applied) | `alembic_version` table |
| Auto-deploy active | ✅ GitHub main → Render Docker build | Confirmed operational |

---

### Logging

`LOG_LEVEL=INFO`. Logs available in Render dashboard under the `vigil-api` service.

**Missing:** No structured log export, no external log retention, no alerting on ingest failure. For Scientific Operations:

- Check Render logs periodically for errors (especially after WorkManager sync windows)
- No automated alerting on pipeline failure is available on free tier
- Manual daily health check: `curl https://vigilbridge.onrender.com/health`

---

### Secrets Management

| Item | Status |
|---|---|
| Secrets in `render.yaml` | ✅ None — all via `generateValue` or `fromDatabase` |
| Secrets in git history | ✅ None found |
| Local audit scripts | ✅ Sanitized this sprint (see Security Audit) |

---

## Infrastructure Verdict

| Component | Status |
|---|---|
| Web service | ✅ OPERATIONAL |
| Database | ✅ OPERATIONAL |
| Auto-deploy | ✅ ACTIVE |
| API authentication | ✅ ENFORCED |
| Migrations | ✅ APPLIED |
| **Backups** | **❌ NOT CONFIGURED — ACTION REQUIRED** |
| Monitoring/alerting | ⚠️ MANUAL ONLY |
| Cold-start latency | ⚠️ ~30s (free tier expected behavior) |

**Immediate action:** Run `backend/scripts/backup_db.py` and set a reminder to run it weekly at minimum.
