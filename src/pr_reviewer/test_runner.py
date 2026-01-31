"""CI test result checking for fix PRs."""

from __future__ import annotations

import logging
import time

from pr_reviewer.github_client import GitHubClient
from pr_reviewer.models import ReviewConfig, TestResult

logger = logging.getLogger(__name__)


def wait_for_checks(
    gh: GitHubClient,
    ref: str,
    config: ReviewConfig,
) -> list[TestResult]:
    """Poll check runs on a ref until they complete or timeout.

    Args:
        gh: GitHub client.
        ref: Git ref (branch name or SHA) to check.
        config: Review configuration with timeout/poll settings.

    Returns:
        List of TestResult with final statuses.
    """
    if not config.test_check_enabled:
        logger.info("Test check polling disabled, skipping")
        return []

    timeout = config.test_check_timeout
    interval = config.test_check_poll_interval
    elapsed = 0

    logger.info(
        "Waiting for checks on %s (timeout: %ds, interval: %ds)",
        ref,
        timeout,
        interval,
    )

    while elapsed < timeout:
        results = gh.get_check_runs(ref)

        if not results:
            logger.debug("No check runs found yet, waiting...")
            time.sleep(interval)
            elapsed += interval
            continue

        all_completed = all(r.status == "completed" for r in results)
        if all_completed:
            _log_results(results)
            return results

        in_progress = sum(1 for r in results if r.status != "completed")
        logger.debug(
            "%d/%d checks still running (elapsed: %ds)",
            in_progress,
            len(results),
            elapsed,
        )

        time.sleep(interval)
        elapsed += interval

    # Timeout reached - return whatever we have
    logger.warning("Check polling timed out after %ds", timeout)
    results = gh.get_check_runs(ref)
    _log_results(results)
    return results


def check_results_passed(results: list[TestResult]) -> bool:
    """Check if all completed test results passed."""
    if not results:
        return True

    for result in results:
        if result.status == "completed" and result.conclusion not in ("success", "neutral", "skipped"):
            return False

    return True


def _log_results(results: list[TestResult]) -> None:
    for r in results:
        status = f"{r.status}/{r.conclusion}" if r.conclusion else r.status
        logger.info("  Check %s: %s", r.name, status)
