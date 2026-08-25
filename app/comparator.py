"""
ProfileComparator: compares two AnalysisResult objects head-to-head
across the key metrics used elsewhere in the app.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import configure_logging
from app.models import AnalysisResult

logger = configure_logging(__name__)


@dataclass
class ComparisonMetric:
    """A single metric compared between two profiles."""

    label: str
    value_a: float | int | str
    value_b: float | int | str
    winner: str  # "a", "b", or "tie"


@dataclass
class ComparisonResult:
    """The full head-to-head comparison between two profiles."""

    username_a: str
    username_b: str
    metrics: list[ComparisonMetric]
    overall_winner: str


class ProfileComparator:
    """Encapsulates the logic for comparing two analyzed GitHub profiles."""

    def compare(self, result_a: AnalysisResult, result_b: AnalysisResult) -> ComparisonResult:
        logger.info(
            "Comparing profiles '%s' vs '%s'", result_a.user.login, result_b.user.login
        )

        metrics: list[ComparisonMetric] = [
            self._numeric_metric("Public Repositories", result_a.total_repos, result_b.total_repos),
            self._numeric_metric("Total Stars", result_a.total_stars, result_b.total_stars),
            self._numeric_metric("Total Forks", result_a.total_forks, result_b.total_forks),
            self._numeric_metric("Followers", result_a.user.followers, result_b.user.followers),
            self._numeric_metric("Average Stars / Repo", result_a.average_stars, result_b.average_stars),
            self._numeric_metric(
                "Estimated Commits", result_a.estimated_total_commits, result_b.estimated_total_commits
            ),
            self._numeric_metric("Developer Score", result_a.developer_score, result_b.developer_score),
        ]

        score_a = sum(1 for m in metrics if m.winner == "a")
        score_b = sum(1 for m in metrics if m.winner == "b")

        if score_a > score_b:
            overall_winner = result_a.user.login
        elif score_b > score_a:
            overall_winner = result_b.user.login
        else:
            overall_winner = "tie"

        return ComparisonResult(
            username_a=result_a.user.login,
            username_b=result_b.user.login,
            metrics=metrics,
            overall_winner=overall_winner,
        )

    @staticmethod
    def _numeric_metric(label: str, value_a: float, value_b: float) -> ComparisonMetric:
        if value_a > value_b:
            winner = "a"
        elif value_b > value_a:
            winner = "b"
        else:
            winner = "tie"
        return ComparisonMetric(label=label, value_a=value_a, value_b=value_b, winner=winner)
