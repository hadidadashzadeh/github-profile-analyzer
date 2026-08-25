"""Unit tests for app.scoring.DeveloperScoreCalculator."""

from __future__ import annotations

from app.scoring import DeveloperScoreCalculator


class TestDeveloperScoreCalculator:
    def setup_method(self):
        self.calculator = DeveloperScoreCalculator()

    def test_zero_metrics_yield_zero_score(self):
        score = self.calculator.calculate(
            total_repos=0,
            total_stars=0,
            total_forks=0,
            followers=0,
            estimated_commits=0,
            activity_level="No Activity",
            language_count=0,
        )
        assert score == 0.0

    def test_score_is_bounded_between_0_and_100(self):
        score = self.calculator.calculate(
            total_repos=100_000,
            total_stars=10_000_000,
            total_forks=1_000_000,
            followers=1_000_000,
            estimated_commits=1_000_000,
            activity_level="Very High",
            language_count=50,
        )
        assert 0 <= score <= 100

    def test_higher_metrics_yield_higher_score(self):
        low_score = self.calculator.calculate(
            total_repos=1, total_stars=0, total_forks=0, followers=0,
            estimated_commits=0, activity_level="Low", language_count=1,
        )
        high_score = self.calculator.calculate(
            total_repos=50, total_stars=1000, total_forks=200, followers=500,
            estimated_commits=2000, activity_level="Very High", language_count=8,
        )
        assert high_score > low_score

    def test_grade_label_boundaries(self):
        assert DeveloperScoreCalculator.grade_label(90) == "Elite"
        assert DeveloperScoreCalculator.grade_label(75) == "Advanced"
        assert DeveloperScoreCalculator.grade_label(55) == "Intermediate"
        assert DeveloperScoreCalculator.grade_label(30) == "Emerging"
        assert DeveloperScoreCalculator.grade_label(10) == "Beginner"
