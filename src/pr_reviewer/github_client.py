"""GitHub API wrapper using PyGitHub."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from github import Github, GithubException
from github.PullRequest import PullRequest
from github.Repository import Repository

from pr_reviewer.models import FileChange, PRInfo, TestResult

logger = logging.getLogger(__name__)


@dataclass
class GitHubClient:
    """Wrapper around PyGitHub for PR review operations."""

    token: str
    repo_full_name: str
    _github: Github = field(init=False, repr=False)
    _repo: Repository = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._github = Github(self.token)
        self._repo = self._github.get_repo(self.repo_full_name)

    @property
    def repo(self) -> Repository:
        return self._repo

    def get_pr(self, pr_number: int) -> PullRequest:
        return self._repo.get_pull(pr_number)

    def get_pr_info(self, pr_number: int) -> PRInfo:
        """Fetch full PR information including file changes."""
        pr = self.get_pr(pr_number)
        files = []
        for f in pr.get_files():
            files.append(
                FileChange(
                    filename=f.filename,
                    status=f.status,
                    patch=f.patch,
                    additions=f.additions,
                    deletions=f.deletions,
                    sha=f.sha,
                )
            )

        return PRInfo(
            number=pr.number,
            title=pr.title,
            body=pr.body,
            author=pr.user.login,
            head_branch=pr.head.ref,
            base_branch=pr.base.ref,
            head_sha=pr.head.sha,
            labels=[label.name for label in pr.get_labels()],
            files=files,
        )

    def get_file_content(self, path: str, ref: str) -> str | None:
        """Get file content at a specific ref."""
        try:
            content_file = self._repo.get_contents(path, ref=ref)
            if isinstance(content_file, list):
                return None
            return content_file.decoded_content.decode("utf-8")
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def get_file_sha(self, path: str, ref: str) -> str | None:
        """Get file blob SHA at a specific ref."""
        try:
            content_file = self._repo.get_contents(path, ref=ref)
            if isinstance(content_file, list):
                return None
            return content_file.sha
        except GithubException as e:
            if e.status == 404:
                return None
            raise

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> str:
        """Create a GitHub issue and return its URL."""
        issue = self._repo.create_issue(
            title=title,
            body=body,
            labels=labels or [],
        )
        logger.info("Created issue #%d: %s", issue.number, issue.html_url)
        return issue.html_url

    def create_branch(self, branch_name: str, from_sha: str) -> None:
        """Create a new branch from a SHA."""
        ref = f"refs/heads/{branch_name}"
        self._repo.create_git_ref(ref=ref, sha=from_sha)
        logger.info("Created branch %s from %s", branch_name, from_sha[:8])

    def commit_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> None:
        """Create or update a file via Contents API.

        Args:
            path: File path in the repo.
            content: New file content.
            message: Commit message.
            branch: Target branch.
            sha: Existing file blob SHA (required for updates, None for new files).
        """
        if sha:
            self._repo.update_file(
                path=path,
                message=message,
                content=content,
                sha=sha,
                branch=branch,
            )
        else:
            self._repo.create_file(
                path=path,
                message=message,
                content=content,
                branch=branch,
            )
        logger.info("Committed %s to %s", path, branch)

    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> str:
        """Create a pull request and return its URL."""
        pr = self._repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
        )
        if labels:
            pr.add_to_labels(*labels)
        logger.info("Created PR #%d: %s", pr.number, pr.html_url)
        return pr.html_url

    def post_comment(self, pr_number: int, body: str) -> None:
        """Post a comment on a pull request."""
        pr = self.get_pr(pr_number)
        pr.create_issue_comment(body)
        logger.info("Posted comment on PR #%d", pr_number)

    def get_check_runs(self, ref: str) -> list[TestResult]:
        """Get check run results for a commit ref."""
        commit = self._repo.get_commit(ref)
        results = []
        for run in commit.get_check_runs():
            results.append(
                TestResult(
                    name=run.name,
                    status=run.status,
                    conclusion=run.conclusion,
                )
            )
        return results

    def get_repo_config(self, ref: str) -> str | None:
        """Try to read .ai-reviewer.yml from the repo."""
        return self.get_file_content(".ai-reviewer.yml", ref=ref)
