"""Tests for diff parser."""

from pr_reviewer.diff_parser import filter_files, parse_patch_line_numbers
from pr_reviewer.models import FileChange, PRInfo, ReviewConfig


class TestFilterFiles:
    def test_filter_excluded_patterns(self, sample_pr_info, sample_config):
        files = filter_files(sample_pr_info, sample_config)
        filenames = [f.filename for f in files]
        assert "src/auth.py" in filenames
        assert "package-lock.json" not in filenames

    def test_filter_removed_files(self):
        pr_info = PRInfo(
            number=1,
            title="test",
            author="dev",
            head_branch="feat",
            base_branch="main",
            head_sha="abc",
            files=[
                FileChange(filename="deleted.py", status="removed", patch="-old code"),
                FileChange(filename="added.py", status="added", patch="+new code"),
            ],
        )
        config = ReviewConfig()
        files = filter_files(pr_info, config)
        assert len(files) == 1
        assert files[0].filename == "added.py"

    def test_filter_no_patch(self):
        pr_info = PRInfo(
            number=1,
            title="test",
            author="dev",
            head_branch="feat",
            base_branch="main",
            head_sha="abc",
            files=[
                FileChange(filename="binary.png", status="added", patch=None),
                FileChange(filename="code.py", status="added", patch="+code"),
            ],
        )
        config = ReviewConfig()
        files = filter_files(pr_info, config)
        assert len(files) == 1
        assert files[0].filename == "code.py"


class TestParsePatchLineNumbers:
    def test_simple_addition(self):
        patch = (
            "@@ -0,0 +1,3 @@\n"
            "+line1\n"
            "+line2\n"
            "+line3\n"
        )
        ranges = parse_patch_line_numbers(patch)
        assert ranges == [(1, 3)]

    def test_mixed_changes(self):
        patch = (
            "@@ -10,5 +10,6 @@\n"
            " context\n"
            "-removed\n"
            "+added1\n"
            "+added2\n"
            " context\n"
            " context\n"
        )
        ranges = parse_patch_line_numbers(patch)
        assert len(ranges) >= 1
        # added1 is at line 11, added2 at line 12
        assert (11, 12) in ranges

    def test_empty_patch(self):
        ranges = parse_patch_line_numbers("")
        assert ranges == []
