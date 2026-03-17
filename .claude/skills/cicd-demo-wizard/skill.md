---
name: cicd-demo-wizard
description: "Full orchestrated demo of the AI-Powered CI/CD Platform. Interactive wizard that walks through product onboarding, PR creation, AI review, merge, deployment through all environments, and release — with dashboard visibility at every step."
user_invocable: true
arguments: "[product] — Optional: devonway, iqmc, or lucidity. If not specified, asks interactively."
---

# CICD Demo Wizard — Full Platform Orchestration

This is a **rigid** skill. Follow every phase exactly in order. Pause and ask the user before proceeding between phases.

## Overview

This wizard demonstrates the entire AI-Powered CI/CD Platform lifecycle:

```
Phase 0: Setup & Cleanup
Phase 1: Product Onboarding (as Platform Team)
Phase 2: Feature Development (as Product Team)
Phase 3: AI Code Review
Phase 4: Merge to Platform
Phase 5: Test Environment Pipeline
Phase 6: Perf Environment Pipeline
Phase 7: Staging Environment Pipeline
Phase 8: Release & Documentation
Phase 9: Summary & Impact
```

At each phase, explain what's happening, who is acting (Platform Team vs Product Team), and tell the user to watch the dashboard.

## Prerequisites

Before starting, verify:
1. Dashboard is running at http://localhost:5175 (or similar port)
2. GitHub CLI is authenticated (`gh auth status`)
3. All demo repos exist: demo-product, devonway, iqmc, lucidity
4. ANTHROPIC_API_KEY secret is set on product repos

If any prerequisite fails, help the user fix it before proceeding.

---

## Phase 0: Setup & Cleanup

**Role: Platform Team**

Ask the user using AskUserQuestion:

**"Welcome to the AI-Powered CI/CD Platform Demo! Let's set up."**

Questions to ask (all at once):
1. Which product to demo? (DevonWay .NET Gold / IQMC .NET Silver / Lucidity PHP Bronze)
2. Clean up previous test data? (Yes full cleanup / No keep existing)
3. Is the dashboard visible at http://localhost:5175?

If cleanup requested:
1. Close all open PRs on the selected product repo: `gh pr list --state open --repo {repo} | close each`
2. Delete all releases: `gh release list --repo {repo} | delete each`
3. Delete all tags: `git tag -l | delete each locally and remotely`
4. Delete feature branches: `git push origin --delete` for any non-main branches
5. Prune remote: `git remote prune origin`

After cleanup, confirm: "Clean slate. Dashboard should show {product} with no active changes."

---

## Phase 1: Product Onboarding

**Role: Platform Team**

Tell the user:
> "You're now acting as the **Platform Team**. A product team has requested onboarding for {product}. Let's register it in the platform."

Ask using AskUserQuestion:
**"The {product} team has submitted an onboarding request. Ready to proceed?"**
- Yes, onboard {product}
- Show me what onboarding does first

If they want to see what it does, explain:
1. Scan the repo to detect tech stack
2. Register product in `config/products.json`
3. Create `products/{name}/product.json`
4. Scaffold `.platform/` config files
5. Generate CI/CD pipeline (GitHub Actions)

Then confirm the product is already registered in demo-cicd-platform:
```bash
cat demo-cicd-platform/config/products.json | grep {product}
cat demo-cicd-platform/products/{product}/product.json
```

Show the product.json contents and explain: "This is the 5-field standardized schema. The platform auto-detects everything else."

Tell user: "Check the dashboard — {product} should appear as a row with 'No active changes'."

---

## Phase 2: Feature Development

**Role: Product Team**

Tell the user:
> "You're now acting as the **{product} Product Team**. You need to add a new feature. Let's create a branch and open a PR."

Steps (execute with 3-second delays between each):

1. **Create branch:**
   ```bash
   cd {product_repo_path}
   git checkout main && git pull
   git checkout -b feat/new-feature
   ```

2. **Add code with intentional security issues** (for AI review to catch):
   - For .NET: Add a controller with hardcoded connection string, SQL injection, command injection
   - For PHP: Add an endpoint with shell_exec, hardcoded credentials
   - For Python: Add subprocess.run with shell=True, hardcoded secrets

3. **Commit:**
   ```bash
   git add -A
   git commit -m "feat: add {feature_description}"
   ```

4. **Push:**
   ```bash
   git push -u origin feat/new-feature
   ```

5. **Open PR:**
   ```bash
   gh pr create --title "feat: {feature_description}" --body "## Summary\n- {description}\n\n## Test plan\n- [ ] Verify endpoints work"
   ```

Tell user: "PR created! Watch the dashboard — a new row should appear under {product} with ✅ PR Open. The AI Review and Tests columns should start showing ⏳."

---

## Phase 3: AI Code Review

**Role: Automated (Claude AI)**

Tell the user:
> "The AI Code Review is now running automatically. Claude is reviewing the PR against platform standards."

