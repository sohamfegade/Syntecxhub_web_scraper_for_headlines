from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from logger import get_logger
from settings import Settings

log = get_logger(__name__)

HeadlineDict = Dict[str, Any]


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        cfg = Settings()
        self._db_path: Path = db_path or cfg.database_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise_schema()
        log.info("DatabaseManager ready  ->  %s", self._db_path)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

    def insert_headline(self, headline: HeadlineDict) -> bool:
        sql = """
            INSERT OR IGNORE INTO headlines
                (title, source, author, category, published_time, url, scraped_time)
            VALUES (:title, :source, :author, :category, :published_time, :url, :scraped_time)
        """
        row = _normalise_headline(headline)
        try:
            with self._connect() as conn:
                cursor = conn.execute(sql, row)
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            log.error("Insert failed: %s", exc)
            return False

    def insert_many(self, headlines: List[HeadlineDict]) -> Tuple[int, int]:
        sql = """
            INSERT OR IGNORE INTO headlines
                (title, source, author, category, published_time, url, scraped_time)
            VALUES (:title, :source, :author, :category, :published_time, :url, :scraped_time)
        """
        rows = [_normalise_headline(h) for h in headlines]
        inserted = 0
        try:
            with self._connect() as conn:
                for row in rows:
                    cursor = conn.execute(sql, row)
                    inserted += cursor.rowcount
        except sqlite3.Error as exc:
            log.error("Bulk insert failed: %s", exc)
        skipped = len(rows) - inserted
        log.info("Bulk insert: %d inserted, %d duplicates skipped.", inserted, skipped)
        return inserted, skipped

    def get_all_headlines(self, limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM headlines ORDER BY scraped_time DESC LIMIT ? OFFSET ?"
        return self._fetch_all(sql, (limit, offset))

    def get_headlines_today(self) -> List[Dict[str, Any]]:
        today = datetime.now().strftime("%Y-%m-%d")
        sql = "SELECT * FROM headlines WHERE DATE(scraped_time) = ? ORDER BY scraped_time DESC"
        return self._fetch_all(sql, (today,))

    def get_headline_by_id(self, headline_id: int) -> Optional[Dict[str, Any]]:
        rows = self._fetch_all("SELECT * FROM headlines WHERE id = ?", (headline_id,))
        return rows[0] if rows else None

    def delete_headline(self, headline_id: int) -> bool:
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM headlines WHERE id = ?", (headline_id,))
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            log.error("Delete failed (id=%d): %s", headline_id, exc)
            return False

    def delete_all_headlines(self) -> int:
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM headlines")
                count = cursor.rowcount
                log.warning("Deleted ALL %d headlines.", count)
                return count
        except sqlite3.Error as exc:
            log.error("Delete-all failed: %s", exc)
            return 0

    def search(self, keyword: str, source: Optional[str] = None,
               category: Optional[str] = None, sort_by: str = "scraped_time",
               sort_order: str = "DESC", limit: int = 200) -> List[Dict[str, Any]]:
        allowed_sort = {"scraped_time", "published_time", "title", "source", "category"}
        if sort_by not in allowed_sort:
            sort_by = "scraped_time"
        if sort_order.upper() not in ("ASC", "DESC"):
            sort_order = "DESC"

        clauses: List[str] = ["title LIKE ?"]
        params: List[Any] = [f"%{keyword}%"]
        if source:
            clauses.append("source = ?")
            params.append(source)
        if category:
            clauses.append("category = ?")
            params.append(category)

        where = " AND ".join(clauses)
        sql = f"SELECT * FROM headlines WHERE {where} ORDER BY {sort_by} {sort_order} LIMIT ?"
        params.append(limit)
        return self._fetch_all(sql, tuple(params))

    def toggle_bookmark(self, headline_id: int) -> bool:
        sql = "UPDATE headlines SET bookmarked = CASE WHEN bookmarked = 1 THEN 0 ELSE 1 END WHERE id = ?"
        return self._toggle_flag(sql, headline_id, "bookmarked")

    def toggle_favourite(self, headline_id: int) -> bool:
        sql = "UPDATE headlines SET favourite = CASE WHEN favourite = 1 THEN 0 ELSE 1 END WHERE id = ?"
        return self._toggle_flag(sql, headline_id, "favourite")

    def get_bookmarked(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM headlines WHERE bookmarked = 1 ORDER BY scraped_time DESC")

    def get_favourites(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM headlines WHERE favourite = 1 ORDER BY scraped_time DESC")

    def _toggle_flag(self, sql: str, headline_id: int, flag_name: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(sql, (headline_id,))
                cursor = conn.execute(f"SELECT {flag_name} FROM headlines WHERE id = ?", (headline_id,))
                row = cursor.fetchone()
                return bool(row[flag_name]) if row else False
        except sqlite3.Error as exc:
            log.error("Toggle %s failed (id=%d): %s", flag_name, headline_id, exc)
            return False

    def save_search(self, query: str) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO search_history (query, searched_at) VALUES (?, ?)", (query.strip(), now))
        except sqlite3.Error as exc:
            log.error("Save search failed: %s", exc)

    def get_recent_searches(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?", (limit,))

    def clear_search_history(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM search_history")
        except sqlite3.Error as exc:
            log.error("Clear search history failed: %s", exc)

    def log_activity(self, action: str, details: str = "") -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO activity_log (action, details, created_at) VALUES (?, ?, ?)",
                             (action, details, now))
        except sqlite3.Error as exc:
            log.error("Log activity failed: %s", exc)

    def get_recent_activity(self, limit: int = 30) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,))

    def get_statistics(self) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        queries = {
            "total_headlines":  "SELECT COUNT(*) AS n FROM headlines",
            "today_headlines":  "SELECT COUNT(*) AS n FROM headlines WHERE DATE(scraped_time) = ?",
            "total_sources":    "SELECT COUNT(DISTINCT source) AS n FROM headlines",
            "last_scraped":     "SELECT MAX(scraped_time) AS n FROM headlines",
            "total_bookmarked": "SELECT COUNT(*) AS n FROM headlines WHERE bookmarked = 1",
            "total_favourites": "SELECT COUNT(*) AS n FROM headlines WHERE favourite = 1",
        }
        stats: Dict[str, Any] = {}
        try:
            with self._connect() as conn:
                for key, sql in queries.items():
                    params: tuple = (today,) if "?" in sql else ()
                    row = conn.execute(sql, params).fetchone()
                    stats[key] = row["n"] if row else 0
        except sqlite3.Error as exc:
            log.error("Statistics query failed: %s", exc)
        return stats

    def get_headlines_per_source(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT source, COUNT(*) AS count FROM headlines GROUP BY source ORDER BY count DESC")

    def get_category_distribution(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT category, COUNT(*) AS count FROM headlines GROUP BY category ORDER BY count DESC")

    def get_daily_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        sql = "SELECT DATE(scraped_time) AS date, COUNT(*) AS count FROM headlines WHERE scraped_time >= DATE('now', ?) GROUP BY DATE(scraped_time) ORDER BY date ASC"
        return self._fetch_all(sql, (f"-{days} days",))

    def get_distinct_sources(self) -> List[str]:
        rows = self._fetch_all("SELECT DISTINCT source FROM headlines ORDER BY source ASC")
        return [r["source"] for r in rows]

    def get_distinct_categories(self) -> List[str]:
        rows = self._fetch_all("SELECT DISTINCT category FROM headlines ORDER BY category ASC")
        return [r["category"] for r in rows]

    def remove_duplicates(self) -> int:
        sql = "DELETE FROM headlines WHERE id NOT IN (SELECT MIN(id) FROM headlines GROUP BY url)"
        try:
            with self._connect() as conn:
                cursor = conn.execute(sql)
                removed = cursor.rowcount
                log.info("Removed %d duplicate headlines.", removed)
                return removed
        except sqlite3.Error as exc:
            log.error("Duplicate removal failed: %s", exc)
            return 0

    def backup(self, backup_dir: Optional[Path] = None) -> Optional[Path]:
        if not self._db_path.exists():
            return None
        target_dir = backup_dir or (self._db_path.parent.parent / "backups")
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = target_dir / f"newsscrape_backup_{stamp}.db"
        try:
            shutil.copy2(str(self._db_path), str(backup_file))
            log.info("Database backed up to %s", backup_file)
            self.log_activity("backup_created", str(backup_file))
            return backup_file
        except OSError as exc:
            log.error("Backup failed: %s", exc)
            return None

    def get_all_as_dicts(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM headlines ORDER BY scraped_time DESC")

    def _fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            log.error("Query failed: %s | SQL: %s", exc, sql[:120])
            return []

    @property
    def path(self) -> Path:
        return self._db_path

    def __repr__(self) -> str:
        return f"<DatabaseManager path={self._db_path}>"


def _normalise_headline(raw: HeadlineDict) -> HeadlineDict:
    return {
        "title":          str(raw.get("title", "")).strip(),
        "source":         str(raw.get("source", "Unknown")).strip(),
        "author":         str(raw.get("author", "")).strip(),
        "category":       str(raw.get("category", "General")).strip(),
        "published_time": str(raw.get("published_time", "")).strip() or None,
        "url":            str(raw.get("url", "")).strip(),
        "scraped_time":   str(raw.get("scraped_time", "")).strip(),
    }


_SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS headlines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    author          TEXT    DEFAULT '',
    category        TEXT    DEFAULT 'General',
    published_time  TEXT,
    url             TEXT    NOT NULL UNIQUE,
    scraped_time    TEXT    NOT NULL,
    bookmarked      INTEGER DEFAULT 0,
    favourite       INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_headlines_source ON headlines (source);
CREATE INDEX IF NOT EXISTS idx_headlines_category ON headlines (category);
CREATE INDEX IF NOT EXISTS idx_headlines_scraped ON headlines (scraped_time);
CREATE INDEX IF NOT EXISTS idx_headlines_url ON headlines (url);

CREATE TABLE IF NOT EXISTS search_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query       TEXT    NOT NULL,
    searched_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,
    details     TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL
);
"""
