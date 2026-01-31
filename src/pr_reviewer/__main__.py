"""CLI entry point for the PR reviewer."""

import argparse
import sys

from pr_reviewer.main import run_review


def main() -> int:
    parser = argparse.ArgumentParser(description="AI PR Review Agent")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--github-token", help="GitHub token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--anthropic-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    success = run_review(
        repo_full_name=args.repo,
        pr_number=args.pr,
        github_token=args.github_token,
        anthropic_api_key=args.anthropic_key,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
