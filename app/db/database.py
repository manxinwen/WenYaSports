"""SQLite persistence layer for long-term memory.

Tables:
  - users(user_id TEXT PRIMARY KEY, profile_json TEXT)
  - activities(activity_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
               date TEXT, features_json TEXT, metadata_json TEXT,
               recommendation_json TEXT, file_path TEXT)
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
