"""
ProfileAnalyzer: turns a raw list of repositories + user metadata
into an AnalysisResult, using pandas/numpy for the heavy lifting.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.config import configure_logging
from app.exceptions import InvalidUsernameError
from app.github_client import GitHubClient
from app.models import AnalysisResult, GitHubUser, Repository
from app.scoring import DeveloperScoreCalculator

logger = configure_logging(__name__)


class ProfileAnalyzer:
    """
    Orchestrates fetching + analyzing a GitHub profile.

    This class is intentionally the "conductor": it delegates HTTP
    work to GitHubClient and scoring logic to DeveloperScoreCalculator,
    keeping each class focused on a single responsibility (SRP).
    """

    def __init__(self, client: GitHubClient | None = None) -> None:
        self._client = client or GitHubClient()
        self._score_calculator = DeveloperScoreCalculator()

    @staticmethod
    def _validate_username(username: str) -> str:
        cleaned = username.strip().lstrip("@")
        if not cleaned or len(cleaned) > 39:
            raise InvalidUsernameError(f"'{username}' is not a valid GitHub username.")
        if not all(c.isalnum() or c == "-" for c in cleaned):
            raise InvalidUsernameError(f"'{username}' contains invalid characters.")
        return cleaned

    def analyze(self, username: str, estimate_commits: bool = True, commit_sample_size: int = 8) -> AnalysisResult:
        """
        Run a full analysis pipeline for a single GitHub username.

        Args:
            username: The GitHub login to analyze.
            estimate_commits: Whether to query commit counts (costs extra API calls).
            commit_sample_size: How many of the most-recently-updated repos
                to sample for commit counting, to stay within rate limits.

        Returns:
            A fully populated AnalysisResult.
        """
        username = self._validate_username(username)
        logger.info("Starting analysis pipeline for '%s'", username)

        user: GitHubUser = self._client.get_user(username)
        repos: list[Repository] = self._client.get_repositories(username)

        df = self._repos_to_dataframe(repos)

        total_repos = len(repos)
        total_stars = int(df["stargazers_count"].sum()) if not df.empty else 0
        total_forks = int(df["forks_count"].sum()) if not df.empty else 0
        total_watchers = int(df["watchers_count"].sum()) if not df.empty else 0

        language_distribution = self._compute_language_distribution(repos)
        most_used_language = (
            max(language_distribution, key=language_distribution.get)
            if language_distribution
            else None
        )

        average_stars = float(np.round(df["stargazers_count"].mean(), 2)) if not df.empty else 0.0
        average_forks = float(np.round(df["forks_count"].mean(), 2)) if not df.empty else 0.0

        estimated_total_commits = 0
        if estimate_commits and repos:
            estimated_total_commits = self._estimate_commits(username, repos, commit_sample_size)

        activity_level = self._compute_activity_level(repos)

        score = self._score_calculator.calculate(
            total_repos=total_repos,
            total_stars=total_stars,
            total_forks=total_forks,
            followers=user.followers,
            estimated_commits=estimated_total_commits,
            activity_level=activity_level,
            language_count=len(language_distribution),
        )

        result = AnalysisResult(
            user=user,
            repositories=repos,
            total_repos=total_repos,
            total_stars=total_stars,
            total_forks=total_forks,
            total_watchers=total_watchers,
            language_distribution=language_distribution,
            most_used_language=most_used_language,
            average_stars=average_stars,
            average_forks=average_forks,
            estimated_total_commits=estimated_total_commits,
            activity_level=activity_level,
            developer_score=score,
        )

        logger.info(
            "Analysis complete for '%s': %d repos, %d stars, score=%.1f",
            username, total_repos, total_stars, score,
        )
        return result

    @staticmethod
    def _repos_to_dataframe(repos: list[Repository]) -> pd.DataFrame:
        if not repos:
            return pd.DataFrame(
                columns=["name", "language", "stargazers_count", "forks_count", "watchers_count"]
            )
        return pd.DataFrame(
            [
                {
                    "name": r.name,
                    "language": r.language,
                    "stargazers_count": r.stargazers_count,
                    "forks_count": r.forks_count,
                    "watchers_count": r.watchers_count,
                    "is_fork": r.is_fork,
                    "is_archived": r.is_archived,
                    "pushed_at": r.pushed_at,
                }
                for r in repos
            ]
        )

    @staticmethod
    def _compute_language_distribution(repos: list[Repository]) -> dict[str, int]:
        counter = Counter(r.language for r in repos if r.language)
        return dict(counter.most_common())

    def _estimate_commits(self, username: str, repos: list[Repository], sample_size: int) -> int:
        """
        Sample the N most recently updated, non-fork repositories to
        estimate total commit volume. Sampling (instead of querying
        every repo) keeps this within GitHub's API rate limits.
        """
        candidates = sorted(
            (r for r in repos if not r.is_fork),
            key=lambda r: r.pushed_at or datetime.min,
            reverse=True,
        )[:sample_size]

        if not candidates:
            return 0

        sampled_total = 0
        for repo in candidates:
            owner = username
            count = self._client.get_repo_commit_count(owner, repo.name)
            sampled_total += count

        if len(candidates) < len([r for r in repos if not r.is_fork]) and len(candidates) > 0:
            non_fork_total = len([r for r in repos if not r.is_fork])
            scale_factor = non_fork_total / len(candidates)
            return int(round(sampled_total * scale_factor))

        return sampled_total

    @staticmethod
    def _compute_activity_level(repos: list[Repository]) -> str:
        """
        Classify overall activity as Low / Medium / High / Very High
        based on how many repos were pushed to in the last 90 days.
        """
        if not repos:
            return "No Activity"

        cutoff = datetime.utcnow() - timedelta(days=90)
        recent_count = sum(1 for r in repos if r.pushed_at and r.pushed_at >= cutoff)
        ratio = recent_count / len(repos)

        if ratio >= 0.5:
            return "Very High"
        if ratio >= 0.25:
            return "High"
        if ratio >= 0.1:
            return "Medium"
        return "Low"

    def close(self) -> None:
        self._client.close()
