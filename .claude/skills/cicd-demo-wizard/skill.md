---
name: cicd-demo-wizard
description: "Full orchestrated demo of the AI-Powered CI/CD Platform. Interactive wizard that walks through product onboarding, tenant provisioning, PR creation, AI review, merge, tenant-aware deployment through all environments, and release — with dashboard visibility at every step."
user_invocable: true
arguments: "[product] — Optional: devonway, iqmc, lucidity, or demo-product. If not specified, asks interactively."
---

# CICD Demo Wizard — Full Platform Orchestration

This is a **rigid** skill. Follow every phase exactly in order. Pause and ask the user before proceeding between phases.

## Overview

This wizard demonstrates the entire AI-Powered CI/CD Platform lifecycle:

```
Phase 0:  Setup & Cleanup
Phase 1:  Product Onboarding (6-phase lifecycle)
Phase 2:  Tenant Provisioning (provision tenants at different tiers)
Phase 3:  Feature Development (as Product Team — PR with intentional issues)
Phase 4:  AI Code Review (GitHub Copilot — automated)
Phase 5:  Merge to Main
Phase 6:  Deploy to Test (canary tenant → ring rollout)
Phase 7:  Deploy to Perftest (load/stress/spike tests)
Phase 8:  Deploy to Staging (UAT + compliance)
Phase 9:  Release & Documentation (AI notes + JIRA + Confluence)
Phase 10: Summary & Impact
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

Before asking, read `config/products.json` to get the list of registered products. Build the product choices dynamically from the registry — do NOT hardcode product names. Products are listed by name only (no tier labels).

Questions to ask (all at once):
1. Which product to demo? (List each product from `products.json` by name only — e.g. "DevonWay", "IQMC", "Lucidity", "Demo Product" — derived from the registry, not hardcoded)
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

## Phase 1: Product Onboarding (6-Phase Lifecycle)

**Role: Platform Team**

Tell the user:
> "You're now the **Platform Team (Vertex)**. A product team has requested onboarding for {product}. The Platform Team owns the entire onboarding process — scanning, registration, scaffolding, infra provisioning, and readiness checks. This is run via `/cicd-onboard`."

Ask using AskUserQuestion:
**"The {product} team has submitted an onboarding request. Ready to walk through onboarding?"**
- Yes, walk through the 6-phase onboarding
- Show me what each phase does first

Present the 6-phase onboarding lifecycle (always show this, whether they pick "walk through" or "show me first"):

> ### The 6-Phase Onboarding Lifecycle
>
> | # | Phase | Skill | What Happens |
> |---|-------|-------|-------------|
> | 1 | Migrate | `/cicd-migrate-repo` | Clone from Bitbucket → create GitHub repo → push (skipped if already on GitHub) |
> | 2 | Scan | `/cicd-scan` | Auto-detect tech stack, CI/CD system, IaC, deploy target, services |
> | 3 | Register | `/cicd-register` | Generate `product.json` (4 fields: name, team, repo, tenancy) → update `products.json` |
> | 4 | Scaffold | `/cicd-scaffold` | Generate thin-caller `ci.yaml` → push to product repo |
> | 5 | Infra | `/cicd-infra` | Provision TFC workspaces → Terraform plan/apply (or import existing) |
> | 6 | Readiness | `/cicd-readiness-check` | First pipeline run → verify security/quality gates → readiness report |
>
> All products get the same pipeline rigor — no tier selection needed. The Platform Team (Vertex) owns and runs the entire onboarding process.

Then walk through each phase for the demo product:

**Phase 1.1 — Migrate:** Check if the product repo exists on GitHub:
```bash
gh repo view shermanlye-ideagen/{product} --json name,url -q '.url'
```
Tell user: "Repo already exists on GitHub — Phase 1 (Migrate) is skipped."

**Phase 1.2 — Scan:** Show what the scan detects. Read the product's `product.json` to show detected stack info:
```bash
cat products/{product}/product.json
```
Explain what the scanner detects: tech stack, deploy target, runtime version, services, etc.

**Phase 1.3 — Register:** Show the product is registered in the platform:
```bash
# Show registry entry
python -c "import json; data=json.load(open('config/products.json')); entry=[p for p in data['products'] if p['name']=='{product}'][0]; print(json.dumps(entry, indent=2))"
```
Explain: "This is the standardized registration — 4 required fields. The platform auto-detects everything else via conventions + policies."

**Phase 1.4 — Scaffold:** Show the CI/CD workflow that was scaffolded in the product repo:
```bash
gh api repos/shermanlye-ideagen/{product}/contents/.github/workflows -q '.[].name'
```
Explain: "The scaffold phase generates thin-caller workflows that reference the platform's reusable workflows. Product repos never contain pipeline logic — only the call."

**Phase 1.5 — Infra:** Explain that in production, this provisions TFC workspaces and runs Terraform plan/apply per environment (test, perftest, staging, prod). For the demo, infrastructure is pre-provisioned.

**Phase 1.6 — Readiness:** Explain that the readiness check verifies: security gates pass (SAST, SBOM), quality gates pass (80% coverage, 5% max duplication), environments are provisioned, and the pipeline-registry entry is valid.

Tell user: "All 6 phases complete. {product} is fully onboarded. Check the dashboard — it should appear as a row with 'No active changes'."

---

## Phase 2: Tenant Provisioning

**Role: Product Team**

Tell the user:
> "You're now acting as the **Product Team**. You know your customers and their infrastructure needs. Each customer is a **tenant** with its own infrastructure tier. Tenant tier (bronze/silver/gold) controls infrastructure sizing — compute, database mode, encryption, monitoring — NOT pipeline behavior. The Product Team owns the tenant registry in their repo."

Ask using AskUserQuestion:
**"Ready to provision two tenants for {product}?"**
- Yes, provision both tenants
- Explain tenant tiers first

If they want an explanation first:
> ### Tenant Tiers (Infrastructure Sizing)
>
> | Tier | Database | Compute | Encryption | Monitoring | Backup |
> |------|----------|---------|------------|------------|--------|
> | Bronze | Shared RDS | t4g.small | AWS-managed | Email alerts | 7-day |
> | Silver | Dedicated RDS (t4g.medium) | t4g.medium | AWS-managed | CloudWatch | 14-day |
> | Gold | Dedicated RDS (r6g.large, multi-AZ) | m6g.large | CMK (customer-managed) | PagerDuty + NR | 30-day |
>
> These tiers control infrastructure only. The CI/CD pipeline is identical for all products and all tenants.

Create `tenants/registry.yaml` in the product repo with two tenants:

```yaml
apiVersion: v1
kind: TenantRegistry
product: {PRODUCT_NAME}

