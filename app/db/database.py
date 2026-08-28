"""SQLite persistence layer for long-term memory.

Tables:
  - users(user_id TEXT PRIMARY KEY, profile_json TEXT)
  - activities(activity_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
               date TEXT, features_json TEXT, metadata_json TEXT,
               recommendation_json TEXT, file_path TEXT)
  - knowledge_files(file_id TEXT PRIMARY KEY, filename TEXT, original_filename TEXT,
                    stored_path TEXT, category TEXT, classification_confidence REAL,
                    uploader TEXT, upload_time TEXT, chunk_count INTEGER, status TEXT,
                    error_message TEXT, metadata_json TEXT)
"""

import json
import os
import sqlite3
from typing import List, Optional

# Default database location: app.db in the project root (overridable via env)
DATABASE_PATH = os.environ.get(
    "FIT_APP_DB", os.path.join(os.path.dirname(__file__), "..", "..", "app.db")
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    profile_json TEXT
);
CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    date TEXT,
    features_json TEXT,
    metadata_json TEXT,
    recommendation_json TEXT,
    file_path TEXT
);
CREATE TABLE IF NOT EXISTS knowledge_files (
    file_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_filename TEXT,
    stored_path TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    classification_confidence REAL DEFAULT 0.0,
    uploader TEXT,
    upload_time TEXT,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    metadata_json TEXT
);
"""


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_user_profile(user_id: str, db_path: Optional[str] = None) -> dict:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT profile_json FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or not row["profile_json"]:
        return {}
    return json.loads(row["profile_json"])


def save_user_profile(user_id: str, profile_json: dict, db_path: Optional[str] = None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users (user_id, profile_json) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET profile_json = excluded.profile_json",
            (user_id, json.dumps(profile_json)),
        )
        conn.commit()
    finally:
        conn.close()


def insert_activity(
    user_id: str,
    date: str,
    features_json: str,
    metadata_json: str,
    recommendation_json: str,
    file_path: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO activities "
            "(user_id, date, features_json, metadata_json, recommendation_json, file_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, date, features_json, metadata_json, recommendation_json, file_path),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_recent_activities(
    user_id: str, limit: int = 10, db_path: Optional[str] = None
) -> List[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM activities WHERE user_id = ? ORDER BY activity_id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_activity(activity_id: int, db_path: Optional[str] = None) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_user_dashboard(user_id: str, db_path: Optional[str] = None) -> dict:
    """Get aggregated dashboard stats for a user.

    Returns:
        {
            "total_activities": int,
            "weekly": [{day, distance, duration, calories}, ...],
            "sports": [{name, value, color}, ...],
            "monthly": [{month, activities, km}, ...],
            "recent": [{activity_id, sport, distance, duration, date, ...}, ...],
            "prs": [{label, value, unit, sport, accent}, ...],
            "empty": bool,
        }
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM activities WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    activities = []
    for r in rows:
        row_dict = dict(r)
        features = json.loads(row_dict.get("features_json") or "{}")
        metadata = json.loads(row_dict.get("metadata_json") or "{}")
        activities.append({
            "activity_id": row_dict["activity_id"],
            "date": row_dict["date"],
            "sport": metadata.get("sport", "run"),
            "distance": features.get("total_distance_m", 0),
            "duration": features.get("total_duration_s", 0),
            "calories": features.get("total_calories", 0),
            "avg_hr": features.get("avg_hr"),
            "avg_pace": features.get("avg_pace"),
            "features": features,
            "metadata": metadata,
        })

    if not activities:
        return {
            "total_activities": 0,
            "weekly": [],
            "sports": [],
            "monthly": [],
            "recent": [],
            "prs": [],
            "empty": True,
        }

    # ---- Weekly data (last 7 days) ----
    from datetime import datetime, timedelta
    today = datetime.now()
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day.weekday()]
        day_activities = [a for a in activities if a["date"] and day_str in str(a["date"])]
        d_distance = sum(a["distance"] / 1000 for a in day_activities)  # km
        d_duration = sum(a["duration"] / 60 for a in day_activities)    # min
        d_calories = sum(a["calories"] for a in day_activities)
        weekly.append({
            "day": day_label,
            "date": day_str,
            "距离": round(d_distance, 1),
            "时长": round(d_duration),
            "卡路里": round(d_calories),
        })

    # ---- Sport distribution ----
    sport_colors = {"run": "#ff6a00", "cycling": "#00d4ff", "hike": "#c6ff3d", "swim": "#60a5fa", "walk": "#a78bfa"}
    sport_map = {"run": "跑步", "cycling": "骑行", "hike": "徒步", "swim": "游泳", "walk": "步行"}
    sport_totals: dict = {}
    for a in activities:
        s = a["sport"] or "run"
        sport_totals[s] = sport_totals.get(s, 0) + a["distance"] / 1000
    total_sport_km = sum(sport_totals.values()) or 1
    sports = []
    for s, km in sorted(sport_totals.items(), key=lambda x: -x[1]):
        sports.append({
            "name": sport_map.get(s, s),
            "value": round(km / total_sport_km * 100),
            "color": sport_colors.get(s, "#888"),
            "total_km": round(km, 1),
        })

    # ---- Monthly trend (last 6 months) ----
    monthly = []
    for i in range(5, -1, -1):
        first_day = today.replace(day=1) - timedelta(days=0)
        # Go back i months
        month_date = today
        for _ in range(i):
            if month_date.month == 1:
                month_date = month_date.replace(year=month_date.year - 1, month=12)
            else:
                month_date = month_date.replace(month=month_date.month - 1)
        month_label = f"{month_date.month}月"
        month_activities = [
            a for a in activities
            if a["date"] and f"{month_date.year}-{month_date.month:02d}" in str(a["date"])
        ]
        monthly.append({
            "month": month_label,
            "活动": len(month_activities),
            "公里": round(sum(a["distance"] / 1000 for a in month_activities), 1),
        })

    # ---- Recent activities (last 5) ----
    recent = []
    for a in activities[:5]:
        recent.append({
            "id": a["activity_id"],
            "type": a["sport"],
            "name": a["metadata"].get("name") or f"{sport_map.get(a['sport'], a['sport'])}活动",
            "date": a["date"],
            "distance": f"{(a['distance'] / 1000):.2f} km",
            "duration": _format_duration(a["duration"]),
            "pace": a.get("avg_pace", "—"),
            "calories": round(a["calories"]),
        })

    # ---- PRs ----
    prs = _compute_prs(activities)

    return {
        "total_activities": len(activities),
        "weekly": weekly,
        "sports": sports,
        "monthly": monthly,
        "recent": recent,
        "prs": prs,
        "empty": False,
    }


