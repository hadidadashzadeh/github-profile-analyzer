"""
PDFReportGenerator: builds a polished, multi-section PDF report for
a given AnalysisResult, embedding the matplotlib charts produced by
ChartGenerator.

Uses reportlab, which has no system-level dependencies (unlike
wkhtmltopdf-based approaches), making it Docker-friendly.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.charts import ChartGenerator
from app.config import configure_logging, settings
from app.exceptions import ReportGenerationError
from app.models import AnalysisResult
from app.scoring import DeveloperScoreCalculator

logger = configure_logging(__name__)


class PDFReportGenerator:
    """Generates a downloadable PDF analysis report for a GitHub profile."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or settings.reports_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._chart_generator = ChartGenerator()
        self._styles = getSampleStyleSheet()
        self._styles.add(
            ParagraphStyle(
                name="SectionHeader",
                fontSize=14,
                spaceAfter=8,
                spaceBefore=14,
                textColor=colors.HexColor("#1f2937"),
                fontName="Helvetica-Bold",
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="ReportTitle",
                fontSize=22,
                spaceAfter=4,
                textColor=colors.HexColor("#111827"),
                fontName="Helvetica-Bold",
            )
        )

    def generate(self, result: AnalysisResult) -> Path:
        """Build the PDF and return the path to the generated file."""
        try:
            output_path = self._output_dir / f"{result.user.login}_report.pdf"
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
                leftMargin=1.7 * cm,
                rightMargin=1.7 * cm,
            )

            story = []
            story.extend(self._build_header(result))
            story.extend(self._build_summary_table(result))
            story.extend(self._build_score_section(result))
            story.extend(self._build_charts_section(result))
            story.extend(self._build_top_repos_table(result))
            story.extend(self._build_footer())

            doc.build(story)
            self._chart_generator.close_all()

            logger.info("PDF report generated at %s", output_path)
            return output_path
        except Exception as exc:
            raise ReportGenerationError(f"Failed to generate PDF report: {exc}") from exc

    def _build_header(self, result: AnalysisResult) -> list:
        elements = [
            Paragraph("GitHub Profile Analysis Report", self._styles["ReportTitle"]),
            Paragraph(
                f"Generated for <b>{result.user.login}</b> "
                f"({result.user.name or 'N/A'}) on "
                f"{result.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')}",
                self._styles["Normal"],
            ),
            Spacer(1, 0.6 * cm),
        ]
        return elements

    def _build_summary_table(self, result: AnalysisResult) -> list:
        data = [
            ["Metric", "Value"],
            ["Public Repositories", str(result.total_repos)],
            ["Total Stars", str(result.total_stars)],
            ["Total Forks", str(result.total_forks)],
            ["Followers", str(result.user.followers)],
            ["Following", str(result.user.following)],
            ["Most Used Language", result.most_used_language or "N/A"],
            ["Average Stars / Repo", f"{result.average_stars:.2f}"],
            ["Estimated Total Commits", str(result.estimated_total_commits)],
            ["Activity Level", result.activity_level],
        ]
        table = Table(data, colWidths=[8 * cm, 8 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return [Paragraph("Profile Summary", self._styles["SectionHeader"]), table, Spacer(1, 0.4 * cm)]

    def _build_score_section(self, result: AnalysisResult) -> list:
        grade = DeveloperScoreCalculator.grade_label(result.developer_score)
        text = (
            f"Developer Score: <b>{result.developer_score:.1f} / 100</b> "
            f"&nbsp;&nbsp;|&nbsp;&nbsp; Grade: <b>{grade}</b>"
        )
        return [
            Paragraph("Developer Score", self._styles["SectionHeader"]),
            Paragraph(text, self._styles["Normal"]),
            Spacer(1, 0.4 * cm),
        ]

    def _build_charts_section(self, result: AnalysisResult) -> list:
        elements = [Paragraph("Visual Analytics", self._styles["SectionHeader"])]
        try:
            lang_fig = self._chart_generator.language_distribution_chart(result, save=True)
            repo_fig = self._chart_generator.repository_statistics_chart(result, save=True)
            activity_fig = self._chart_generator.activity_chart(result, save=True)

            for fig, caption, slug in (
                (lang_fig, "Language Distribution", "language_distribution"),
                (repo_fig, "Top Repositories by Stars and Forks", "top_repositories"),
                (activity_fig, "Activity Recency", "activity_recency"),
            ):
                temp_path = settings.charts_dir / f"_tmp_{slug}_{result.user.login}.png"
                fig.savefig(temp_path, dpi=150, bbox_inches="tight")
                elements.append(Image(str(temp_path), width=15 * cm, height=9 * cm))
                elements.append(Spacer(1, 0.3 * cm))
        except Exception as exc:
            logger.warning("Could not embed charts in PDF: %s", exc)
            elements.append(Paragraph("Charts could not be generated.", self._styles["Normal"]))

        return elements

    def _build_top_repos_table(self, result: AnalysisResult) -> list:
        top_repos = sorted(result.repositories, key=lambda r: r.stargazers_count, reverse=True)[:10]
        if not top_repos:
            return []

        data = [["Repository", "Language", "Stars", "Forks"]]
        for r in top_repos:
            data.append([r.name[:30], r.language or "N/A", str(r.stargazers_count), str(r.forks_count)])

        table = Table(data, colWidths=[7 * cm, 4 * cm, 2.5 * cm, 2.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ]
            )
        )
        return [Paragraph("Top Repositories", self._styles["SectionHeader"]), table, Spacer(1, 0.4 * cm)]

    def _build_footer(self) -> list:
        return [
            Spacer(1, 0.6 * cm),
            Paragraph(
                "Generated by GitHub Profile Analyzer — data sourced from the public GitHub REST API.",
                self._styles["Italic"],
            ),
        ]
