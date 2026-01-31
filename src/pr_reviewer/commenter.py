"""PR comment posting with review summary."""

from __future__ import annotations

import logging

from pr_reviewer.github_client import GitHubClient
from pr_reviewer.models import ReviewResult

logger = logging.getLogger(__name__)


def post_review_comment(
    pr_number: int,
    result: ReviewResult,
    gh: GitHubClient,
) -> None:
    """Post a summary comment on the PR.

    If no issues found, posts an approval comment.
    Otherwise, posts a findings table with links to issues and fix PR.
    """
    if not result.has_issues:
        body = _build_approve_comment()
    else:
        body = _build_findings_comment(result)

    gh.post_comment(pr_number, body)


def _build_approve_comment() -> str:
    return (
        "## AI Review: No Issues Found\n\n"
        "The AI reviewer did not find any issues in this PR. Looking good!\n\n"
        "---\n"
        "*Reviewed by AI PR Reviewer*"
    )


def _build_findings_comment(result: ReviewResult) -> str:
    lines = [
        "## AI Review Summary",
        "",
        f"Found **{len(result.findings)}** issue(s) "
        f"({result.critical_count} critical).",
        "",
    ]

    # Findings table
    lines.extend([
        "### Findings",
        "",
        "| Severity | Category | File | Title |",
        "|----------|----------|------|-------|",
    ])

    for f in result.findings:
        severity_badge = _severity_badge(f.severity.value)
        lines.append(
            f"| {severity_badge} | {f.category.value} | `{f.file}` | {f.title} |"
        )

    lines.append("")

    # Issue links
    if result.issue_urls:
        lines.extend([
            "### Created Issues",
            "",
        ])
        for i, url in enumerate(result.issue_urls, 1):
            lines.append(f"{i}. {url}")
        lines.append("")

    # Fix PR link
    if result.fix_pr_url:
        lines.extend([
            "### Fix PR",
            "",
            f"A fix PR has been created: {result.fix_pr_url}",
            "",
        ])

    # Test results
    if result.test_results:
        lines.extend([
            "### CI Check Results (Fix PR)",
            "",
        ])
        for tr in result.test_results:
            status = tr.conclusion or tr.status
            icon = _check_icon(status)
            lines.append(f"- {icon} **{tr.name}**: {status}")
        lines.append("")

    lines.extend([
        "---",
        "*Reviewed by AI PR Reviewer*",
    ])

    return "\n".join(lines)


def _severity_badge(severity: str) -> str:
    badges = {
        "critical": "🔴 critical",
        "high": "🟠 high",
        "medium": "🟡 medium",
        "low": "🔵 low",
    }
    return badges.get(severity, severity)


def _check_icon(status: str) -> str:
    icons = {
        "success": "✅",
        "failure": "❌",
        "neutral": "⚪",
        "cancelled": "⛔",
        "timed_out": "⏱️",
        "in_progress": "🔄",
        "queued": "⏳",
    }
    return icons.get(status, "❓")
