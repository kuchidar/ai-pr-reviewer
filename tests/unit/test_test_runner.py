"""Tests for test runner module."""

from unittest.mock import MagicMock, patch

from pr_reviewer.models import ReviewConfig, TestResult
from pr_reviewer.test_runner import check_results_passed, wait_for_checks


class TestCheckResultsPassed:
    def test_empty_results(self):
        assert check_results_passed([]) is True

    def test_all_success(self):
        results = [
            TestResult(name="CI", status="completed", conclusion="success"),
            TestResult(name="Lint", status="completed", conclusion="success"),
        ]
        assert check_results_passed(results) is True

    def test_with_failure(self):
        results = [
            TestResult(name="CI", status="completed", conclusion="success"),
            TestResult(name="Lint", status="completed", conclusion="failure"),
        ]
        assert check_results_passed(results) is False

    def test_neutral_is_ok(self):
        results = [
            TestResult(name="CI", status="completed", conclusion="neutral"),
        ]
        assert check_results_passed(results) is True

    def test_skipped_is_ok(self):
        results = [
            TestResult(name="CI", status="completed", conclusion="skipped"),
        ]
        assert check_results_passed(results) is True


class TestWaitForChecks:
    def test_disabled(self):
        gh = MagicMock()
        config = ReviewConfig(test_check_enabled=False)
        results = wait_for_checks(gh, "main", config)
        assert results == []
        gh.get_check_runs.assert_not_called()

    @patch("pr_reviewer.test_runner.time.sleep")
    def test_immediate_completion(self, mock_sleep):
        gh = MagicMock()
        gh.get_check_runs.return_value = [
            TestResult(name="CI", status="completed", conclusion="success"),
        ]
        config = ReviewConfig(test_check_timeout=60, test_check_poll_interval=10)

        results = wait_for_checks(gh, "abc123", config)
        assert len(results) == 1
        assert results[0].conclusion == "success"
        mock_sleep.assert_not_called()

    @patch("pr_reviewer.test_runner.time.sleep")
    def test_polls_until_complete(self, mock_sleep):
        gh = MagicMock()
        gh.get_check_runs.side_effect = [
            [TestResult(name="CI", status="in_progress", conclusion=None)],
            [TestResult(name="CI", status="completed", conclusion="success")],
        ]
        config = ReviewConfig(test_check_timeout=60, test_check_poll_interval=10)

        results = wait_for_checks(gh, "abc123", config)
        assert len(results) == 1
        assert results[0].conclusion == "success"
        assert mock_sleep.call_count == 1