Wait for the workflow to complete:
```bash
# Get latest run ID and watch it
RUN_ID=$(gh run list --repo {repo} --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Once complete, show the results:
```bash
gh run view $RUN_ID --repo {repo} | grep -E "^[✓X]"
```

Then fetch and display the AI review comment:
```bash
gh api repos/{repo}/issues/{pr_number}/comments | python -c "import sys,json; comments=json.load(sys.stdin); [print(c['body'][:500]) for c in comments if 'AI Code Review' in c.get('body','')]"
```

Tell user:
> "Claude found security issues! Check the PR on GitHub to see the full review. Dashboard should now show ✅ AI Review (or ❌ if it found critical issues)."

Ask: **"Ready to proceed to merge? In a real workflow, the team would fix the issues first."**
- Yes, merge anyway (for demo purposes)
- Let me check the review on GitHub first

---

## Phase 4: Merge to Platform

**Role: Product Team → Platform**

Tell the user:
> "Merging the PR to main. This triggers the Standard Pipeline which deploys to the Test environment."

```bash
gh pr merge {pr_number} --repo {repo} --merge --delete-branch
```

Tell user: "PR merged! Watch the dashboard — the 'Merged to Platform' column should flip to ✅."

---

## Phase 5: Test Environment Pipeline

**Role: Automated (Platform)**

Tell the user:
> "The Standard Pipeline is now running on main. This includes: Build → Tests → SAST (SonarQube) → SBOM (Veracode) → E2E (Playwright) → Contract (Pact) → Security Verification → Container Push → Deploy to Test → New Relic Baseline."

Wait for Standard Pipeline:
```bash
sleep 5
RUN_ID=$(gh run list --repo {repo} --workflow "standard-pipeline.yaml" --branch main --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Show results:
```bash
gh run view $RUN_ID --repo {repo} | grep -E "^[✓X]|  [✓X]"
```

Tell user: "Standard Pipeline complete! All jobs passed. Dashboard 'Test' column should show ✅."

---

## Phase 6: Perf Environment Pipeline

**Role: Automated (Platform)**

Tell the user:
> "The Perf Pipeline auto-triggered after Standard Pipeline passed. Running: K6 Baseline Load → Stress Test → Spike Test → Long-Duration → Resource Profiling → Network Simulation → E2E Under Load → New Relic Report."

Wait for Perf Pipeline:
```bash
sleep 10
RUN_ID=$(gh run list --repo {repo} --workflow "perf-pipeline.yaml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Tell user: "Perf Pipeline complete! All K6 performance tests passed. Dashboard 'Perf' column should show ✅."

---

## Phase 7: Staging Environment Pipeline

**Role: Automated (Platform) + Manual UAT Gate**

Tell the user:
> "The Staging Pipeline auto-triggered after Perf Pipeline passed. Running: Deploy to Staging → Integration Tests → E2E Business Validation → UAT → Security & Compliance (Veracode) → Observability Validation."

Wait for Staging Pipeline:
```bash
sleep 10
RUN_ID=$(gh run list --repo {repo} --workflow "staging-pipeline.yaml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Tell user: "Staging Pipeline complete! Dashboard 'Staging' column should show ✅. The full pipeline — from PR to Staging — is now green."

---

## Phase 8: Release & Documentation

**Role: Platform Team**

Tell the user:
> "Now let's create a release. This triggers: AI-generated release notes → GitHub Release → JIRA version → Confluence release page."

Ask: **"Ready to create release v1.0.0 for {product}?"**

Steps:
```bash
cd {product_repo_path}
git checkout main && git pull
git tag v1.0.0
git push origin v1.0.0
```

Wait for Release Pipeline:
```bash
sleep 5
RUN_ID=$(gh run list --repo {repo} --workflow "release.yaml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Show created artifacts:
```bash
echo "=== GitHub Release ==="
gh release view v1.0.0 --repo {repo}

echo "=== JIRA + Confluence ==="
gh run view $RUN_ID --repo {repo} --log | grep -E "(Created JIRA|Confluence page|✅|URL:)"
```

Tell user: "Release complete! 4 artifacts created automatically: GitHub Release with AI notes, JIRA version, Confluence release page."

---

## Phase 9: Summary & Impact

Tell the user:

> ## Demo Complete!
>
> Here's what just happened — the full lifecycle of a change:
>
> | Phase | Who | What | Time |
> |-------|-----|------|------|
> | Onboard | Platform Team | Product registered in platform | Already done |
> | Develop | Product Team | Feature branch + PR created | 30 seconds |
> | AI Review | Claude (automated) | Security issues found + commented | ~20 seconds |
> | Merge | Product Team | PR merged to main | Instant |
> | Test Env | Platform (automated) | 11 jobs: build, test, SAST, SBOM, E2E, deploy | ~1 minute |
> | Perf Env | Platform (automated) | 10 jobs: K6 load/stress/spike, NR report | ~1 minute |
> | Staging | Platform (automated) | 6 jobs: integration, UAT, compliance | ~1 minute |
> | Release | Platform Team | AI notes + GitHub + JIRA + Confluence | ~30 seconds |
>
> **Total: PR to Staging in under 5 minutes. Fully automated. Zero manual steps except the initial PR.**
>
> This runs the same way for all 70+ Ideagen products:
> - DevonWay (.NET, Gold tier) — same pipeline
> - IQMC (.NET, Silver tier) — same pipeline
> - Lucidity (PHP, Bronze tier) — same pipeline
>
> The dashboard shows the real-time status of every product across every environment.

Ask: **"Would you like to demo another product, or are we done?"**
- Demo another product (restart from Phase 1)
- Done — wrap up
