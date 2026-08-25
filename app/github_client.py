"""
GitHubClient: a thin, well-behaved wrapper around the GitHub REST API.

Responsibilities:
    - Authenticate requests (optional personal access token).
    - Handle pagination transparently.
    - Translate HTTP errors into typed application exceptions.
    - Apply sane timeouts and retry-once-on-transient-failure logic.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from app.config import configure_logging, settings
from app.exceptions import (
    GitHubAPIError,
    GitHubAPIRateLimitError,
    GitHubConnectionError,
    GitHubUserNotFoundError,
)
from app.models import GitHubUser, Repository

logger = configure_logging(__name__)


class GitHubClient:
    """Encapsulates all HTTP communication with the GitHub REST API."""

    def __init__(self, token: str | None = None, timeout: int | None = None) -> None:
        self._token = token or settings.github_token
        self._timeout = timeout or settings.request_timeout_seconds
        self._base_url = settings.github_api_base_url
        self._session = requests.Session()
        self._session.headers.update(self._build_headers())

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-profile-analyzer/1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        """
        Perform a single GET request against the GitHub API, retrying
        once on connection-level failures.
        """
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(1, 3):
            try:
                logger.debug("GET %s (attempt %d) params=%s", url, attempt, params)
                response = self._session.get(url, params=params, timeout=self._timeout)
                return response
            except requests.exceptions.RequestException as exc:
                last_error = exc
                logger.warning("Request failed (attempt %d/2): %s", attempt, exc)
                time.sleep(0.75 * attempt)

        raise GitHubConnectionError(
            f"Failed to reach GitHub API at {url} after retries: {last_error}"
        )

    def _handle_response(self, response: requests.Response, username: str | None = None) -> Any:
        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            raise GitHubUserNotFoundError(username or "unknown")

        if response.status_code == 403 and "rate limit" in response.text.lower():
            reset_header = response.headers.get("X-RateLimit-Reset")
            reset_epoch = int(reset_header) if reset_header else None
            raise GitHubAPIRateLimitError(reset_epoch=reset_epoch)

        raise GitHubAPIError(response.status_code, response.text[:300])

    def get_user(self, username: str) -> GitHubUser:
        """Fetch profile metadata for a single GitHub username."""
        logger.info("Fetching GitHub user profile: %s", username)
        response = self._request(f"/users/{username}")
        payload = self._handle_response(response, username=username)
        return GitHubUser.from_api(payload)

    def get_repositories(self, username: str) -> list[Repository]:
        """
        Fetch all public, non-forked-and-forked repositories for a
        user, transparently walking pagination up to a safety cap.
        """
        logger.info("Fetching repositories for: %s", username)
        all_repos: list[Repository] = []

        for page in range(1, settings.max_pages + 1):
            params = {
                "per_page": settings.max_repos_per_page,
                "page": page,
                "sort": "updated",
                "type": "owner",
            }
            response = self._request(f"/users/{username}/repos", params=params)
            payload = self._handle_response(response, username=username)

            if not payload:
                break

            all_repos.extend(Repository.from_api(item) for item in payload)

            if len(payload) < settings.max_repos_per_page:
                break

        logger.info("Fetched %d repositories for %s", len(all_repos), username)
        return all_repos

    def get_repo_commit_count(self, owner: str, repo: str) -> int:
        """
        Estimate the total commit count for a repository using the
        `Link` header pagination trick (asking for 1 commit per page
        and reading the last page number), which avoids downloading
        the full commit history.
        """
        params = {"per_page": 1}
        try:
            response = self._request(f"/repos/{owner}/{repo}/commits", params=params)
        except GitHubConnectionError:
            return 0

        if response.status_code == 409:
            # Empty repository (no commits yet)
            return 0
        if response.status_code != 200:
            return 0

        link_header = response.headers.get("Link")
        if not link_header:
            data = response.json()
            return len(data) if isinstance(data, list) else 0

        for part in link_header.split(","):
            if 'rel="last"' in part:
                try:
                    last_url = part[part.index("<") + 1 : part.index(">")]
                    page_param = last_url.split("page=")[-1].split("&")[0]
                    return int(page_param)
                except (ValueError, IndexError):
                    return 0
        return 0

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