def _format_duration(seconds: float) -> str:
    if not seconds:
        return "—"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}:{m:02d}"
    return f"{m}min"


def _compute_prs(activities: list) -> list:
    """Compute personal records from activities."""
    prs = [
        {"label": "最远距离", "value": "—", "unit": "KM", "sport": "", "accent": "#ff6a00"},
        {"label": "最长时间", "value": "—", "unit": "", "sport": "", "accent": "#00d4ff"},
        {"label": "最高海拔", "value": "—", "unit": "M", "sport": "", "accent": "#60a5fa"},
        {"label": "活动次数", "value": str(len(activities)), "unit": "", "sport": "总", "accent": "#c6ff3d"},
    ]

    if activities:
        max_dist = max(activities, key=lambda a: a["distance"])
        prs[0]["value"] = f"{max_dist['distance'] / 1000:.1f}"
        prs[0]["sport"] = f"{max_dist['sport']}"

        max_dur = max(activities, key=lambda a: a["duration"])
        h = int(max_dur["duration"] // 3600)
        m = int((max_dur["duration"] % 3600) // 60)
        prs[1]["value"] = f"{h}:{m:02d}" if h > 0 else str(m)
        prs[1]["sport"] = f"{max_dur['sport']}"

        # Elevation from features if available
        max_elev = 0
        for a in activities:
            elev = a.get("features", {}).get("total_elevation_gain_m", 0)
            if elev > max_elev:
                max_elev = elev
        prs[2]["value"] = str(int(max_elev)) if max_elev > 0 else "—"
        prs[2]["sport"] = "累计爬升" if max_elev > 0 else ""

    return prs


# ---------------------------------------------------------------------------
# Knowledge Files CRUD
# ---------------------------------------------------------------------------

def insert_knowledge_file(
    file_id: str,
    filename: str,
    original_filename: str,
    stored_path: str,
    category: str = "general",
    classification_confidence: float = 0.0,
    uploader: str = None,
    chunk_count: int = 0,
    status: str = "pending",
    error_message: str = None,
    metadata: dict = None,
    db_path: Optional[str] = None,
) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO knowledge_files "
            "(file_id, filename, original_filename, stored_path, category, "
            "classification_confidence, uploader, upload_time, chunk_count, "
            "status, error_message, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)",
            (
                file_id, filename, original_filename, stored_path, category,
                classification_confidence, uploader, chunk_count,
                status, error_message,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_knowledge_file(file_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_files WHERE file_id = ?", (file_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    result = dict(row)
    if result.get("metadata_json"):
        result["metadata"] = json.loads(result["metadata_json"])
    return result


def list_knowledge_files(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[dict]:
    conn = _connect(db_path)
    try:
        query = "SELECT * FROM knowledge_files WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY upload_time DESC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    results = []
    for r in rows:
        item = dict(r)
        if item.get("metadata_json"):
            item["metadata"] = json.loads(item["metadata_json"])
        results.append(item)
    return results


def update_knowledge_file(
    file_id: str,
    category: Optional[str] = None,
    chunk_count: Optional[int] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
    classification_confidence: Optional[float] = None,
    db_path: Optional[str] = None,
) -> None:
    conn = _connect(db_path)
    try:
        updates = []
        params = []
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if chunk_count is not None:
            updates.append("chunk_count = ?")
            params.append(chunk_count)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if classification_confidence is not None:
            updates.append("classification_confidence = ?")
            params.append(classification_confidence)
        if not updates:
            return
        params.append(file_id)
        conn.execute(
            f"UPDATE knowledge_files SET {', '.join(updates)} WHERE file_id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def delete_knowledge_file(file_id: str, db_path: Optional[str] = None) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM knowledge_files WHERE file_id = ?", (file_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_knowledge_stats(db_path: Optional[str] = None) -> dict:
    conn = _connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM knowledge_files").fetchone()[0]
        indexed = conn.execute(
            "SELECT COUNT(*) FROM knowledge_files WHERE status = 'indexed'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM knowledge_files WHERE status = 'pending'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM knowledge_files WHERE status = 'failed'"
        ).fetchone()[0]
        # 按分类统计
        cat_rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM knowledge_files GROUP BY category"
        ).fetchall()
        categories = {r["category"]: r["cnt"] for r in cat_rows}
        # 总 chunk 数
        chunk_total = conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) FROM knowledge_files"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "total_files": total,
        "indexed": indexed,
        "pending": pending,
        "failed": failed,
        "total_chunks": chunk_total,
        "categories": categories,
    }
