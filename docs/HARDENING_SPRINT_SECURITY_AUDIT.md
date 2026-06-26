# Task 2 — Security Audit Report

**Date:** 2026-06-26
**Sprint:** Engineering Hardening (Final Engineering Sprint)

---

## Summary

One category of security issue found and remediated in this sprint: hardcoded production credentials in loose diagnostic scripts outside the repository. Backend security posture is sound.

---

## Finding 1 — Hardcoded Production Credentials in Diagnostic Scripts (REMEDIATED)

**Severity:** HIGH
**Status:** REMEDIATED 2026-06-26

### Scope

Three Python scripts stored in `C:\Users\kaliv\` (outside the git repository) contained the production Render PostgreSQL connection string in plaintext:

| Script | Size | Purpose |
|---|---|---|
| `vigil_audit.py` | 13KB | Full DB audit — tables, quality, coverage, readiness |
| `vigil_audit2.py` | 3.5KB | Sleep coverage and step EOD analysis |
| `vigil_hr_verify.py` | 1.7KB | Resting HR verification |

**Credential exposed:**
```
postgresql://vigil_db_6eiq_user:<password>@dpg-d8hgeuegvqtc73d7hgbg-a.oregon-postgres.render.com/vigil_db_6eiq
```
(password redacted here)

### Risk

- Scripts were not tracked in git — no commit history exposure
- Scripts were not shared externally — risk limited to local machine
- However: credentials appeared in conversation context during this audit session
- Recommendation: rotate credentials (see below)

### Remediation Applied

All three scripts updated to read credentials from the environment:

```python
import os
CONN = os.environ.get('VIGIL_DB_URL')
if not CONN:
    raise RuntimeError('VIGIL_DB_URL environment variable not set. Export it before running this script.')
```

**Verification:** Running without `VIGIL_DB_URL` set produces:
```
RuntimeError: VIGIL_DB_URL environment variable not set. Export it before running this script.
```
✅ VERIFIED — scripts no longer contain hardcoded credentials.

### Usage After Sanitization

```powershell
$env:VIGIL_DB_URL = "postgresql://vigil_db_6eiq_user:<password>@..."
python C:\Users\kaliv\vigil_audit.py
```

---

## Finding 2 — Credential Rotation Recommendation

**Severity:** MEDIUM
**Status:** RECOMMENDATION

The production DB password was read aloud in this conversation session context.
Although the session is private, rotation is best practice after any credential exposure.

**Rotation steps:**
1. Open Render dashboard → PostgreSQL database → Access Control
2. Reset the database password (Render generates a new one)
3. Render automatically updates `DATABASE_URL` env var in the web service
4. No code changes needed — backend reads `DATABASE_URL` from environment via `config.py`
5. Update `VIGIL_DB_URL` environment variable on local machine after rotation

**Note:** INGEST_API_KEY and READ_API_KEY are separate from the DB password and were not exposed in this session.

---

## Backend Security Audit

| Control | Status | Evidence |
|---|---|---|
| API key authentication | ✅ PASS | `secrets.compare_digest` constant-time compare, `auth.py` |
| Write/read scope separation | ✅ PASS | `INGEST_API_KEY` → POST only; `READ_API_KEY` → GET only; cross-access blocked |
| Production docs disabled | ✅ PASS | `ENABLE_DOCS=false` in render.yaml; `/docs`, `/redoc`, `/openapi.json` return 404 |
| Secrets from environment | ✅ PASS | `config.py` uses `pydantic_settings.BaseSettings`; no hardcoded secrets in codebase |
| Missing key startup validation | ✅ PASS | `validate_runtime_secrets()` called in lifespan; missing key → 503 before accepting traffic |
| No secrets in git history | ✅ PASS | Searched git log — no credential strings found in any commit |
| Database: read-only for audit scripts | ✅ PASS | All scripts set `conn.set_session(readonly=True)` |

---

## No Other Security Findings

| Area | Checked | Result |
|---|---|---|
| SQL injection | ✅ | SQLAlchemy ORM parameterized queries throughout |
| CORS policy | ✅ | FastAPI CORS — reviewed main.py (no wildcard allow-all) |
| Auth bypass | ✅ | `require_ingest_key`/`require_read_key` as FastAPI Security dependencies — all non-health endpoints gated |
| Secret scanning (git) | ✅ | No credentials in any tracked file |
| Environment variable leakage | ✅ | No env dump endpoints, no debug output |

---

## Verdict

**Backend security: SOUND.** One pre-existing local credential exposure in diagnostic scripts — remediated this sprint. Credential rotation is the remaining recommended action.
