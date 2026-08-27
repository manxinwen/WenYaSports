"""FIT/CSV file parsing service."""

import csv
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import fitparse

logger = logging.getLogger(__name__)


class FitParseError(Exception):
    """Raised when a FIT file cannot be parsed."""


# Map FIT field names (lowercase, as returned by fitparse) to our record keys
FIELD_MAP = {
    "timestamp": "timestamp",
    "position_lat": "lat",
    "position_long": "lon",
    "heart_rate": "hr",
    "speed": "speed",
    "altitude": "alt",
    "distance": "distance",
    "power": "power",
}

# Session fields we care about (kept with their FIT names)
SESSION_FIELDS = (
    "sport",
    "start_time",
    "total_timer_time",
    "total_distance",
    "total_ascent",
    "total_descent",
    "avg_heart_rate",
    "max_heart_rate",
    "avg_speed",
    "max_speed",
)


def _extract_record(msg) -> Optional[dict]:
    """Extract a single 'record' message into a mapped dict."""
    rec: Dict[str, Any] = {}
    for field in msg:
        key = FIELD_MAP.get(field.name)
        if key is None or field.value is None:
            continue
        rec[key] = field.value

    # Convert semicircles to degrees (fitparse default processor does not do this)
    if "lat" in rec:
        rec["lat"] = float(rec["lat"]) * (180.0 / 2 ** 31)
    if "lon" in rec:
        rec["lon"] = float(rec["lon"]) * (180.0 / 2 ** 31)
    return rec


def _compute_ascent_descent(records: List[dict]) -> tuple:
    ascent = 0.0
    descent = 0.0
    prev = None
    for rec in records:
        alt = rec.get("alt")
        if alt is None:
            continue
        if prev is not None:
            delta = alt - prev
            if delta > 0:
                ascent += delta
            else:
                descent += -delta
        prev = alt
    return ascent, descent


def _build_metadata(session: dict, records: List[dict]) -> dict:
    sport = session.get("sport") or "unknown"
    start_time = session.get("start_time")
    if start_time is None and records:
        start_time = records[0].get("timestamp")

    if "total_timer_time" in session:
        total_duration = float(session["total_timer_time"])
    elif records and records[-1].get("timestamp") and records[0].get("timestamp"):
        total_duration = (
            records[-1]["timestamp"] - records[0]["timestamp"]
        ).total_seconds()
    else:
        total_duration = 0.0

    if "total_distance" in session:
        total_distance = float(session["total_distance"])
    else:
        total_distance = float(
            max((r["distance"] for r in records if r.get("distance") is not None), default=0.0)
        )

    total_ascent, total_descent = _compute_ascent_descent(records)

    hr_values = [r["hr"] for r in records if r.get("hr") is not None]
    speed_values = [r["speed"] for r in records if r.get("speed") is not None]

    if "avg_heart_rate" in session:
        avg_hr = float(session["avg_heart_rate"])
    else:
        avg_hr = float(sum(hr_values) / len(hr_values)) if hr_values else None

    if "max_heart_rate" in session:
        max_hr = int(session["max_heart_rate"])
    else:
        max_hr = int(max(hr_values)) if hr_values else None

    if "avg_speed" in session:
        avg_speed = float(session["avg_speed"])
    else:
        avg_speed = float(sum(speed_values) / len(speed_values)) if speed_values else None

    if "max_speed" in session:
        max_speed = float(session["max_speed"])
    else:
        max_speed = float(max(speed_values)) if speed_values else None

    return {
        "sport": sport,
        "start_time": start_time,
        "total_timer_time": total_duration,
        "total_distance": total_distance,
        "total_ascent": total_ascent,
        "total_descent": total_descent,
        "avg_heart_rate": avg_hr,
        "max_heart_rate": max_hr,
        "avg_speed": avg_speed,
        "max_speed": max_speed,
    }


def parse_fit_file(file_path: str) -> dict:
    """Parse a FIT file and return {'metadata': ..., 'records': [...]}."""
    records: List[dict] = []
    session: dict = {}
    try:
        fitfile = fitparse.FitFile(file_path)
        for msg in fitfile.get_messages():
            if msg.name == "record":
                rec = _extract_record(msg)
                if rec is not None:
                    records.append(rec)
            elif msg.name == "session":
                for field in msg:
                    if field.name in SESSION_FIELDS and field.value is not None:
                        session[field.name] = field.value
    except FitParseError:
        raise
    except Exception as exc:
        logger.exception("FIT文件解析失败: %s", file_path)
        raise FitParseError(f"解析FIT文件失败: {exc}") from exc

    if not records:
        raise FitParseError("FIT文件中没有可用的record数据")

    metadata = _build_metadata(session, records)
    return {"metadata": metadata, "records": records}


def parse_csv_file(file_path: str) -> dict:
    """Parse a CSV activity file and return {'metadata': ..., 'records': [...]}."""
    records: List[dict] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = {}
                try:
                    ts_str = row.get("timestamp", "")
                    if ts_str:
                        rec["timestamp"] = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    else:
                        rec["timestamp"] = None

                    lat = row.get("latitude")
                    if lat:
                        rec["lat"] = float(lat)

                    lon = row.get("longitude")
                    if lon:
                        rec["lon"] = float(lon)

                    alt = row.get("altitude_m")
                    if alt:
                        rec["alt"] = float(alt)

                    speed = row.get("speed_mps")
                    if speed:
                        rec["speed"] = float(speed)

                    hr = row.get("heart_rate_bpm")
                    if hr:
                        rec["hr"] = int(hr)

                    distance = row.get("cumulative_distance_km")
                    if distance:
                        rec["distance"] = float(distance) * 1000

                    power = row.get("power_watts")
                    if power:
                        rec["power"] = float(power)

                    if rec.get("timestamp"):
                        records.append(rec)
                except (ValueError, KeyError) as exc:
                    logger.warning("跳过 CSV 行 %s: %s", row, exc)
                    continue

    except Exception as exc:
        logger.exception("CSV文件解析失败: %s", file_path)
        raise FitParseError(f"解析CSV文件失败: {exc}") from exc

    if not records:
        raise FitParseError("CSV文件中没有可用的数据行")

    session: dict = {"sport": "running", "start_time": records[0]["timestamp"]}

    metadata = _build_metadata(session, records)
    return {"metadata": metadata, "records": records}


def parse_activity_file(file_path: str) -> dict:
    """Parse an activity file (FIT or CSV) and return standardized data."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".fit":
        return parse_fit_file(file_path)
    elif ext == ".csv":
        return parse_csv_file(file_path)
    else:
        raise FitParseError(f"不支持的文件格式: {ext}，仅支持 .fit 和 .csv")
