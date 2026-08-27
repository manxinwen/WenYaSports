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
