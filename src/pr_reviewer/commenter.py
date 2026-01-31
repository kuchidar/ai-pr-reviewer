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
        "## AI レビュー: 問題なし\n\n"
        "AI レビューの結果、この PR に問題は見つかりませんでした。\n\n"
        "---\n"
        "*AI PR Reviewer によるレビュー*"
    )


def _build_findings_comment(result: ReviewResult) -> str:
    lines = [
        "## AI レビュー結果",
        "",
        f"**{len(result.findings)}** 件の問題が見つかりました"
        f"（うち重大: {result.critical_count} 件）。",
        "",
    ]

    # Findings table
    lines.extend([
        "### 検出された問題",
        "",
        "| 重大度 | カテゴリ | ファイル | 概要 |",
        "|--------|----------|----------|------|",
    ])

    for f in result.findings:
        severity_badge = _severity_badge(f.severity.value)
        category_jp = _category_jp(f.category.value)
        lines.append(
            f"| {severity_badge} | {category_jp} | `{f.file}` | {f.title} |"
        )

    lines.append("")

    # Issue links
    if result.issue_urls:
        lines.extend([
            "### 作成された Issue",
            "",
        ])
        for i, url in enumerate(result.issue_urls, 1):
            lines.append(f"{i}. {url}")
        lines.append("")

    # Fix PR link
    if result.fix_pr_url:
        lines.extend([
            "### 修正 PR",
            "",
            f"修正 PR が作成されました: {result.fix_pr_url}",
            "",
        ])

    # Test results
    if result.test_results:
        lines.extend([
            "### CI チェック結果（修正 PR）",
            "",
        ])
        for tr in result.test_results:
            status = tr.conclusion or tr.status
            icon = _check_icon(status)
            lines.append(f"- {icon} **{tr.name}**: {status}")
        lines.append("")

    lines.extend([
        "---",
        "*AI PR Reviewer によるレビュー*",
    ])

    return "\n".join(lines)


def _severity_badge(severity: str) -> str:
    badges = {
        "critical": "🔴 重大",
        "high": "🟠 高",
        "medium": "🟡 中",
        "low": "🔵 低",
    }
    return badges.get(severity, severity)


def _category_jp(category: str) -> str:
    mapping = {
        "security": "セキュリティ",
        "performance": "パフォーマンス",
        "maintainability": "保守性",
        "correctness": "正確性",
        "style": "スタイル",
    }
    return mapping.get(category, category)


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
