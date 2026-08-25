"""
DeveloperScoreCalculator: computes a single 0-100 "developer score"
from an analyzed profile's raw metrics.

The formula is a weighted, log-dampened composite so that a single
viral repo (e.g. 50,000 stars) cannot single-handedly dominate the
score, while still rewarding consistent output and community traction.
"""

from __future__ import annotations

import numpy as np

from app.config import configure_logging

logger = configure_logging(__name__)

_ACTIVITY_WEIGHTS = {
    "Very High": 1.0,
    "High": 0.75,
    "Medium": 0.5,
    "Low": 0.25,
    "No Activity": 0.0,
}


class DeveloperScoreCalculator:
    """Encapsulates the developer-score business logic in one place."""

    # Weight distribution across the 100-point scale.
    WEIGHT_REPOS = 15
    WEIGHT_STARS = 25
    WEIGHT_FORKS = 15
    WEIGHT_FOLLOWERS = 15
    WEIGHT_COMMITS = 20
    WEIGHT_ACTIVITY = 10

    @staticmethod
    def _log_scale(value: int, cap_value: float) -> float:
        """
        Map a raw count to a 0-1 range using log1p scaling, so growth
        has diminishing returns rather than being strictly linear.
        """
        if value <= 0:
            return 0.0
        scaled = np.log1p(value) / np.log1p(cap_value)
        return float(min(scaled, 1.0))

    def calculate(
        self,
        total_repos: int,
        total_stars: int,
        total_forks: int,
        followers: int,
        estimated_commits: int,
        activity_level: str,
        language_count: int,
    ) -> float:
        """
        Compute the composite developer score (0-100).

        Each raw metric is normalized independently, weighted, and
        summed. A small bonus (up to 5 points) rewards language
        diversity, capped so it cannot push the score above 100.
        """
        repo_component = self._log_scale(total_repos, cap_value=100) * self.WEIGHT_REPOS
        star_component = self._log_scale(total_stars, cap_value=5000) * self.WEIGHT_STARS
        fork_component = self._log_scale(total_forks, cap_value=1000) * self.WEIGHT_FORKS
        follower_component = self._log_scale(followers, cap_value=2000) * self.WEIGHT_FOLLOWERS
        commit_component = self._log_scale(estimated_commits, cap_value=5000) * self.WEIGHT_COMMITS
        activity_component = _ACTIVITY_WEIGHTS.get(activity_level, 0.0) * self.WEIGHT_ACTIVITY

        diversity_bonus = min(language_count, 10) * 0.5  # up to 5 bonus points

        raw_score = (
            repo_component
            + star_component
            + fork_component
            + follower_component
            + commit_component
            + activity_component
            + diversity_bonus
        )

        final_score = float(np.clip(raw_score, 0, 100))
        logger.debug(
            "Score breakdown -> repos=%.2f stars=%.2f forks=%.2f followers=%.2f "
            "commits=%.2f activity=%.2f diversity_bonus=%.2f => total=%.2f",
            repo_component, star_component, fork_component, follower_component,
            commit_component, activity_component, diversity_bonus, final_score,
        )
        return round(final_score, 1)

    @staticmethod
    def grade_label(score: float) -> str:
        """Convert a numeric score into a human-readable grade label."""
        if score >= 85:
            return "Elite"
        if score >= 70:
            return "Advanced"
        if score >= 50:
            return "Intermediate"
        if score >= 25:
            return "Emerging"
        return "Beginner"
