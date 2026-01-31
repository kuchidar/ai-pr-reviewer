"""Automatic GitHub Issue creation from review findings."""

from __future__ import annotations

import logging

from pr_reviewer.github_client import GitHubClient
from pr_reviewer.models import PRInfo, ReviewConfig, ReviewFinding

logger = logging.getLogger(__name__)


def create_issues(
    findings: list[ReviewFinding],
    pr_info: PRInfo,
    gh: GitHubClient,
    config: ReviewConfig,
) -> list[str]:
    """Create GitHub Issues for each review finding.

    Args:
        findings: Review findings to create issues for.
        pr_info: PR metadata for context.
        gh: GitHub client.
        config: Review configuration.

    Returns:
        List of created issue URLs.
    """
    issue_urls: list[str] = []

    for finding in findings:
        title = _build_issue_title(finding, pr_info)
        body = _build_issue_body(finding, pr_info)
        labels = [config.labels["review"], config.labels["automated"]]

        try:
            url = gh.create_issue(title=title, body=body, labels=labels)
            issue_urls.append(url)
        except Exception as e:
            logger.error("Failed to create issue for %s: %s", finding.title, e)

    logger.info("Created %d issues from %d findings", len(issue_urls), len(findings))
    return issue_urls


def _build_issue_title(finding: ReviewFinding, pr_info: PRInfo) -> str:
    severity_emoji = {
        "critical": "[CRITICAL]",
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }
    prefix = severity_emoji.get(finding.severity.value, "")
    return f"{prefix} {finding.title} (PR #{pr_info.number})"


def _build_issue_body(finding: ReviewFinding, pr_info: PRInfo) -> str:
    lines = [
        f"## AI Review Finding",
        f"",
        f"**Source PR:** #{pr_info.number} ({pr_info.title})",
        f"**File:** `{finding.file}`",
    ]

    if finding.line:
        lines.append(f"**Line:** {finding.line}")

    lines.extend([
        f"**Severity:** {finding.severity.value}",
        f"**Category:** {finding.category.value}",
        f"",
        f"## Description",
        f"",
        finding.description,
    ])

    if finding.suggested_fix:
        lines.extend([
            f"",
            f"## Suggested Fix",
            f"",
            f"```",
            finding.suggested_fix,
            f"```",
        ])

    lines.extend([
        f"",
        f"---",
        f"*This issue was automatically created by AI PR Reviewer.*",
    ])

    return "\n".join(lines)
