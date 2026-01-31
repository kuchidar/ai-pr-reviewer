"""Orchestrator: integrates all modules into the review pipeline."""

from __future__ import annotations

import logging
import os
import sys

from pr_reviewer.commenter import post_review_comment
from pr_reviewer.config import load_config
from pr_reviewer.diff_parser import filter_files
from pr_reviewer.fix_generator import generate_fix_pr
from pr_reviewer.github_client import GitHubClient
from pr_reviewer.issue_creator import create_issues
from pr_reviewer.models import ReviewResult
from pr_reviewer.reviewer import review_pr
from pr_reviewer.test_runner import check_results_passed, wait_for_checks

logger = logging.getLogger(__name__)

# Known bot suffixes for infinite loop prevention
_BOT_ACTORS = {"[bot]", "github-actions", "dependabot"}


def run_review(
    repo_full_name: str,
    pr_number: int,
    github_token: str | None = None,
    anthropic_api_key: str | None = None,
) -> bool:
    """Run the full PR review pipeline.

    Args:
        repo_full_name: Repository in "owner/repo" format.
        pr_number: PR number to review.
        github_token: GitHub token (falls back to GITHUB_TOKEN env var).
        anthropic_api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var).

    Returns:
        True if review completed successfully.
    """
    _setup_logging()

    gh_token = github_token or os.environ.get("GITHUB_TOKEN")
    api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")

    if not gh_token:
        logger.error("GitHub token not provided (set GITHUB_TOKEN or --github-token)")
        return False
    if not api_key:
        logger.error("Anthropic API key not provided (set ANTHROPIC_API_KEY or --anthropic-key)")
        return False

    gh = GitHubClient(token=gh_token, repo_full_name=repo_full_name)

    # --- Fetch PR info ---
    logger.info("Fetching PR #%d from %s", pr_number, repo_full_name)
    pr_info = gh.get_pr_info(pr_number)

    # --- Infinite loop prevention (3 guards) ---
    if _should_skip(pr_info, gh):
        return True

    # --- Load config (3-layer merge) ---
    repo_config_content = gh.get_repo_config(ref=pr_info.head_branch)
    config = load_config(repo_config_content=repo_config_content)
    logger.info("Config loaded: model=%s, min_severity=%s", config.claude_model, config.min_severity)

    # --- Filter files ---
    files = filter_files(pr_info, config)
    if not files:
        logger.info("No reviewable files found, posting approval")
        result = ReviewResult()
        post_review_comment(pr_number, result, gh)
        return True

    # --- Load full file content for context ---
    for f in files:
        if f.status != "removed":
            f.content = gh.get_file_content(f.filename, ref=pr_info.head_sha)

    # --- Review ---
    logger.info("Reviewing %d files...", len(files))
    findings = review_pr(pr_info, files, config, api_key)

    result = ReviewResult(findings=findings)

    # --- Create issues ---
    if findings:
        logger.info("Creating issues for %d findings...", len(findings))
        result.issue_urls = create_issues(findings, pr_info, gh, config)

    # --- Generate fix PR ---
    if findings and config.fix_enabled:
        logger.info("Generating fix PR...")
        result.fix_pr_url = generate_fix_pr(findings, pr_info, gh, config, api_key)

    # --- Wait for CI checks on fix PR ---
    if result.fix_pr_url and config.test_check_enabled:
        fix_branch = f"{config.fix_branch_prefix}{pr_info.number}"
        logger.info("Waiting for CI checks on fix branch %s...", fix_branch)
        result.test_results = wait_for_checks(gh, fix_branch, config)

        if not check_results_passed(result.test_results):
            logger.warning("Some CI checks failed on the fix PR")

    # --- Post summary comment ---
    logger.info("Posting review comment on PR #%d...", pr_number)
    post_review_comment(pr_number, result, gh)

    logger.info(
        "Review complete: %d findings, %d issues, fix_pr=%s",
        len(result.findings),
        len(result.issue_urls),
        result.fix_pr_url or "none",
    )
    return True


def _should_skip(pr_info, gh: GitHubClient) -> bool:
    """Check 3 guards for infinite loop prevention.

    1. Bot actor check: skip if PR author is a bot.
    2. Branch prefix check: skip if head branch starts with ai-fix/.
    3. Label check: skip if PR has the 'ai-fix' label.
    """
    # Guard 1: Bot actor
    author = pr_info.author.lower()
    if any(bot in author for bot in _BOT_ACTORS):
        logger.info("Skipping PR #%d: author '%s' is a bot", pr_info.number, pr_info.author)
        return True

    # Guard 2: Branch prefix
    if pr_info.head_branch.startswith("ai-fix/"):
        logger.info(
            "Skipping PR #%d: head branch '%s' is an AI fix branch",
            pr_info.number,
            pr_info.head_branch,
        )
        return True

    # Guard 3: Label check
    if "ai-fix" in pr_info.labels:
        logger.info("Skipping PR #%d: has 'ai-fix' label", pr_info.number)
        return True

    return False


def _setup_logging() -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
