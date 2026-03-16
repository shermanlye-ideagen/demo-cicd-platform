# AI-Powered CI/CD Platform Demo

Demonstrates AI-enhanced DevOps workflows using **Claude Code + GitHub Actions** for Ideagen's unified CI/CD platform.

## What This Demonstrates

### GitHub Actions (Automated — Zero Manual Steps)

| Workflow | Trigger | What AI Does |
|----------|---------|-------------|
| **AI Code Review** | Every PR | Claude reviews changes against platform standards, comments with findings |
| **AI Release** | Tag push | Claude generates categorized release notes, creates JIRA version + Confluence page |
| **Self-Service Validation** | PR with `self-service` label | Claude validates against policies, explains decisions with quotes |

### Claude Code Skills (Interactive)

| Skill | Command | What It Does |
|-------|---------|-------------|
| **Self-Service Portal** | `/cicd-self-service "..."` | Provision tenants + add services via natural language |

## Architecture

```
Product Repo                        Platform Repo (this repo)
├── .github/workflows/ci.yaml      ├── .github/workflows/
│   (calls platform workflows)     │   ├── _review-ai.yaml      ← Claude API
│                                   │   ├── release.yaml          ← Claude + JIRA + Confluence
├── .platform/                      │   └── _validate-self-service-pr.yaml
│   ├── config.yaml                 ├── config/
│   └── hooks.yaml                  │   ├── platform-standards.yaml
│                                   │   ├── conventions/
├── tenants/                        │   └── policies/
│   └── registry.yaml               ├── scripts/
│                                   │   ├── ai-review.py          ← Claude API caller
└── src/                            │   ├── release-jira.py
                                    │   └── release-confluence.py
```

## Platform Standards

- **Non-negotiable security**: SAST + SBOM required for ALL products
- **Tier-based governance**: Bronze (dev) → Silver (production) → Gold (enterprise)
- **Self-service boundaries**: Teams can provision tenants + add services. Everything else is platform-managed.
- **Zero exceptions**: No per-product overrides to security or compliance policies.

## Setup

### Secrets (GitHub repo settings)

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude API calls |
| `ATLASSIAN_EMAIL` | JIRA/Confluence API |
| `ATLASSIAN_TOKEN` | JIRA/Confluence API |

### Variables (GitHub repo settings)

| Variable | Value |
|----------|-------|
| `ATLASSIAN_BASE_URL` | `https://ideagen.atlassian.net` |

## Companion Repo

See [demo-product](https://github.com/shermanlye-ideagen/demo-product) for a sample product that uses this platform.
