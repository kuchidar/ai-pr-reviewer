"""Configuration loading with 3-layer merge: default → repo → env vars."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from pr_reviewer.models import ReviewConfig

logger = logging.getLogger(__name__)

_DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default_rules.yml"
_REPO_CONFIG_FILENAME = ".ai-reviewer.yml"

_ENV_PREFIX = "AI_REVIEWER_"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _flatten_config(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested config dict into ReviewConfig field names."""
    flat: dict[str, Any] = {}

    review = raw.get("review", {})
    flat["min_severity"] = review.get("min_severity")
    flat["max_findings_per_file"] = review.get("max_findings_per_file")
    flat["max_total_findings"] = review.get("max_total_findings")

    flat["exclude_patterns"] = raw.get("exclude_patterns")
    flat["categories"] = raw.get("categories")
    flat["labels"] = raw.get("labels")

    fix = raw.get("fix", {})
    flat["fix_enabled"] = fix.get("enabled")
    flat["fix_branch_prefix"] = fix.get("branch_prefix")
    flat["fix_max_files_per_pr"] = fix.get("max_files_per_pr")

    test = raw.get("test_check", {})
    flat["test_check_enabled"] = test.get("enabled")
    flat["test_check_timeout"] = test.get("timeout")
    flat["test_check_poll_interval"] = test.get("poll_interval")

    claude = raw.get("claude", {})
    flat["claude_model"] = claude.get("model")
    flat["claude_max_tokens"] = claude.get("max_tokens")

    return {k: v for k, v in flat.items() if v is not None}


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides with AI_REVIEWER_ prefix."""
    mapping = {
        f"{_ENV_PREFIX}MIN_SEVERITY": "min_severity",
        f"{_ENV_PREFIX}MAX_FINDINGS_PER_FILE": ("max_findings_per_file", int),
        f"{_ENV_PREFIX}MAX_TOTAL_FINDINGS": ("max_total_findings", int),
        f"{_ENV_PREFIX}FIX_ENABLED": ("fix_enabled", lambda v: v.lower() in ("true", "1", "yes")),
        f"{_ENV_PREFIX}FIX_BRANCH_PREFIX": "fix_branch_prefix",
        f"{_ENV_PREFIX}CLAUDE_MODEL": "claude_model",
        f"{_ENV_PREFIX}CLAUDE_MAX_TOKENS": ("claude_max_tokens", int),
        f"{_ENV_PREFIX}TEST_CHECK_ENABLED": (
            "test_check_enabled",
            lambda v: v.lower() in ("true", "1", "yes"),
        ),
        f"{_ENV_PREFIX}TEST_CHECK_TIMEOUT": ("test_check_timeout", int),
    }

    for env_key, spec in mapping.items():
        value = os.environ.get(env_key)
        if value is None:
            continue
        if isinstance(spec, str):
            config[spec] = value
        else:
            field_name, converter = spec
            config[field_name] = converter(value)

    return config


def load_config(
    repo_config_content: str | None = None,
    default_rules_path: Path | None = None,
) -> ReviewConfig:
    """Load and merge configuration from all 3 layers.

    Args:
        repo_config_content: Raw YAML content of .ai-reviewer.yml from the repo (if any).
        default_rules_path: Override path for default rules (for testing).

    Returns:
        Validated ReviewConfig.
    """
    rules_path = default_rules_path or _DEFAULT_RULES_PATH

    # Layer 1: Default rules
    if rules_path.exists():
        raw = _load_yaml(rules_path)
        logger.debug("Loaded default rules from %s", rules_path)
    else:
        raw = {}
        logger.warning("Default rules not found at %s", rules_path)

    # Layer 2: Repo-level config
    if repo_config_content:
        repo_raw = yaml.safe_load(repo_config_content) or {}
        raw = _deep_merge(raw, repo_raw)
        logger.debug("Merged repo-level config")

    # Flatten to ReviewConfig fields
    flat = _flatten_config(raw)

    # Layer 3: Environment variable overrides
    flat = _apply_env_overrides(flat)

    return ReviewConfig(**flat)
