"""Unit tests for app.analyzer.ProfileAnalyzer."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.analyzer import ProfileAnalyzer
from app.exceptions import InvalidUsernameError
from app.models import GitHubUser, Repository


def _make_repo(name: str, language: str | None, stars: int, forks: int, days_since_push: int = 10, is_fork=False) -> Repository:
    return Repository(
        name=name,
        full_name=f"user/{name}",
        description="desc",
        language=language,
        stargazers_count=stars,
        forks_count=forks,
        watchers_count=stars,
        open_issues_count=0,
        size=100,
        created_at=datetime.utcnow() - timedelta(days=400),
        updated_at=datetime.utcnow() - timedelta(days=days_since_push),
        pushed_at=datetime.utcnow() - timedelta(days=days_since_push),
        is_fork=is_fork,
        is_archived=False,
        html_url=f"https://github.com/user/{name}",
    )


def _make_user(login="testuser", followers=50) -> GitHubUser:
    return GitHubUser(
        login=login,
        name="Test User",
        bio="Bio",
        company=None,
        location=None,
        email=None,
        public_repos=3,
        followers=followers,
        following=5,
        created_at=datetime.utcnow() - timedelta(days=1000),
        avatar_url=None,
        html_url=f"https://github.com/{login}",
    )


class TestProfileAnalyzer:
    def test_analyze_computes_aggregates_correctly(self):
        mock_client = MagicMock()
        mock_client.get_user.return_value = _make_user()
        mock_client.get_repositories.return_value = [
            _make_repo("repo-a", "Python", 100, 10, days_since_push=5),
            _make_repo("repo-b", "Python", 50, 5, days_since_push=200),
            _make_repo("repo-c", "JavaScript", 20, 2, days_since_push=500),
        ]
        mock_client.get_repo_commit_count.return_value = 10

        analyzer = ProfileAnalyzer(client=mock_client)
        result = analyzer.analyze("testuser", estimate_commits=True)

        assert result.total_repos == 3
        assert result.total_stars == 170
        assert result.total_forks == 17
        assert result.most_used_language == "Python"
        assert result.language_distribution == {"Python": 2, "JavaScript": 1}
        assert result.average_stars == pytest.approx(56.67, rel=0.01)
        assert 0 <= result.developer_score <= 100

    def test_analyze_with_no_repositories(self):
        mock_client = MagicMock()
        mock_client.get_user.return_value = _make_user()
        mock_client.get_repositories.return_value = []

        analyzer = ProfileAnalyzer(client=mock_client)
        result = analyzer.analyze("testuser", estimate_commits=False)

        assert result.total_repos == 0
        assert result.total_stars == 0
        assert result.most_used_language is None
        assert result.activity_level == "No Activity"
        assert result.developer_score >= 0

    def test_invalid_username_raises(self):
        mock_client = MagicMock()
        analyzer = ProfileAnalyzer(client=mock_client)
        with pytest.raises(InvalidUsernameError):
            analyzer.analyze("invalid username!!")

    def test_activity_level_high_when_recently_active(self):
        mock_client = MagicMock()
        mock_client.get_user.return_value = _make_user()
        mock_client.get_repositories.return_value = [
            _make_repo(f"repo-{i}", "Python", 1, 0, days_since_push=5) for i in range(5)
        ]
        analyzer = ProfileAnalyzer(client=mock_client)
        result = analyzer.analyze("testuser", estimate_commits=False)
        assert result.activity_level in {"Very High", "High"}

    def test_empty_username_raises(self):
        mock_client = MagicMock()
        analyzer = ProfileAnalyzer(client=mock_client)
        with pytest.raises(InvalidUsernameError):
            analyzer.analyze("   ")
