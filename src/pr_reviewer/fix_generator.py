"""Fix code generation and fix PR creation."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import anthropic

from pr_reviewer.github_client import GitHubClient
from pr_reviewer.models import PRInfo, ReviewConfig, ReviewFinding

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def generate_fix_pr(
    findings: list[ReviewFinding],
    pr_info: PRInfo,
    gh: GitHubClient,
    config: ReviewConfig,
    api_key: str,
) -> str | None:
    """Generate a fix PR for findings that have suggested fixes.

    Groups findings by file to avoid SHA conflicts when committing
    multiple changes to the same file.

    Args:
        findings: Review findings (only those with suggested_fix are used).
        pr_info: PR metadata.
        gh: GitHub client.
        config: Review configuration.
        api_key: Anthropic API key.

    Returns:
        Fix PR URL, or None if no fixes were generated.
    """
    fixable = [f for f in findings if f.suggested_fix]
    if not fixable:
        logger.info("No fixable findings, skipping fix PR generation")
        return None

    # Group findings by file to handle SHA conflicts
    by_file: dict[str, list[ReviewFinding]] = defaultdict(list)
    for finding in fixable:
        by_file[finding.file].append(finding)

    # Limit files per PR
    files_to_fix = dict(list(by_file.items())[: config.fix_max_files_per_pr])

    # Create fix branch from PR head
    fix_branch = f"{config.fix_branch_prefix}{pr_info.number}"
    try:
        gh.create_branch(fix_branch, from_sha=pr_info.head_sha)
    except Exception as e:
        logger.error("Failed to create fix branch %s: %s", fix_branch, e)
        return None

    # Generate and commit fixes file by file
    client = anthropic.Anthropic(api_key=api_key)
    fix_template = (_PROMPTS_DIR / "fix_generation.txt").read_text(encoding="utf-8")
    committed_any = False

    for filename, file_findings in files_to_fix.items():
        try:
            success = _fix_and_commit_file(
                client=client,
                fix_template=fix_template,
                gh=gh,
                pr_info=pr_info,
                filename=filename,
                file_findings=file_findings,
                fix_branch=fix_branch,
                config=config,
            )
            if success:
                committed_any = True
        except Exception as e:
            logger.error("Failed to fix %s: %s", filename, e)

    if not committed_any:
        logger.warning("No fixes were committed, skipping PR creation")
        return None

    # Create fix PR targeting the original PR's head branch
    pr_title = f"AI Fix: Address review findings for PR #{pr_info.number}"
    pr_body = _build_fix_pr_body(pr_info, files_to_fix)
    labels = [config.labels["fix"], config.labels["automated"]]

    try:
        fix_pr_url = gh.create_pull_request(
            title=pr_title,
            body=pr_body,
            head=fix_branch,
            base=pr_info.head_branch,
            labels=labels,
        )
        return fix_pr_url
    except Exception as e:
        logger.error("Failed to create fix PR: %s", e)
        return None


def _fix_and_commit_file(
    client: anthropic.Anthropic,
    fix_template: str,
    gh: GitHubClient,
    pr_info: PRInfo,
    filename: str,
    file_findings: list[ReviewFinding],
    fix_branch: str,
    config: ReviewConfig,
) -> bool:
    """Generate a complete fixed file and commit it.

    Returns True if the commit succeeded.
    """
    # Get the current file content from the fix branch (which is at PR head)
    current_content = gh.get_file_content(filename, ref=fix_branch)
    if current_content is None:
        logger.warning("Could not read %s from branch %s", filename, fix_branch)
        return False

    # Get file SHA for the update
    file_sha = gh.get_file_sha(filename, ref=fix_branch)
    if file_sha is None:
        logger.warning("Could not get SHA for %s on branch %s", filename, fix_branch)
        return False

    # Build findings description
    findings_desc = "\n".join(
        f"- [{f.severity.value}] {f.title}: {f.description}\n  Suggested: {f.suggested_fix}"
        for f in file_findings
    )

    prompt = fix_template.format(
        filename=filename,
        current_content=current_content,
        findings=findings_desc,
    )

    try:
        response = client.messages.create(
            model=config.claude_model,
            max_tokens=config.claude_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error generating fix for %s: %s", filename, e)
        return False

    fixed_content = _extract_fixed_content(response.content[0].text)
    if fixed_content is None:
        logger.warning("Could not extract fixed content for %s", filename)
        return False

    # Commit the fix
    commit_msg = f"fix: address AI review findings in {filename}\n\nFindings addressed:\n{findings_desc}"
    gh.commit_file(
        path=filename,
        content=fixed_content,
        message=commit_msg,
        branch=fix_branch,
        sha=file_sha,
    )
    return True


def _extract_fixed_content(response_text: str) -> str | None:
    """Extract the complete fixed file content from Claude's response."""
    text = response_text.strip()

    # Try JSON format first: {"fixed_content": "..."}
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "fixed_content" in data:
            return data["fixed_content"]
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    if "```" in text:
        lines = text.split("\n")
        in_block = False
        content_lines = []
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                content_lines.append(line)
        if content_lines:
            return "\n".join(content_lines) + "\n"

    return None


def _build_fix_pr_body(
    pr_info: PRInfo,
    fixes: dict[str, list[ReviewFinding]],
) -> str:
    lines = [
        "## AI-Generated Fix PR",
        "",
        f"This PR addresses review findings from PR #{pr_info.number}.",
        "",
        "### Files Modified",
        "",
    ]

    for filename, file_findings in fixes.items():
        lines.append(f"#### `{filename}`")
        for f in file_findings:
            lines.append(f"- **[{f.severity.value}]** {f.title}")
        lines.append("")

    lines.extend([
        "---",
        "*This PR was automatically generated by AI PR Reviewer.*",
    ])

    return "\n".join(lines)
