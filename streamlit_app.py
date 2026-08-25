"""
Streamlit entry point for the GitHub Profile Analyzer.

Run locally with:
    streamlit run streamlit_app.py

Or via Docker (see README.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from app.analyzer import ProfileAnalyzer
from app.comparator import ProfileComparator
from app.config import configure_logging
from app.database import DatabaseManager
from app.exceptions import GitHubAnalyzerError
from app.models import AnalysisResult
from app.scoring import DeveloperScoreCalculator
from app.charts import ChartGenerator
from app.pdf_report import PDFReportGenerator

logger = configure_logging(__name__)

st.set_page_config(
    page_title="GitHub Profile Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_database() -> DatabaseManager:
    return DatabaseManager()


def run_analysis(username: str) -> AnalysisResult | None:
    analyzer = ProfileAnalyzer()
    try:
        with st.spinner(f"Fetching and analyzing '{username}'..."):
            result = analyzer.analyze(username)
            get_database().save_analysis(result)
        return result
    except GitHubAnalyzerError as exc:
        st.error(f"⚠️ {exc}")
        logger.error("Analysis failed for '%s': %s", username, exc)
        return None
    finally:
        analyzer.close()


def render_dashboard(result: AnalysisResult) -> None:
    st.subheader(f"📌 Overview — {result.user.login}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Repositories", result.total_repos)
    col2.metric("Most Used Language", result.most_used_language or "N/A")
    col3.metric("Average Stars", f"{result.average_stars:.1f}")
    col4.metric("Developer Score", f"{result.developer_score:.1f}/100",
                DeveloperScoreCalculator.grade_label(result.developer_score))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total Stars", result.total_stars)
    col6.metric("Total Forks", result.total_forks)
    col7.metric("Followers", result.user.followers)
    col8.metric("Activity Level", result.activity_level)

    st.divider()

    charts = ChartGenerator()
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.pyplot(charts.language_distribution_chart(result, save=False))
    with chart_col2:
        st.pyplot(charts.activity_chart(result, save=False))

    st.pyplot(charts.repository_statistics_chart(result, save=False))
    charts.close_all()

    st.divider()
    st.subheader("📁 Repository Growth (History)")
    growth_data = get_database().get_growth_series(result.user.login)
    if len(growth_data) >= 2:
        growth_df = pd.DataFrame(growth_data)
        growth_df["analyzed_at"] = pd.to_datetime(growth_df["analyzed_at"])
        st.line_chart(growth_df.set_index("analyzed_at")[["total_repos", "total_stars"]])
    else:
        st.info("Run the analysis on multiple occasions to build a growth trend for this user.")

    st.divider()
    st.subheader("📄 Export Report")
    if st.button("Generate PDF Report", type="primary"):
        try:
            with st.spinner("Building PDF report..."):
                pdf_generator = PDFReportGenerator()
                pdf_path = pdf_generator.generate(result)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download PDF Report",
                    data=f.read(),
                    file_name=pdf_path.name,
                    mime="application/pdf",
                )
        except GitHubAnalyzerError as exc:
            st.error(f"⚠️ Could not generate PDF: {exc}")


def render_comparison() -> None:
    st.subheader("⚖️ Compare Two Profiles")
    col1, col2 = st.columns(2)
    username_a = col1.text_input("First username", key="cmp_user_a")
    username_b = col2.text_input("Second username", key="cmp_user_b")

    if st.button("Compare Profiles", type="primary"):
        if not username_a or not username_b:
            st.warning("Please enter both usernames.")
            return

        result_a = run_analysis(username_a)
        result_b = run_analysis(username_b)

        if result_a and result_b:
            comparator = ProfileComparator()
            comparison = comparator.compare(result_a, result_b)

            rows = [
                {"Metric": m.label, username_a: m.value_a, username_b: m.value_b,
                 "Leader": {"a": username_a, "b": username_b, "tie": "Tie"}[m.winner]}
                for m in comparison.metrics
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if comparison.overall_winner == "tie":
                st.success("🤝 It's a tie overall!")
            else:
                st.success(f"🏆 Overall stronger profile: **{comparison.overall_winner}**")


def render_history() -> None:
    st.subheader("🕘 Analysis History")
    history = get_database().get_history(limit=100)
    if not history:
        st.info("No analyses saved yet. Run an analysis first.")
        return

    df = pd.DataFrame(history)[
        ["username", "analyzed_at", "total_repos", "total_stars", "developer_score", "activity_level"]
    ]
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("📊 GitHub Profile Analyzer")
    st.caption("Analyze, score, visualize, and export reports for any public GitHub profile.")

    with st.sidebar:
        st.header("🔍 Analyze a Profile")
        username = st.text_input("GitHub username", placeholder="e.g. torvalds")
        analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

        st.divider()
        page = st.radio("Navigate", ["Dashboard", "Compare Profiles", "History"])

        st.divider()
        st.caption("Built with Python, Streamlit, Pandas, NumPy, Matplotlib & SQLite.")

    if page == "Dashboard":
        if analyze_clicked and username:
            result = run_analysis(username)
            if result:
                st.session_state["last_result"] = result

        if "last_result" in st.session_state:
            render_dashboard(st.session_state["last_result"])
        else:
            st.info("👈 Enter a GitHub username in the sidebar and click **Analyze** to get started.")

    elif page == "Compare Profiles":
        render_comparison()

    elif page == "History":
        render_history()


if __name__ == "__main__":
    main()
