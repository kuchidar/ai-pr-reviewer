"""Tests for reviewer module."""

from unittest.mock import MagicMock, patch

from pr_reviewer.models import (
    Category,
    FileChange,
    PRInfo,
    ReviewConfig,
    Severity,
)
from pr_reviewer.reviewer import _parse_findings, review_pr


class TestParseFindings:
    def test_parse_json_array(self):
        response = """[
            {
                "file": "test.py",
                "line": 5,
                "severity": "high",
                "category": "security",
                "title": "SQL injection",
                "description": "Unsanitized input in query"
            }
        ]"""
        findings = _parse_findings(response, "test.py")
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert findings[0].category == Category.SECURITY

    def test_parse_json_object(self):
        response = '{"findings": [{"file": "a.py", "severity": "low", "category": "style", "title": "Naming", "description": "Bad name"}]}'
        findings = _parse_findings(response, "a.py")
        assert len(findings) == 1

    def test_parse_json_in_code_block(self):
        response = """```json
{"findings": [{"file": "b.py", "severity": "medium", "category": "performance", "title": "Slow loop", "description": "O(n^2) loop"}]}
```"""
        findings = _parse_findings(response, "b.py")
        assert len(findings) == 1
        assert findings[0].category == Category.PERFORMANCE

    def test_parse_empty_findings(self):
        response = '{"findings": []}'
        findings = _parse_findings(response, "test.py")
        assert findings == []

    def test_parse_invalid_json(self):
        response = "This is not JSON at all"
        findings = _parse_findings(response, "test.py")
        assert findings == []

    def test_parse_partial_invalid(self):
        response = '{"findings": [{"file": "a.py", "severity": "high", "category": "security", "title": "Good", "description": "Valid"}, {"invalid": true}]}'
        findings = _parse_findings(response, "a.py")
        # First finding is valid, second is invalid
        assert len(findings) == 1


class TestReviewPR:
    @patch("pr_reviewer.reviewer.anthropic.Anthropic")
    def test_review_respects_max_total(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Mock Claude response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"findings": [{"file": "a.py", "severity": "low", "category": "style", "title": "Issue", "description": "Desc"}]}')]
        mock_client.messages.create.return_value = mock_response

        pr_info = PRInfo(
            number=1, title="test", author="dev",
            head_branch="feat", base_branch="main", head_sha="abc",
        )
        files = [
            FileChange(filename=f"file{i}.py", status="added", patch="+code", content="code")
            for i in range(5)
        ]
        config = ReviewConfig(max_total_findings=2)

        findings = review_pr(pr_info, files, config, "fake-key")
        # Should stop after reaching max_total_findings
        assert len(findings) <= 2
