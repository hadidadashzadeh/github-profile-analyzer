"""Unit tests for app.database.DatabaseManager."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.database import DatabaseManager
from app.models import AnalysisResult, GitHubUser


def _make_result(username="testuser", repos=10, stars=100) -> AnalysisResult:
    user = GitHubUser(
        login=username, name="Test", bio=None, company=None, location=None,
        email=None, public_repos=repos, followers=20, following=5,
        created_at=datetime.utcnow(), avatar_url=None, html_url="",
    )
    return AnalysisResult(
        user=user,
        repositories=[],
        total_repos=repos,
        total_stars=stars,
        total_forks=5,
        total_watchers=stars,
        language_distribution={"Python": 5},
        most_used_language="Python",
        average_stars=10.0,
        average_forks=0.5,
        estimated_total_commits=200,
        activity_level="High",
        developer_score=42.5,
    )


@pytest.fixture
def temp_db() -> DatabaseManager:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        yield DatabaseManager(db_path=db_path)


class TestDatabaseManager:
    def test_save_and_retrieve_analysis(self, temp_db: DatabaseManager):
        result = _make_result()
        row_id = temp_db.save_analysis(result)
        assert row_id > 0

        history = temp_db.get_history(username="testuser")
        assert len(history) == 1
        assert history[0]["username"] == "testuser"
        assert history[0]["total_stars"] == 100

    def test_get_history_filters_by_username(self, temp_db: DatabaseManager):
        temp_db.save_analysis(_make_result(username="alice"))
        temp_db.save_analysis(_make_result(username="bob"))

        alice_history = temp_db.get_history(username="alice")
        assert len(alice_history) == 1
        assert alice_history[0]["username"] == "alice"

        all_history = temp_db.get_history()
        assert len(all_history) == 2

    def test_growth_series_ordered_ascending(self, temp_db: DatabaseManager):
        temp_db.save_analysis(_make_result(username="grower", repos=5, stars=10))
        temp_db.save_analysis(_make_result(username="grower", repos=8, stars=25))

        series = temp_db.get_growth_series("grower")
        assert len(series) == 2
        assert series[0]["total_repos"] <= series[1]["total_repos"]

    def test_delete_history(self, temp_db: DatabaseManager):
        temp_db.save_analysis(_make_result(username="todelete"))
        deleted = temp_db.delete_history("todelete")
        assert deleted == 1
        assert temp_db.get_history(username="todelete") == []

    def test_clear_all(self, temp_db: DatabaseManager):
        temp_db.save_analysis(_make_result(username="a"))
        temp_db.save_analysis(_make_result(username="b"))
        temp_db.clear_all()
        assert temp_db.get_history() == []
