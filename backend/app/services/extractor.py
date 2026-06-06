"""
Health Connect payload extractor.

HC webhook payloads vary by record type. This module normalises
them into a flat list of (metric_type, value, unit, timestamp) tuples
that can be stored as Observation rows.

Each extractor function receives the full raw payload dict and returns
a list of extracted dicts. Unknown fields are silently ignored so the
system never rejects a payload it cannot fully parse.

FHIR metric_type codes follow LOINC conventions where applicable:
  steps          → 55423-8
  sleep_duration → 93832-4
  heart_rate     → 8867-4
  resting_hr     → 40443-4
  spo2           → 2708-6
  respiratory_rate → 9279-1
"""

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _parse_ts(value: Any) -> datetime | None:
    """Parse ISO-8601 string or epoch milliseconds into a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def extract_observations(payload: dict[str, Any], source: str = "health_connect") -> list[dict]:
    """
    Entry point. Dispatches to per-record-type extractors based on
    payload structure. Returns list of observation dicts ready to insert.
    """
    results: list[dict] = []

    record_type = payload.get("record_type") or payload.get("type") or ""

    extractors = {
        "steps": _extract_steps,
        "StepsRecord": _extract_steps,
        "sleep": _extract_sleep,
        "SleepSessionRecord": _extract_sleep,
        "heart_rate": _extract_heart_rate,
        "HeartRateRecord": _extract_heart_rate,
        "resting_heart_rate": _extract_resting_hr,
        "RestingHeartRateRecord": _extract_resting_hr,
        "oxygen_saturation": _extract_spo2,
        "OxygenSaturationRecord": _extract_spo2,
        "respiratory_rate": _extract_respiratory_rate,
        "RespiratoryRateRecord": _extract_respiratory_rate,
        "snapshot": _extract_vigil_snapshot,
    }

    extractor = extractors.get(record_type)
    if extractor:
        results.extend(extractor(payload, source))
    else:
        # Unknown type — store a single raw observation with no parsed value
        ts = _parse_ts(payload.get("timestamp") or payload.get("start_time")) or _now()
        results.append({
            "metric_type": record_type or "unknown",
            "value": None,
            "unit": None,
            "timestamp": ts,
            "source": source,
        })

    return results


def _extract_steps(payload: dict, source: str) -> list[dict]:
    ts = _parse_ts(payload.get("start_time") or payload.get("timestamp")) or _now()
    count = payload.get("count") or payload.get("steps") or payload.get("value")
    return [{
        "metric_type": "steps",
        "value": float(count) if count is not None else None,
        "unit": "steps",
        "timestamp": ts,
        "source": source,
    }]


def _extract_sleep(payload: dict, source: str) -> list[dict]:
    start = _parse_ts(payload.get("start_time"))
    end = _parse_ts(payload.get("end_time"))
    if start and end:
        duration_minutes = (end - start).total_seconds() / 60
        return [{
            "metric_type": "sleep_duration",
            "value": round(duration_minutes, 2),
            "unit": "min",
            "timestamp": start,
            "source": source,
        }]
    return []


def _extract_heart_rate(payload: dict, source: str) -> list[dict]:
    results = []
    samples = payload.get("samples") or []
    if samples:
        for sample in samples:
            ts = _parse_ts(sample.get("time") or sample.get("timestamp"))
            bpm = sample.get("bpm") or sample.get("beatsPerMinute")
            if ts and bpm is not None:
                results.append({
                    "metric_type": "heart_rate",
                    "value": float(bpm),
                    "unit": "bpm",
                    "timestamp": ts,
                    "source": source,
                })
    else:
        ts = _parse_ts(payload.get("timestamp") or payload.get("start_time")) or _now()
        bpm = payload.get("bpm") or payload.get("value")
        if bpm is not None:
            results.append({
                "metric_type": "heart_rate",
                "value": float(bpm),
                "unit": "bpm",
                "timestamp": ts,
                "source": source,
            })
    return results


def _extract_resting_hr(payload: dict, source: str) -> list[dict]:
    ts = _parse_ts(payload.get("timestamp") or payload.get("start_time")) or _now()
    bpm = payload.get("bpm") or payload.get("beatsPerMinute") or payload.get("value")
    if bpm is None:
        return []
    return [{
        "metric_type": "resting_hr",
        "value": float(bpm),
        "unit": "bpm",
        "timestamp": ts,
        "source": source,
    }]


def _extract_spo2(payload: dict, source: str) -> list[dict]:
    ts = _parse_ts(payload.get("timestamp") or payload.get("start_time")) or _now()
    pct = payload.get("percentage") or payload.get("value")
    if pct is None:
        return []
    return [{
        "metric_type": "spo2",
        "value": float(pct),
        "unit": "%",
        "timestamp": ts,
        "source": source,
    }]


def _extract_respiratory_rate(payload: dict, source: str) -> list[dict]:
    ts = _parse_ts(payload.get("timestamp") or payload.get("start_time")) or _now()
    rate = payload.get("rate") or payload.get("value")
    if rate is None:
        return []
    return [{
        "metric_type": "respiratory_rate",
        "value": float(rate),
        "unit": "breaths/min",
        "timestamp": ts,
        "source": source,
    }]


def _extract_vigil_snapshot(payload: dict, source: str) -> list[dict]:
    """
    VigilBridge VitalsSnapshot format — matches current Room entity.
    Converts one snapshot into multiple observations.

    Sleep timing metrics are computed in device-local time using the
    IANA timezone id sent in payload["timezone"]. Falls back to UTC
    if the field is absent or invalid.
    """
    results = []
    ts_ms = payload.get("timestampMs") or payload.get("timestamp_ms")
    ts = _parse_ts(ts_ms) or _now()

    field_map = [
        ("stepsToday", "steps_today", "steps"),
        ("steps7d", "steps_7d", "steps"),
        ("steps30d", "steps_30d", "steps"),
        ("sleepDurationMinutes", "sleep_duration_minutes", "min"),
        ("restingHrBpm", "resting_hr_bpm", "bpm"),
    ]

    for camel, snake, unit in field_map:
        val = payload.get(camel) or payload.get(snake)
        if val is not None:
            results.append({
                "metric_type": snake,
                "value": float(val),
                "unit": unit,
                "timestamp": ts,
                "source": source,
            })

    sleep_start_ms = payload.get("sleepStartMs")
    sleep_end_ms = payload.get("sleepEndMs")

    if sleep_start_ms is not None or sleep_end_ms is not None:
        tz_str = payload.get("timezone") or "UTC"
        try:
            tz = ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, KeyError):
            tz = timezone.utc

        def _local_hour(utc_dt: datetime) -> float:
            local = utc_dt.astimezone(tz)
            return round(local.hour + local.minute / 60.0 + local.second / 3600.0, 4)

        start_utc = _parse_ts(sleep_start_ms) if sleep_start_ms is not None else None
        end_utc = _parse_ts(sleep_end_ms) if sleep_end_ms is not None else None

        if start_utc is not None:
            results.append({
                "metric_type": "sleep_start_hour",
                "value": _local_hour(start_utc),
                "unit": "hour",
                "timestamp": start_utc,
                "source": source,
            })

        if end_utc is not None:
            results.append({
                "metric_type": "sleep_end_hour",
                "value": _local_hour(end_utc),
                "unit": "hour",
                "timestamp": end_utc,
                "source": source,
            })

        if start_utc is not None and end_utc is not None:
            mid_epoch_s = (sleep_start_ms + sleep_end_ms) / 2000.0
            mid_utc = datetime.fromtimestamp(mid_epoch_s, tz=timezone.utc)
            results.append({
                "metric_type": "sleep_midpoint_hour",
                "value": _local_hour(mid_utc),
                "unit": "hour",
                "timestamp": mid_utc,
                "source": source,
            })

            duration_hours = round((end_utc - start_utc).total_seconds() / 3600.0, 4)
            results.append({
                "metric_type": "sleep_duration_hours",
                "value": duration_hours,
                "unit": "hours",
                "timestamp": start_utc,
                "source": source,
            })

    return results
