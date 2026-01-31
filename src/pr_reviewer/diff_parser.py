"""PR diff parsing and file filtering."""

from __future__ import annotations

import fnmatch
import logging

from pr_reviewer.models import FileChange, PRInfo, ReviewConfig

logger = logging.getLogger(__name__)


def filter_files(pr_info: PRInfo, config: ReviewConfig) -> list[FileChange]:
    """Filter PR files based on exclusion patterns and status.

    Args:
        pr_info: PR information with file changes.
        config: Review configuration with exclude patterns.

    Returns:
        List of FileChange objects that should be reviewed.
    """
    reviewable = []
    for file_change in pr_info.files:
        if file_change.status == "removed":
            logger.debug("Skipping removed file: %s", file_change.filename)
            continue

        if _is_excluded(file_change.filename, config.exclude_patterns):
            logger.debug("Skipping excluded file: %s", file_change.filename)
            continue

        if file_change.patch is None:
            logger.debug("Skipping file without patch (binary?): %s", file_change.filename)
            continue

        reviewable.append(file_change)

    logger.info(
        "Filtered %d/%d files for review",
        len(reviewable),
        len(pr_info.files),
    )
    return reviewable


def _is_excluded(filename: str, patterns: list[str]) -> bool:
    """Check if a filename matches any exclusion pattern."""
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True
        # Also check each path component for directory patterns
        if "/" in pattern and fnmatch.fnmatch(filename, pattern):
            return True
    return False


def parse_patch_line_numbers(patch: str) -> list[tuple[int, int]]:
    """Extract changed line ranges from a unified diff patch.

    Returns:
        List of (start_line, end_line) tuples for added/modified lines.
    """
    ranges = []
    current_line = 0

    for line in patch.split("\n"):
        if line.startswith("@@"):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            parts = line.split("+")
            if len(parts) >= 2:
                range_part = parts[1].split("@@")[0].strip()
                if "," in range_part:
                    start = int(range_part.split(",")[0])
                else:
                    start = int(range_part)
                current_line = start
        elif line.startswith("+") and not line.startswith("+++"):
            ranges.append((current_line, current_line))
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Deleted lines don't advance the current line counter
            pass
        else:
            current_line += 1

    return _merge_ranges(ranges)


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge adjacent or overlapping line ranges."""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    merged = [sorted_ranges[0]]

    for start, end in sorted_ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged
