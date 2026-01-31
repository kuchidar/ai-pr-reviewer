"""Claude API review logic."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from pr_reviewer.models import FileChange, PRInfo, ReviewConfig, ReviewFinding

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def review_pr(
    pr_info: PRInfo,
    files: list[FileChange],
    config: ReviewConfig,
    api_key: str,
) -> list[ReviewFinding]:
    """Review all files in a PR using Claude API.

    Args:
        pr_info: PR metadata.
        files: Filtered file changes to review.
        config: Review configuration.
        api_key: Anthropic API key.

    Returns:
        List of review findings.
    """
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _load_prompt("review_system.txt")
    file_template = _load_prompt("review_file.txt")

    all_findings: list[ReviewFinding] = []

    for file_change in files:
        if len(all_findings) >= config.max_total_findings:
            logger.warning(
                "Reached max total findings (%d), stopping review",
                config.max_total_findings,
            )
            break

        findings = _review_file(
            client=client,
            system_prompt=system_prompt,
            file_template=file_template,
            pr_info=pr_info,
            file_change=file_change,
            config=config,
        )
        all_findings.extend(findings)

    # Filter by minimum severity
    severity_order = ["critical", "high", "medium", "low"]
    min_idx = severity_order.index(config.min_severity.value)
    filtered = [f for f in all_findings if severity_order.index(f.severity.value) <= min_idx]

    logger.info("Review complete: %d findings (after severity filter)", len(filtered))
    return filtered


def _review_file(
    client: anthropic.Anthropic,
    system_prompt: str,
    file_template: str,
    pr_info: PRInfo,
    file_change: FileChange,
    config: ReviewConfig,
) -> list[ReviewFinding]:
    """Review a single file and return findings."""
    user_message = file_template.format(
        pr_title=pr_info.title,
        pr_body=pr_info.body or "(no description)",
        filename=file_change.filename,
        patch=file_change.patch or "(no diff available)",
        file_content=file_change.content or "(content not loaded)",
        categories=", ".join(c.value for c in config.categories),
        max_findings=config.max_findings_per_file,
    )

    logger.debug("Reviewing file: %s", file_change.filename)

    try:
        response = client.messages.create(
            model=config.claude_model,
            max_tokens=config.claude_max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        logger.error("Claude API error reviewing %s: %s", file_change.filename, e)
        return []

    return _parse_findings(response.content[0].text, file_change.filename)


def _parse_findings(response_text: str, filename: str) -> list[ReviewFinding]:
    """Parse Claude's JSON response into ReviewFinding objects."""
    try:
        # Extract JSON from possible markdown code block
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (``` markers)
            text = "\n".join(lines[1:-1])

        data = json.loads(text)

        if isinstance(data, dict):
            findings_data = data.get("findings", [])
        elif isinstance(data, list):
            findings_data = data
        else:
            logger.warning("Unexpected response format for %s", filename)
            return []

        findings = []
        for item in findings_data:
            try:
                finding = ReviewFinding(**item)
                findings.append(finding)
            except Exception as e:
                logger.warning("Failed to parse finding for %s: %s", filename, e)

        return findings

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON response for %s: %s", filename, e)
        return []
