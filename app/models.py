"""
Typed data models representing GitHub domain entities.

Using dataclasses (instead of raw dicts) gives us type safety,
autocompletion, and a single source of truth for the shape of the
data flowing through the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Repository:
    """Represents a single GitHub repository."""

    name: str
    full_name: str
    description: str | None
    language: str | None
    stargazers_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    size: int
    created_at: datetime | None
    updated_at: datetime | None
    pushed_at: datetime | None
    is_fork: bool
    is_archived: bool
    html_url: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Repository":
        """Build a Repository instance from a raw GitHub API JSON object."""

        def _parse_dt(value: str | None) -> datetime | None:
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                return None

        return cls(
            name=payload.get("name", ""),
            full_name=payload.get("full_name", ""),
            description=payload.get("description"),
            language=payload.get("language"),
            stargazers_count=int(payload.get("stargazers_count", 0) or 0),
            forks_count=int(payload.get("forks_count", 0) or 0),
            watchers_count=int(payload.get("watchers_count", 0) or 0),
            open_issues_count=int(payload.get("open_issues_count", 0) or 0),
            size=int(payload.get("size", 0) or 0),
            created_at=_parse_dt(payload.get("created_at")),
            updated_at=_parse_dt(payload.get("updated_at")),
            pushed_at=_parse_dt(payload.get("pushed_at")),
            is_fork=bool(payload.get("fork", False)),
            is_archived=bool(payload.get("archived", False)),
            html_url=payload.get("html_url", ""),
        )


@dataclass
class GitHubUser:
    """Represents a GitHub user/profile."""

    login: str
    name: str | None
    bio: str | None
    company: str | None
    location: str | None
    email: str | None
    public_repos: int
    followers: int
    following: int
    created_at: datetime | None
    avatar_url: str | None
    html_url: str

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "GitHubUser":
        created_at = None
        if payload.get("created_at"):
            try:
                created_at = datetime.strptime(payload["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                created_at = None

        return cls(
            login=payload.get("login", ""),
            name=payload.get("name"),
            bio=payload.get("bio"),
            company=payload.get("company"),
            location=payload.get("location"),
            email=payload.get("email"),
            public_repos=int(payload.get("public_repos", 0) or 0),
            followers=int(payload.get("followers", 0) or 0),
            following=int(payload.get("following", 0) or 0),
            created_at=created_at,
            avatar_url=payload.get("avatar_url"),
            html_url=payload.get("html_url", ""),
        )


@dataclass
class AnalysisResult:
    """
    Aggregated analysis output for a single GitHub profile.
    This is the object that gets persisted, charted, scored and
    turned into a PDF report.
    """

    user: GitHubUser
    repositories: list[Repository]
    total_repos: int
    total_stars: int
    total_forks: int
    total_watchers: int
    language_distribution: dict[str, int]
    most_used_language: str | None
    average_stars: float
    average_forks: float
    estimated_total_commits: int
    activity_level: str
    developer_score: float
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
