# AI-Powered CI/CD Platform Demo

Demonstrates AI-enhanced DevOps workflows using **GitHub Copilot + GitHub Actions** for Ideagen's unified CI/CD platform.

## What This Demonstrates

### GitHub Actions (Automated — Zero Manual Steps)

| Workflow | Trigger | What AI Does |
|----------|---------|-------------|
| **AI Code Review** | Every PR | GitHub Copilot reviews changes natively on PRs |
| **AI Release** | Tag push | Claude generates categorized release notes, creates JIRA version + Confluence page |
| **Self-Service Validation** | PR with `self-service` label | Validates changes against policies, posts results |

### Claude Code Skills (Interactive)

| Skill | Command | What It Does |
|-------|---------|-------------|
| **Self-Service Portal** | `/cicd-self-service "..."` | Provision tenants + add services via natural language |

## Architecture

```
Product Repo                        Platform Repo (this repo)
├── .github/workflows/ci.yaml      ├── .github/workflows/
│   (standard pipeline)            │   ├── release.yaml          ← Claude + JIRA + Confluence
│                                   │   └── _validate-self-service-pr.yaml
├── .platform/                      ├── config/
│   ├── config.yaml                 │   ├── platform-standards.yaml
│   └── hooks.yaml                  │   ├── conventions/
│                                   │   └── policies/
├── tenants/                        ├── scripts/
│   └── registry.yaml               │   ├── release-jira.py
│                                   │   └── release-confluence.py
└── src/                            └── products/
                                        └── {name}/product.json

AI Code Review: GitHub Copilot (native, repo settings)
```

## Platform Standards

- **Non-negotiable security**: SAST + SBOM required for ALL products
- **Uniform pipeline**: All products get the same CI/CD rigor — 4 environments, full scanning, load testing
- **Self-service boundaries**: Teams can provision tenants + add services. Everything else is platform-managed.
- **Zero exceptions**: No per-product overrides to security or compliance policies.

## Setup

### Secrets (GitHub repo settings)

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude API (release notes) |
| `ATLASSIAN_EMAIL` | JIRA/Confluence API |
| `ATLASSIAN_TOKEN` | JIRA/Confluence API |

### Variables (GitHub repo settings)

| Variable | Value |
|----------|-------|
| `ATLASSIAN_BASE_URL` | `https://ideagen.atlassian.net` |

### GitHub Copilot (repo settings)

Enable on all product repos: **Repo Settings → Code review → Copilot**

## Companion Repos

| Repo | Stack | Purpose |
|------|-------|---------|
| [devonway](https://github.com/shermanlye-ideagen/devonway) | .NET | Safety management |
| [iqmc](https://github.com/shermanlye-ideagen/iqmc) | .NET | Quality management |
| [lucidity](https://github.com/shermanlye-ideagen/lucidity) | PHP | Compliance & risk |
| [demo-product](https://github.com/shermanlye-ideagen/demo-product) | Python | Platform demo |
