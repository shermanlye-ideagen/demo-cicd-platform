# Demo CI/CD Platform

## Overview

AI-powered CI/CD platform for Ideagen. Showcases Claude Code + GitHub Actions integration for 70+ products.

## Architecture

- **Convention + Policy + Platform Standards** — no per-product exceptions
- **AI Code Review** — Claude reviews every PR against platform standards
- **AI Release** — Claude generates release notes, JIRA versions, Confluence pages
- **Self-Service** — Product teams provision tenants + add services via Claude Code skill

## Skills

| Skill | Purpose |
|-------|---------|
| `/cicd-self-service` | Interactive portal: provision tenant, add service, query boundaries |

## Key Config Files

- `config/platform-standards.yaml` — Non-negotiable governance (SAST, SBOM, coverage floors, approval gates)
- `config/conventions/self-service-boundaries.yaml` — What teams can customize vs what's platform-protected
- `config/products.json` — Product registry
- `products/{name}/product.json` — Per-product registration (5-field schema)

## GitHub Actions Workflows

| Workflow | Trigger | What It Does |
|----------|---------|-------------|
| `_review-ai.yaml` | PR (reusable) | Claude reviews diff against platform standards |
| `release.yaml` | Tag push | AI release notes + GitHub Release + JIRA version + Confluence page |
| `_validate-self-service-pr.yaml` | PR with `self-service` label | Claude validates changes against self-service boundaries |
| `standard-pipeline.yaml` | PR/push (reusable) | Standard CI pipeline (build, test, scan, deploy) |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/ai-review.py` | Calls Claude API for code review / self-service validation |
| `scripts/release-jira.py` | Creates JIRA version and links resolved tickets |
| `scripts/release-confluence.py` | Creates Confluence release page |
| `scripts/resolve-config.py` | Resolves product config (convention + policy) |
| `scripts/detect-stack.py` | Auto-detects tech stack from repo files |
| `scripts/validate-all.py` | Validates all products and policies |

## Companion Repo

Product repos call this platform's reusable workflows. See: [demo-product](https://github.com/shermanlye-ideagen/demo-product)
