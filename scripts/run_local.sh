#!/usr/bin/env bash
set -euo pipefail

# Local execution script for AI PR Reviewer
#
# Usage: ./scripts/run_local.sh owner/repo PR_NUMBER
#
# Required environment variables:
#   GITHUB_TOKEN     - GitHub personal access token
#   ANTHROPIC_API_KEY - Anthropic API key
#
# Optional environment variables:
#   LOG_LEVEL        - Logging level (default: INFO)
#   AI_REVIEWER_*    - Config overrides (see config.py)

REPO="${1:?Usage: $0 owner/repo PR_NUMBER}"
PR_NUMBER="${2:?Usage: $0 owner/repo PR_NUMBER}"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    echo "Error: GITHUB_TOKEN environment variable is required" >&2
    exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is required" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== AI PR Reviewer ==="
echo "Repository: $REPO"
echo "PR Number:  $PR_NUMBER"
echo "======================"

# Install in development mode if not already installed
if ! python -c "import pr_reviewer" 2>/dev/null; then
    echo "Installing pr_reviewer in development mode..."
    pip install -e "$PROJECT_DIR" >/dev/null
fi

python -m pr_reviewer --repo "$REPO" --pr "$PR_NUMBER"
