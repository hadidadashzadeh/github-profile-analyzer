"""Unit tests for app.github_client.GitHubClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.exceptions import (
    GitHubAPIError,
    GitHubAPIRateLimitError,
    GitHubUserNotFoundError,
)
from app.github_client import GitHubClient
from app.models import GitHubUser, Repository


def _mock_response(status_code: int, json_data=None, text: str = "", headers: dict | None = None):
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = text
    mock_resp.headers = headers or {}
    return mock_resp


class TestGitHubClientGetUser:
    def test_get_user_success(self):
        client = GitHubClient(token="fake-token")
        payload = {
            "login": "octocat",
            "name": "The Octocat",
            "bio": "GitHub mascot",
            "company": None,
            "location": "San Francisco",
            "email": None,
            "public_repos": 8,
            "followers": 100,
            "following": 9,
            "created_at": "2011-01-25T18:44:36Z",
            "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
            "html_url": "https://github.com/octocat",
        }
        with patch.object(client, "_request", return_value=_mock_response(200, payload)):
            user = client.get_user("octocat")

        assert isinstance(user, GitHubUser)
        assert user.login == "octocat"
        assert user.public_repos == 8
        assert user.followers == 100

    def test_get_user_not_found_raises(self):
        client = GitHubClient()
        with patch.object(client, "_request", return_value=_mock_response(404, {}, "Not Found")):
            with pytest.raises(GitHubUserNotFoundError):
                client.get_user("this-user-should-not-exist-xyz")

    def test_rate_limit_raises_typed_error(self):
        client = GitHubClient()
        response = _mock_response(
            403, {}, "API rate limit exceeded", headers={"X-RateLimit-Reset": "1700000000"}
        )
        with patch.object(client, "_request", return_value=response):
            with pytest.raises(GitHubAPIRateLimitError) as exc_info:
                client.get_user("someone")
        assert exc_info.value.reset_epoch == 1700000000

    def test_generic_api_error_raises(self):
        client = GitHubClient()
        with patch.object(client, "_request", return_value=_mock_response(500, {}, "Server Error")):
            with pytest.raises(GitHubAPIError):
                client.get_user("someone")


class TestGitHubClientGetRepositories:
    def test_get_repositories_single_page(self):
        client = GitHubClient()
        payload = [
            {
                "name": "repo1",
                "full_name": "octocat/repo1",
                "description": "A test repo",
                "language": "Python",
                "stargazers_count": 10,
                "forks_count": 2,
                "watchers_count": 10,
                "open_issues_count": 1,
                "size": 500,
                "created_at": "2020-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "pushed_at": "2023-01-01T00:00:00Z",
                "fork": False,
                "archived": False,
                "html_url": "https://github.com/octocat/repo1",
            }
        ]
        with patch.object(client, "_request", return_value=_mock_response(200, payload)):
            repos = client.get_repositories("octocat")

        assert len(repos) == 1
        assert isinstance(repos[0], Repository)
        assert repos[0].name == "repo1"
        assert repos[0].language == "Python"

    def test_get_repositories_empty(self):
        client = GitHubClient()
        with patch.object(client, "_request", return_value=_mock_response(200, [])):
            repos = client.get_repositories("nobody")
        assert repos == []
