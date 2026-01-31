"""Tests for data models."""

from pr_reviewer.models import (
    Category,
    ReviewConfig,
    ReviewFinding,
    ReviewResult,
    Severity,
)


class TestReviewFinding:
    def test_create_finding(self):
        f = ReviewFinding(
            file="test.py",
            line=10,
            severity=Severity.HIGH,
            category=Category.SECURITY,
            title="Test issue",
            description="A test issue",
        )
        assert f.file == "test.py"
        assert f.severity == Severity.HIGH
        assert f.suggested_fix is None

    def test_finding_with_fix(self):
        f = ReviewFinding(
            file="test.py",
            severity=Severity.LOW,
            category=Category.STYLE,
            title="Style issue",
            description="Minor style problem",
            suggested_fix="fixed_code()",
        )
        assert f.suggested_fix == "fixed_code()"
        assert f.line is None


class TestReviewResult:
    def test_empty_result(self):
        r = ReviewResult()
        assert not r.has_issues
        assert r.critical_count == 0

    def test_result_with_findings(self, sample_findings):
        r = ReviewResult(findings=sample_findings)
        assert r.has_issues
        assert r.critical_count == 0
        assert len(r.findings) == 2

    def test_critical_count(self):
        findings = [
            ReviewFinding(
                file="a.py",
                severity=Severity.CRITICAL,
                category=Category.SECURITY,
                title="Critical",
                description="Critical issue",
            ),
            ReviewFinding(
                file="b.py",
                severity=Severity.HIGH,
                category=Category.CORRECTNESS,
                title="High",
                description="High issue",
            ),
        ]
        r = ReviewResult(findings=findings)
        assert r.critical_count == 1


class TestReviewConfig:
    def test_defaults(self):
        config = ReviewConfig()
        assert config.min_severity == Severity.LOW
        assert config.fix_enabled is True
        assert config.claude_model == "claude-sonnet-4-20250514"

    def test_custom_config(self):
        config = ReviewConfig(
            min_severity=Severity.HIGH,
            fix_enabled=False,
            claude_model="claude-opus-4-20250514",
        )
        assert config.min_severity == Severity.HIGH
        assert config.fix_enabled is False