tenants:
  - name: acme-corp
    tier: bronze
    region: us-east-1
    status: active
    created_at: "{TODAY_DATE}"

  - name: enterprise-client
    tier: gold
    region: us-east-1
    status: active
    created_at: "{TODAY_DATE}"
    compliance:
      data_residency: us
      cmk_encryption: true
      backup_retention_days: 30
```

Steps:
```bash
cd {product_repo_path}
git checkout main && git pull
# Create tenants/registry.yaml with the content above
mkdir -p tenants
# Write the file
git add tenants/registry.yaml
git commit -m "feat: provision tenants acme-corp (bronze) and enterprise-client (gold)"
git push origin main
```

After push, explain:
> "Pushing `tenants/registry.yaml` triggers the **Tenant Provisioning Workflow**. For each tenant, Crossplane creates a `TenantInfra` custom resource that provisions:
> - A dedicated Kubernetes namespace (`{product}-{tenant}`)
> - RBAC rules scoped to the tenant namespace
> - NetworkPolicy isolating tenant traffic
> - Tier-appropriate infrastructure: `acme-corp` gets shared DB + basic monitoring (bronze), `enterprise-client` gets dedicated multi-AZ RDS + CMK encryption + PagerDuty (gold)
>
> The tenant registry is NOT per-environment — the same `tenants/registry.yaml` defines all tenants. The provisioning workflow creates tenant infrastructure in the target environment based on the git event."

Tell user: "Check the dashboard — two tenants should appear under {product}."

---

## Phase 3: Feature Development

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

Tell user: "PR created! Watch the dashboard — a new row should appear under {product} with PR Open. The AI Review and Tests columns should start showing activity."

---

## Phase 4: AI Code Review

**Role: Automated (GitHub Copilot)**

Tell the user:
> "The AI Code Review is now running automatically. GitHub Copilot reviews every PR natively against platform standards."

Wait for the review to appear:
```bash
# Check for Copilot review comments
gh api repos/{repo}/pulls/{pr_number}/reviews -q '.[].body' | head -20
```

Tell user:
> "GitHub Copilot found security issues! Check the PR on GitHub to see the full review. Dashboard should now show AI Review activity."

Ask: **"Ready to proceed to merge? In a real workflow, the team would fix the issues first."**
- Yes, merge anyway (for demo purposes)
- Let me check the review on GitHub first

---

## Phase 5: Merge to Main

**Role: Product Team**

Tell the user:
> "Merging the PR to main. This triggers the Standard Pipeline which builds, tests, scans, and deploys through environments."

```bash
gh pr merge {pr_number} --repo {repo} --merge --delete-branch
```

Tell user: "PR merged! Watch the dashboard — the pipeline will begin deploying through environments."

---

## Phase 6: Deploy to Test (Canary → Ring Rollout)

**Role: Automated (Platform)**

Tell the user:
> "The Standard Pipeline is now deploying to the **Test** environment. For multi-tenant products, deployment uses **canary/ring-based rollout**:
>
> 1. **Canary phase:** The canary tenant (`acme-corp`) receives the new version first
> 2. **Health check:** Platform verifies health endpoints, error rates, and latency for the canary tenant
> 3. **Ring rollout:** Once canary passes, remaining tenants (`enterprise-client`) receive the new version
>
> This ensures that issues are caught with a smaller-blast-radius tenant before rolling out to enterprise customers."

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

Tell user: "Standard Pipeline complete! All jobs passed. Both tenants in the Test environment have the new version. Dashboard 'Test' column should show success."

---

## Phase 7: Deploy to Perftest

**Role: Automated (Platform)**

Tell the user:
> "The Perftest Pipeline auto-triggered after Test passed. Running: K6 Baseline Load → Stress Test → Spike Test → Long-Duration → Resource Profiling → Network Simulation → E2E Under Load → New Relic Report.
>
> Performance tests run against **all tenants** in the perftest environment. This validates that both bronze-tier (shared DB) and gold-tier (dedicated DB) infrastructure handles load correctly."

Wait for Perf Pipeline:
```bash
sleep 10
RUN_ID=$(gh run list --repo {repo} --workflow "perf-pipeline.yaml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Tell user: "Perf Pipeline complete! All K6 performance tests passed across all tenants. Dashboard 'Perftest' column should show success."

---

## Phase 8: Deploy to Staging

**Role: Automated (Platform) + Manual UAT Gate**

Tell the user:
> "The Staging Pipeline auto-triggered after Perftest passed. Running: Deploy to Staging → Integration Tests → E2E Business Validation → UAT → Security & Compliance (Veracode) → Observability Validation.
>
> Staging uses the same **canary → ring rollout** as Test — `acme-corp` gets the new version first, then `enterprise-client` after health checks pass."

Wait for Staging Pipeline:
```bash
sleep 10
RUN_ID=$(gh run list --repo {repo} --workflow "staging-pipeline.yaml" --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch $RUN_ID --repo {repo} --exit-status
```

Tell user: "Staging Pipeline complete! Dashboard 'Staging' column should show success. The full pipeline — from PR to Staging — is now green."

---

## Phase 9: Release & Documentation

**Role: Product Team decides → Platform automation executes**

Tell the user:
> "You're the **Product Team** — you decide when to release. Tagging a version triggers the platform automation: AI-generated release notes → GitHub Release → JIRA version → Confluence release page."

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
gh run view $RUN_ID --repo {repo} --log | grep -E "(Created JIRA|Confluence page|URL:)"
```

Tell user: "Release complete! 4 artifacts created automatically: GitHub Release with AI notes, JIRA version, Confluence release page."

---

## Phase 10: Summary & Impact

Tell the user:

> ## Demo Complete!
>
> Here's what just happened — the full lifecycle of a change:
>
> | Phase | Who | What |
> |-------|-----|------|
> | Onboard | Platform Team | 6-phase lifecycle: migrate → scan → register → scaffold → infra → readiness |
> | **Provision Tenants** | **Product Team** | **Created tenant registry with bronze (acme-corp) + gold (enterprise-client) tenants in their repo** |
> | Develop | Product Team | Feature branch + PR created |
> | AI Review | Automated (GitHub Copilot) | Security issues found + commented |
> | Merge | Product Team | PR merged to main |
> | Test → Staging | Automated (Platform pipelines) | Canary/ring deployment through all environments — canary tenant first, then ring rollout |
> | Release | Product Team decides → Platform automation executes | AI notes + GitHub + JIRA + Confluence |
>
> **Key takeaways:**
> - **No product tiers** — all products get the same CI/CD pipeline rigor (4 environments, full scanning, load testing)
> - **Tenant tiers** control infrastructure sizing only (bronze = shared DB, gold = dedicated multi-AZ + CMK)
> - **Canary/ring deployment** ensures safe rollout across tenants
> - **Total: PR to Staging in under 5 minutes. Fully automated. Zero manual steps except the initial PR.**

Read `config/products.json` and list all registered products dynamically (no tier labels):

> This runs the same way for all Ideagen products:
> {list each product by name from products.json}
>
> The dashboard shows the real-time status of every product across every environment.

Ask: **"Would you like to demo another product, or are we done?"**
- Demo another product (restart from Phase 0)
- Done — wrap up
