"""
Vigil Database Backup Script.

Exports all 7 application tables to NDJSON files in a timestamped directory.
Run manually or on a schedule. Does not modify any data.

Usage:
    export VIGIL_DB_URL="postgresql://..."
    python backend/scripts/backup_db.py [--output-dir ./backups]

Output: ./backups/vigil_backup_YYYYMMDD_HHMMSS/
  observations.ndjson
  baselines.ndjson
  constraints.ndjson
  state_estimates.ndjson
  validation_records.ndjson
  users.ndjson
  devices.ndjson
  MANIFEST.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras


TABLES = [
    "users",
    "devices",
    "observations",
    "baselines",
    "constraints",
    "state_estimates",
    "validation_records",
]


def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")


def backup(db_url: str, output_dir: Path) -> dict:
    ts = datetime.now(tz=timezone.utc)
    backup_dir = output_dir / f"vigil_backup_{ts.strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(db_url, connect_timeout=30)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    manifest = {
        "backup_started_at": ts.isoformat(),
        "tables": {},
    }

    for table in TABLES:
        out_path = backup_dir / f"{table}.ndjson"
        cur.execute(f"SELECT * FROM {table} ORDER BY created_at ASC")  # noqa: S608
        rows = cur.fetchall()
        with open(out_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(row), default=serialize) + "\n")
        manifest["tables"][table] = {"rows": len(rows), "file": out_path.name}
        print(f"  {table}: {len(rows)} rows → {out_path.name}")

    manifest["backup_completed_at"] = datetime.now(tz=timezone.utc).isoformat()

    manifest_path = backup_dir / "MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    conn.close()
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Vigil database backup")
    parser.add_argument("--output-dir", default="./backups", help="Directory to write backup into")
    args = parser.parse_args()

    db_url = os.environ.get("VIGIL_DB_URL")
    if not db_url:
        print("ERROR: VIGIL_DB_URL environment variable not set.", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    print(f"Vigil backup → {output_dir}")
    manifest = backup(db_url, output_dir)
    total_rows = sum(t["rows"] for t in manifest["tables"].values())
    print(f"\nBackup complete. {total_rows} total rows. Manifest: {output_dir}/vigil_backup_*/MANIFEST.json")


if __name__ == "__main__":
    main()
