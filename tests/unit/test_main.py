"""Tests for orchestrator (main.py)."""

from unittest.mock import MagicMock, patch

from pr_reviewer.main import _should_skip
from pr_reviewer.models import PRInfo


class TestShouldSkip:
    def _make_pr_info(self, author="developer", head_branch="feature/x", labels=None):
        return PRInfo(
            number=1,
            title="test",
            author=author,
            head_branch=head_branch,
            base_branch="main",
            head_sha="abc",
            labels=labels or [],
        )

    def test_skip_bot_actor(self):
        pr = self._make_pr_info(author="dependabot[bot]")
        assert _should_skip(pr, MagicMock()) is True

    def test_skip_github_actions(self):
        pr = self._make_pr_info(author="github-actions")
        assert _should_skip(pr, MagicMock()) is True

    def test_skip_ai_fix_branch(self):
        pr = self._make_pr_info(head_branch="ai-fix/42")
        assert _should_skip(pr, MagicMock()) is True

    def test_skip_ai_fix_label(self):
        pr = self._make_pr_info(labels=["ai-fix"])
        assert _should_skip(pr, MagicMock()) is True

    def test_normal_pr_not_skipped(self):
        pr = self._make_pr_info()
        assert _should_skip(pr, MagicMock()) is False

    def test_multiple_labels_with_ai_fix(self):
        pr = self._make_pr_info(labels=["enhancement", "ai-fix", "urgent"])
        assert _should_skip(pr, MagicMock()) is True
