"""Shared test fixtures."""

import pytest

from pr_reviewer.models import (
    Category,
    FileChange,
    PRInfo,
    ReviewConfig,
    ReviewFinding,
    Severity,
)


@pytest.fixture
def sample_pr_info() -> PRInfo:
    return PRInfo(
        number=42,
        title="Add user authentication",
        body="Implements JWT-based authentication for the API.",
        author="developer123",
        head_branch="feature/auth",
        base_branch="main",
        head_sha="abc123def456",
        labels=["enhancement"],
        files=[
            FileChange(
                filename="src/auth.py",
                status="added",
                patch=(
                    "@@ -0,0 +1,20 @@\n"
                    "+import jwt\n"
                    "+import os\n"
                    "+\n"
                    "+SECRET = os.environ['JWT_SECRET']\n"
                    "+\n"
                    "+def create_token(user_id: str) -> str:\n"
                    "+    return jwt.encode({'user_id': user_id}, SECRET)\n"
                    "+\n"
                    "+def verify_token(token: str) -> dict:\n"
                    "+    return jwt.decode(token, SECRET, algorithms=['HS256'])\n"
                ),
                additions=10,
                deletions=0,
                sha="file_sha_123",
            ),
            FileChange(
                filename="requirements.txt",
                status="modified",
                patch="@@ -1,2 +1,3 @@\n flask\n+PyJWT\n requests\n",
                additions=1,
                deletions=0,
                sha="file_sha_456",
            ),
            FileChange(
                filename="package-lock.json",
                status="modified",
                patch="@@ large binary diff @@",
                additions=500,
                deletions=300,
                sha="file_sha_789",
            ),
        ],
    )


@pytest.fixture
def sample_config() -> ReviewConfig:
    return ReviewConfig(
        exclude_patterns=["*.lock", "package-lock.json"],
    )


@pytest.fixture
def sample_findings() -> list[ReviewFinding]:
    return [
        ReviewFinding(
            file="src/auth.py",
            line=4,
            severity=Severity.HIGH,
            category=Category.SECURITY,
            title="Hardcoded secret fallback risk",
            description=(
                "Using os.environ['JWT_SECRET'] will raise KeyError if not set, "
                "but there's no validation at startup."
            ),
            suggested_fix="SECRET = os.environ.get('JWT_SECRET')\nif not SECRET:\n    raise RuntimeError('JWT_SECRET not configured')",
        ),
        ReviewFinding(
            file="src/auth.py",
            line=10,
            severity=Severity.MEDIUM,
            category=Category.CORRECTNESS,
            title="Missing error handling in verify_token",
            description="jwt.decode can raise multiple exceptions that are not handled.",
            suggested_fix=None,
        ),
    ]
