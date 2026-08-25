"""
Custom exception hierarchy used across the GitHub Profile Analyzer.

Having a dedicated exception hierarchy makes it possible for callers
(the Streamlit UI, the CLI, or unit tests) to catch precise error
conditions instead of relying on generic `Exception` handling.
"""


class GitHubAnalyzerError(Exception):
    """Base class for all application-specific exceptions."""


class GitHubUserNotFoundError(GitHubAnalyzerError):
    """Raised when the requested GitHub username does not exist."""

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(f"GitHub user '{username}' was not found.")


class GitHubAPIRateLimitError(GitHubAnalyzerError):
    """Raised when the GitHub API rate limit has been exceeded."""

    def __init__(self, reset_epoch: int | None = None) -> None:
        self.reset_epoch = reset_epoch
        message = "GitHub API rate limit exceeded."
        if reset_epoch:
            message += f" It resets at epoch timestamp {reset_epoch}."
        super().__init__(message)


class GitHubAPIError(GitHubAnalyzerError):
    """Raised for any other non-2xx response returned by the GitHub API."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"GitHub API error [{status_code}]: {message}")


class GitHubConnectionError(GitHubAnalyzerError):
    """Raised when a network-level failure occurs while calling the API."""


class DatabaseError(GitHubAnalyzerError):
    """Raised for any SQLite persistence failure."""


class ReportGenerationError(GitHubAnalyzerError):
    """Raised when PDF report generation fails."""


class ChartGenerationError(GitHubAnalyzerError):
    """Raised when a matplotlib chart cannot be generated."""


class InvalidUsernameError(GitHubAnalyzerError):
    """Raised when the supplied username fails basic validation."""
