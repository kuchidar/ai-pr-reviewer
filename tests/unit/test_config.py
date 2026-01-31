"""Tests for configuration loading."""

import os
from pathlib import Path

import pytest

from pr_reviewer.config import _deep_merge, _flatten_config, load_config
from pr_reviewer.models import Severity


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}, "y": 3}
        override = {"x": {"b": 99, "c": 100}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 99, "c": 100}, "y": 3}

    def test_override_replaces_non_dict(self):
        base = {"a": [1, 2]}
        override = {"a": [3, 4, 5]}
        result = _deep_merge(base, override)
        assert result == {"a": [3, 4, 5]}


class TestFlattenConfig:
    def test_flatten_full(self):
        raw = {
            "review": {
                "min_severity": "high",
                "max_findings_per_file": 5,
                "max_total_findings": 20,
            },
            "exclude_patterns": ["*.lock"],
            "fix": {
                "enabled": False,
                "branch_prefix": "fix/",
            },
            "claude": {
                "model": "claude-opus-4-20250514",
            },
        }
        flat = _flatten_config(raw)
        assert flat["min_severity"] == "high"
        assert flat["max_findings_per_file"] == 5
        assert flat["fix_enabled"] is False
        assert flat["fix_branch_prefix"] == "fix/"
        assert flat["claude_model"] == "claude-opus-4-20250514"

    def test_flatten_empty(self):
        flat = _flatten_config({})
        assert flat == {}


class TestLoadConfig:
    def test_load_defaults(self):
        config = load_config()
        assert config.min_severity == Severity.LOW
        assert "*.lock" in config.exclude_patterns
        assert config.fix_enabled is True

    def test_repo_config_override(self):
        repo_yaml = """
review:
  min_severity: high
fix:
  enabled: false
"""
        config = load_config(repo_config_content=repo_yaml)
        assert config.min_severity == Severity.HIGH
        assert config.fix_enabled is False

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("AI_REVIEWER_MIN_SEVERITY", "critical")
        monkeypatch.setenv("AI_REVIEWER_FIX_ENABLED", "false")
        config = load_config()
        assert config.min_severity == Severity.CRITICAL
        assert config.fix_enabled is False

    def test_3_layer_priority(self, monkeypatch):
        """Env vars override repo config which overrides defaults."""
        repo_yaml = """
review:
  min_severity: high
"""
        monkeypatch.setenv("AI_REVIEWER_MIN_SEVERITY", "critical")
        config = load_config(repo_config_content=repo_yaml)
        # Env var wins over repo config
        assert config.min_severity == Severity.CRITICAL
