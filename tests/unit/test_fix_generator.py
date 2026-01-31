"""Tests for fix generator."""

from unittest.mock import MagicMock, patch

from pr_reviewer.fix_generator import _extract_fixed_content, generate_fix_pr
from pr_reviewer.models import (
    Category,
    ReviewConfig,
    ReviewFinding,
    Severity,
)


class TestExtractFixedContent:
    def test_json_format(self):
        response = '{"fixed_content": "def hello():\\n    print(\\"hi\\")\\n"}'
        content = _extract_fixed_content(response)
        assert content is not None
        assert "def hello()" in content

    def test_code_block_format(self):
        response = """Here is the fix:
```python
def hello():
    print("hi")
```"""
        content = _extract_fixed_content(response)
        assert content is not None
        assert 'print("hi")' in content

    def test_no_content_found(self):
        response = "I cannot fix this file."
        content = _extract_fixed_content(response)
        assert content is None


class TestGenerateFixPR:
    def test_skips_when_no_fixable_findings(self, sample_pr_info):
        findings = [
            ReviewFinding(
                file="a.py",
                severity=Severity.MEDIUM,
                category=Category.CORRECTNESS,
                title="Issue",
                description="No fix available",
                suggested_fix=None,
            )
        ]
        gh = MagicMock()
        config = ReviewConfig()

        result = generate_fix_pr(findings, sample_pr_info, gh, config, "fake-key")
        assert result is None
        gh.create_branch.assert_not_called()

    @patch("pr_reviewer.fix_generator.anthropic.Anthropic")
    def test_creates_fix_pr(self, mock_anthropic_cls, sample_findings, sample_pr_info):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"fixed_content": "fixed code"}')]
        mock_client.messages.create.return_value = mock_response

        gh = MagicMock()
        gh.get_file_content.return_value = "original code"
        gh.get_file_sha.return_value = "sha123"
        gh.create_pull_request.return_value = "https://github.com/owner/repo/pull/99"

        config = ReviewConfig()
        url = generate_fix_pr(sample_findings, sample_pr_info, gh, config, "fake-key")

        assert url == "https://github.com/owner/repo/pull/99"
        gh.create_branch.assert_called_once()
        gh.commit_file.assert_called()
        gh.create_pull_request.assert_called_once()

    def test_handles_branch_creation_failure(self, sample_findings, sample_pr_info):
        gh = MagicMock()
        gh.create_branch.side_effect = Exception("Branch exists")

        config = ReviewConfig()
        result = generate_fix_pr(sample_findings, sample_pr_info, gh, config, "fake-key")
        assert result is None
