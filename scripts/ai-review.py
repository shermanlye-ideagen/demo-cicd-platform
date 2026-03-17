#!/usr/bin/env python
"""AI Code Review — Call Claude API for platform-aware code review.

Used by GitHub Actions workflows to review PRs against platform standards.

Author: Sherman Lye
Created: 2026-03-16

Usage:
    python scripts/ai-review.py \
        --diff /tmp/pr-diff.txt \
        --product demo-product \
        --standards config/platform-standards.yaml \
        --boundaries config/conventions/self-service-boundaries.yaml

    # Self-service mode (includes validation + scope results):
    python scripts/ai-review.py \
        --diff /tmp/pr-diff.txt \
        --product self-service \
        --standards config/platform-standards.yaml \
        --boundaries config/conventions/self-service-boundaries.yaml \
        --mode self-service \
        --validation-output /tmp/validation-output.txt \
        --scope-check /tmp/scope-check.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def read_file(path: str) -> str:
    """Read a file and return its contents."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"[File not found: {path}]"


def call_claude(system_prompt: str, user_prompt: str) -> str:
    """Call Claude API and return the response text."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    body = json.dumps({
        "model": os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
        return data["content"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Claude API error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def build_system_prompt(standards: str, boundaries: str, mode: str) -> str:
    """Build the system prompt with platform context."""
    if mode == "self-service":
        return f"""You are an AI platform governance assistant reviewing a self-service PR.

Your job is to validate changes against the platform's self-service boundaries and explain your findings clearly.

## Platform Standards
{standards}

## Self-Service Boundaries
{boundaries}

## Instructions
1. Check if all changed files are within the self-service customizable scope
2. For each warning or violation, quote the specific policy section that applies
3. Explain WHY the boundary exists (security, compliance, standardization)
4. If changes are within boundaries, confirm approval
5. If changes violate boundaries, explain what the team CAN do instead
6. Provide an overall assessment: AUTO-APPROVE or NEEDS-PLATFORM-REVIEW

Format your response as a GitHub PR comment in markdown. Start with a status badge:
- ✅ **Auto-Approved** — all changes within self-service boundaries
- ⚠️ **Needs Review** — some changes require platform team approval
- ❌ **Blocked** — changes violate platform policies"""
    else:
        return f"""You are an AI code reviewer for the Ideagen CI/CD platform.

Review the PR diff against these platform standards and self-service boundaries.

## Platform Standards
{standards}

## Self-Service Boundaries
{boundaries}

## Review Checklist
1. **Security**: Hardcoded secrets, credentials, API keys in source code
2. **Platform Compliance**: Forbidden file patterns (*.tf, helm/, charts/, kustomization.yaml)
3. **Convention Violations**: Incorrect file locations, missing required fields
4. **Code Quality**: Error handling, input validation, logging
5. **Best Practices**: Python/Docker best practices relevant to the changes

## Instructions
- Be specific: reference line numbers and file paths
- Be actionable: suggest how to fix each issue
- Be concise: focus on the most important findings
- Format as a clear markdown comment with sections

Start with a 1-line summary, then detail findings by category."""


def build_user_prompt(diff: str, product: str, mode: str,
                      validation_output: str = "", scope_check: str = "") -> str:
    """Build the user prompt with the PR diff and context."""
    prompt = f"## Product: {product}\n\n## PR Diff\n```\n{diff[:50000]}\n```"

    if mode == "self-service" and validation_output:
        prompt += f"\n\n## Validation Output\n```\n{validation_output}\n```"
    if mode == "self-service" and scope_check:
        prompt += f"\n\n## Scope Check\n```\n{scope_check}\n```"

    return prompt


def main():
    parser = argparse.ArgumentParser(description="AI Code Review via Claude API")
    parser.add_argument("--diff", required=True, help="Path to PR diff file")
    parser.add_argument("--product", required=True, help="Product name")
    parser.add_argument("--standards", required=True, help="Path to platform-standards.yaml")
    parser.add_argument("--boundaries", required=True, help="Path to self-service-boundaries.yaml")
    parser.add_argument("--mode", default="review", choices=["review", "self-service"])
    parser.add_argument("--validation-output", default="", help="Path to validation output")
    parser.add_argument("--scope-check", default="", help="Path to scope check output")
    parser.add_argument("--output", default="/tmp/ai-review-output.md", help="Output file")
    args = parser.parse_args()

    diff = read_file(args.diff)
    standards = read_file(args.standards)
    boundaries = read_file(args.boundaries)
    validation_output = read_file(args.validation_output) if args.validation_output else ""
    scope_check = read_file(args.scope_check) if args.scope_check else ""

    if not diff or diff.startswith("[File not found"):
        print("No diff content found, skipping review", file=sys.stderr)
        Path(args.output).write_text("No changes to review.")
        return

    system_prompt = build_system_prompt(standards, boundaries, args.mode)
    user_prompt = build_user_prompt(diff, args.product, args.mode,
                                    validation_output, scope_check)

    print(f"Calling Claude API for {args.mode} review of {args.product}...")
    review = call_claude(system_prompt, user_prompt)

    header = "## 🤖 AI Code Review\n\n" if args.mode == "review" else "## 🤖 AI Self-Service Validation\n\n"
    output = header + review + "\n\n---\n*Powered by Claude (Anthropic) — [Platform Standards](config/platform-standards.yaml)*\n"

    Path(args.output).write_text(output, encoding="utf-8")
    print(f"Review written to {args.output}")


if __name__ == "__main__":
    main()
