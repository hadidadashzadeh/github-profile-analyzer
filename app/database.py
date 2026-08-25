"""
DatabaseManager: handles all SQLite persistence for analysis history.

Uses the standard library `sqlite3` module directly (no ORM) to keep
the dependency footprint small, wrapped behind a clean, typed,
exception-safe interface.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.config import configure_logging, settings
from app.exceptions import DatabaseError
from app.models import AnalysisResult

logger = configure_logging(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    total_repos INTEGER NOT NULL,
    total_stars INTEGER NOT NULL,
    total_forks INTEGER NOT NULL,
    followers INTEGER NOT NULL,
    most_used_language TEXT,
    average_stars REAL,
    estimated_total_commits INTEGER,
    activity_level TEXT,
    developer_score REAL NOT NULL,
    language_distribution TEXT,
    raw_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_username ON analysis_history (username);
CREATE INDEX IF NOT EXISTS idx_history_analyzed_at ON analysis_history (analyzed_at);
"""


class DatabaseManager:
    """Thread-safe-enough (per-call connections) SQLite persistence layer."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.database_path
        self._initialize_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"SQLite operation failed: {exc}") from exc
        finally:
            conn.close()

    def _initialize_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
            logger.info("Database schema ready at %s", self._db_path)
        except DatabaseError:
            logger.exception("Failed to initialize database schema")
            raise

    def save_analysis(self, result: AnalysisResult) -> int:
        """Persist an AnalysisResult and return the new row's id."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_history (
                    username, analyzed_at, total_repos, total_stars, total_forks,
                    followers, most_used_language, average_stars,
                    estimated_total_commits, activity_level, developer_score,
                    language_distribution, raw_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.user.login,
                    result.analyzed_at.isoformat(),
                    result.total_repos,
                    result.total_stars,
                    result.total_forks,
                    result.user.followers,
                    result.most_used_language,
                    result.average_stars,
                    result.estimated_total_commits,
                    result.activity_level,
                    result.developer_score,
                    json.dumps(result.language_distribution),
                    json.dumps(
                        {
                            "name": result.user.name,
                            "bio": result.user.bio,
                            "avatar_url": result.user.avatar_url,
                        }
                    ),
                ),
            )
            new_id = cursor.lastrowid
        logger.info("Saved analysis for '%s' as history row %d", result.user.login, new_id)
        return int(new_id)

    def get_history(self, username: str | None = None, limit: int = 50) -> list[dict]:
        """Retrieve past analyses, optionally filtered by username."""
        query = "SELECT * FROM analysis_history"
        params: tuple = ()
        if username:
            query += " WHERE username = ?"
            params = (username,)
        query += " ORDER BY analyzed_at DESC LIMIT ?"
        params = params + (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_growth_series(self, username: str) -> list[dict]:
        """Return repo-count-over-time datapoints for growth charting."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT analyzed_at, total_repos, total_stars, developer_score
                FROM analysis_history
                WHERE username = ?
                ORDER BY analyzed_at ASC
                """,
                (username,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_history(self, username: str) -> int:
        """Delete all stored analyses for a given username. Returns rows deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM analysis_history WHERE username = ?", (username,))
        deleted = cursor.rowcount
        logger.info("Deleted %d history rows for '%s'", deleted, username)
        return deleted

    def clear_all(self) -> None:
        """Wipe the entire history table. Use with caution."""
        with self._connect() as conn:
            conn.execute("DELETE FROM analysis_history")
        logger.warning("Cleared entire analysis_history table")
