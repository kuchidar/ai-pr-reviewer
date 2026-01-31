"""Tests for issue creator."""

from unittest.mock import MagicMock

from pr_reviewer.issue_creator import _build_issue_body, _build_issue_title, create_issues
from pr_reviewer.models import Category, ReviewConfig, Severity


class TestBuildIssueTitle:
    def test_critical_prefix(self, sample_findings, sample_pr_info):
        finding = sample_findings[0]
        finding.severity = Severity.CRITICAL
        title = _build_issue_title(finding, sample_pr_info)
        assert "[重大]" in title
        assert "PR #42" in title

    def test_includes_finding_title(self, sample_findings, sample_pr_info):
        title = _build_issue_title(sample_findings[0], sample_pr_info)
        assert sample_findings[0].title in title


class TestBuildIssueBody:
    def test_contains_file_info(self, sample_findings, sample_pr_info):
        body = _build_issue_body(sample_findings[0], sample_pr_info)
        assert "src/auth.py" in body
        assert "セキュリティ" in body

    def test_includes_suggested_fix(self, sample_findings, sample_pr_info):
        body = _build_issue_body(sample_findings[0], sample_pr_info)
        assert "修正案" in body
        assert "RuntimeError" in body

    def test_no_fix_section_when_none(self, sample_findings, sample_pr_info):
        body = _build_issue_body(sample_findings[1], sample_pr_info)
        assert "修正案" not in body


class TestCreateIssues:
    def test_creates_issues_for_all_findings(self, sample_findings, sample_pr_info):
        gh = MagicMock()
        gh.create_issue.return_value = "https://github.com/owner/repo/issues/1"

        config = ReviewConfig()
        urls = create_issues(sample_findings, sample_pr_info, gh, config)

        assert len(urls) == 2
        assert gh.create_issue.call_count == 2

    def test_handles_api_failure(self, sample_findings, sample_pr_info):
        gh = MagicMock()
        gh.create_issue.side_effect = Exception("API error")

        config = ReviewConfig()
        urls = create_issues(sample_findings, sample_pr_info, gh, config)

        assert len(urls) == 0

    def test_uses_correct_labels(self, sample_findings, sample_pr_info):
        gh = MagicMock()
        gh.create_issue.return_value = "https://github.com/owner/repo/issues/1"

        config = ReviewConfig()
        create_issues(sample_findings[:1], sample_pr_info, gh, config)

        call_kwargs = gh.create_issue.call_args
        assert "ai-review" in call_kwargs.kwargs["labels"]
        assert "automated" in call_kwargs.kwargs["labels"]
