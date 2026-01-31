"""Tests for commenter module."""

from unittest.mock import MagicMock

from pr_reviewer.commenter import _build_approve_comment, _build_findings_comment, post_review_comment
from pr_reviewer.models import ReviewResult, TestResult


class TestBuildApproveComment:
    def test_contains_no_issues(self):
        comment = _build_approve_comment()
        assert "No Issues Found" in comment


class TestBuildFindingsComment:
    def test_contains_finding_count(self, sample_findings):
        result = ReviewResult(findings=sample_findings)
        comment = _build_findings_comment(result)
        assert "2" in comment
        assert "issue(s)" in comment

    def test_contains_findings_table(self, sample_findings):
        result = ReviewResult(findings=sample_findings)
        comment = _build_findings_comment(result)
        assert "| Severity |" in comment
        assert "src/auth.py" in comment

    def test_contains_issue_urls(self, sample_findings):
        result = ReviewResult(
            findings=sample_findings,
            issue_urls=["https://github.com/o/r/issues/1", "https://github.com/o/r/issues/2"],
        )
        comment = _build_findings_comment(result)
        assert "Created Issues" in comment
        assert "issues/1" in comment

    def test_contains_fix_pr_url(self, sample_findings):
        result = ReviewResult(
            findings=sample_findings,
            fix_pr_url="https://github.com/o/r/pull/99",
        )
        comment = _build_findings_comment(result)
        assert "Fix PR" in comment
        assert "pull/99" in comment

    def test_contains_test_results(self, sample_findings):
        result = ReviewResult(
            findings=sample_findings,
            test_results=[
                TestResult(name="CI", status="completed", conclusion="success"),
                TestResult(name="Lint", status="completed", conclusion="failure"),
            ],
        )
        comment = _build_findings_comment(result)
        assert "CI Check Results" in comment
        assert "CI" in comment


class TestPostReviewComment:
    def test_posts_approve_when_no_issues(self):
        gh = MagicMock()
        result = ReviewResult()
        post_review_comment(42, result, gh)
        gh.post_comment.assert_called_once()
        body = gh.post_comment.call_args[0][1]
        assert "No Issues Found" in body

    def test_posts_findings_when_issues(self, sample_findings):
        gh = MagicMock()
        result = ReviewResult(findings=sample_findings)
        post_review_comment(42, result, gh)
        gh.post_comment.assert_called_once()
        body = gh.post_comment.call_args[0][1]
        assert "Summary" in body
