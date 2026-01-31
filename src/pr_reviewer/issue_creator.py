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
    severity_label = {
        "critical": "[重大]",
        "high": "[高]",
        "medium": "[中]",
        "low": "[低]",
    }
    prefix = severity_label.get(finding.severity.value, "")
    return f"{prefix} {finding.title} (PR #{pr_info.number})"


def _build_issue_body(finding: ReviewFinding, pr_info: PRInfo) -> str:
    lines = [
        f"## AI レビュー指摘",
        f"",
        f"**対象 PR:** #{pr_info.number} ({pr_info.title})",
        f"**ファイル:** `{finding.file}`",
    ]

    if finding.line:
        lines.append(f"**行番号:** {finding.line}")

    severity_jp = {
        "critical": "重大（マージ前に必ず修正）",
        "high": "高（修正すべき）",
        "medium": "中（修正を検討）",
        "low": "低（できれば対応）",
    }
    category_jp = {
        "security": "セキュリティ",
        "performance": "パフォーマンス",
        "maintainability": "保守性",
        "correctness": "正確性",
        "style": "スタイル",
    }

    lines.extend([
        f"**重大度:** {severity_jp.get(finding.severity.value, finding.severity.value)}",
        f"**カテゴリ:** {category_jp.get(finding.category.value, finding.category.value)}",
        f"",
        f"## 説明",
        f"",
        finding.description,
    ])

    if finding.suggested_fix:
        lines.extend([
            f"",
            f"## 修正案",
            f"",
            f"```",
            finding.suggested_fix,
            f"```",
        ])

    lines.extend([
        f"",
        f"---",
        f"*この Issue は AI PR Reviewer によって自動作成されました。*",
    ])

    return "\n".join(lines)
