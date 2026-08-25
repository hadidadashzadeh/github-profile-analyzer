"""
ChartGenerator: produces matplotlib figures/PNG files for a given
AnalysisResult (language distribution, repo statistics, activity).

Figures are returned as matplotlib.figure.Figure objects so callers
(Streamlit, PDF report) can embed them however they like, and are
also optionally persisted to disk as PNG files.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # headless backend, safe for servers/containers

from app.config import configure_logging, settings
from app.exceptions import ChartGenerationError
from app.models import AnalysisResult

logger = configure_logging(__name__)

_COLOR_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]


class ChartGenerator:
    """Generates all charts required by the dashboard and PDF report."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or settings.charts_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "ggplot")

    def language_distribution_chart(self, result: AnalysisResult, save: bool = True) -> plt.Figure:
        """Pie chart of language usage across repositories."""
        try:
            fig, ax = plt.subplots(figsize=(6, 6))
            data = result.language_distribution

            if not data:
                ax.text(0.5, 0.5, "No language data available", ha="center", va="center")
                ax.axis("off")
            else:
                top_items = list(data.items())[:8]
                other_total = sum(v for _, v in list(data.items())[8:])
                labels = [k for k, _ in top_items]
                values = [v for _, v in top_items]
                if other_total:
                    labels.append("Other")
                    values.append(other_total)

                ax.pie(
                    values,
                    labels=labels,
                    autopct="%1.1f%%",
                    colors=_COLOR_PALETTE[: len(values)],
                    startangle=90,
                    wedgeprops={"edgecolor": "white", "linewidth": 1},
                )
                ax.set_title(f"Language Distribution — {result.user.login}", fontsize=13, fontweight="bold")

            fig.tight_layout()
            if save:
                self._save(fig, f"{result.user.login}_languages.png")
            return fig
        except Exception as exc:
            raise ChartGenerationError(f"Failed to build language chart: {exc}") from exc

    def repository_statistics_chart(self, result: AnalysisResult, save: bool = True) -> plt.Figure:
        """Bar chart of top repositories by stars."""
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            repos_sorted = sorted(result.repositories, key=lambda r: r.stargazers_count, reverse=True)[:10]

            if not repos_sorted:
                ax.text(0.5, 0.5, "No repositories to display", ha="center", va="center")
                ax.axis("off")
            else:
                names = [r.name[:18] for r in repos_sorted]
                stars = [r.stargazers_count for r in repos_sorted]
                forks = [r.forks_count for r in repos_sorted]

                x = np.arange(len(names))
                width = 0.38

                ax.bar(x - width / 2, stars, width, label="Stars", color="#4C72B0")
                ax.bar(x + width / 2, forks, width, label="Forks", color="#DD8452")

                ax.set_xticks(x)
                ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
                ax.set_ylabel("Count")
                ax.set_title(f"Top Repositories — {result.user.login}", fontsize=13, fontweight="bold")
                ax.legend()

            fig.tight_layout()
            if save:
                self._save(fig, f"{result.user.login}_repo_stats.png")
            return fig
        except Exception as exc:
            raise ChartGenerationError(f"Failed to build repository statistics chart: {exc}") from exc

    def activity_chart(self, result: AnalysisResult, save: bool = True) -> plt.Figure:
        """Bar chart showing repository counts bucketed by last-push recency."""
        try:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            buckets = {"0-30d": 0, "31-90d": 0, "91-180d": 0, "181-365d": 0, ">365d": 0, "Unknown": 0}

            from datetime import datetime
            now = datetime.utcnow()

            for repo in result.repositories:
                if not repo.pushed_at:
                    buckets["Unknown"] += 1
                    continue
                days = (now - repo.pushed_at).days
                if days <= 30:
                    buckets["0-30d"] += 1
                elif days <= 90:
                    buckets["31-90d"] += 1
                elif days <= 180:
                    buckets["91-180d"] += 1
                elif days <= 365:
                    buckets["181-365d"] += 1
                else:
                    buckets[">365d"] += 1

            labels = list(buckets.keys())
            values = list(buckets.values())
            bars = ax.bar(labels, values, color=_COLOR_PALETTE[: len(labels)])
            ax.bar_label(bars, padding=2, fontsize=9)
            ax.set_ylabel("Repositories")
            ax.set_title(
                f"Activity Recency — {result.user.login} (Level: {result.activity_level})",
                fontsize=12, fontweight="bold",
            )

            fig.tight_layout()
            if save:
                self._save(fig, f"{result.user.login}_activity.png")
            return fig
        except Exception as exc:
            raise ChartGenerationError(f"Failed to build activity chart: {exc}") from exc

    def _save(self, fig: plt.Figure, filename: str) -> Path:
        path = self._output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight")
        logger.debug("Saved chart to %s", path)
        return path

    @staticmethod
    def close_all() -> None:
        plt.close("all")
