"""Application configuration."""

import os


def get_max_submissions_per_hour() -> int:
    """Get maximum submissions per hour from environment."""
    return int(os.getenv("MAX_SUBMISSIONS_PER_HOUR", "50"))


def get_max_concurrent_running() -> int:
    """Get maximum concurrent running jobs from environment."""
    return int(os.getenv("MAX_CONCURRENT_RUNNING", "2"))
