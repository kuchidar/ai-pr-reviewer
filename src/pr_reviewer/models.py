"""Pydantic data models for the PR reviewer."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    CORRECTNESS = "correctness"
    STYLE = "style"


class ReviewFinding(BaseModel):
    """A single review finding from Claude."""

    file: str = Field(description="File path relative to repo root")
    line: Optional[int] = Field(default=None, description="Line number (if applicable)")
    severity: Severity
    category: Category
    title: str = Field(description="Short summary of the issue")
    description: str = Field(description="Detailed explanation")
    suggested_fix: Optional[str] = Field(
        default=None, description="Suggested code fix (if applicable)"
    )


class FileChange(BaseModel):
    """A file changed in a PR."""

    filename: str
    status: str = Field(description="added, modified, removed, renamed")
    patch: Optional[str] = Field(default=None, description="Unified diff patch")
    additions: int = 0
    deletions: int = 0
    content: Optional[str] = Field(default=None, description="Full file content for context")
    sha: Optional[str] = Field(default=None, description="File blob SHA")


class PRInfo(BaseModel):
    """Pull request metadata."""

    number: int
    title: str
    body: Optional[str] = None
    author: str
    head_branch: str
    base_branch: str
    head_sha: str
    labels: List[str] = Field(default_factory=list)
    files: List[FileChange] = Field(default_factory=list)


class TestResult(BaseModel):
    """CI test result for a check run."""

    name: str
    status: str = Field(description="queued, in_progress, completed")
    conclusion: Optional[str] = Field(
        default=None, description="success, failure, neutral, cancelled, timed_out, etc."
    )


class ReviewResult(BaseModel):
    """Aggregated result of a full PR review."""

    findings: List[ReviewFinding] = Field(default_factory=list)
    issue_urls: List[str] = Field(default_factory=list)
    fix_pr_url: Optional[str] = None
    test_results: List[TestResult] = Field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.findings) > 0

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)


class ReviewConfig(BaseModel):
    """Validated review configuration."""

    min_severity: Severity = Severity.LOW
    max_findings_per_file: int = 10
    max_total_findings: int = 50
    exclude_patterns: List[str] = Field(default_factory=list)
    categories: List[Category] = Field(
        default_factory=lambda: list(Category)
    )
    labels: Dict[str, str] = Field(
        default_factory=lambda: {
            "review": "ai-review",
            "automated": "automated",
            "fix": "ai-fix",
        }
    )
    fix_enabled: bool = True
    fix_branch_prefix: str = "ai-fix/"
    fix_max_files_per_pr: int = 10
    test_check_enabled: bool = True
    test_check_timeout: int = 300
    test_check_poll_interval: int = 30
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096
