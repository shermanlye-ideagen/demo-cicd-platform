---
title: "Reusable Workflow Pattern for Demo"
author: Sherman Lye
date: 2026-03-17
status: approved
audience: platform-team
last_updated: 2026-03-17
---

# Reusable Workflow Pattern for Demo

## Problem

Product repo workflows contain all pipeline jobs inline (~150 lines each). This doesn't represent the real architecture where product repos have thin callers (~10 lines) and all logic lives in the platform repo's reusable workflows.

## Design

### demo-cicd-platform (new workflows)

Create reusable workflows with `workflow_call` triggers and simulated (echo-only) jobs:

- `.github/workflows/standard-pipeline.yaml` — 10 jobs: build, test, sast, sbom, e2e, contract, security-verify, container-push, deploy-test, nr-baseline
- `.github/workflows/perf-pipeline.yaml` — triggered by `workflow_run` on Standard Pipeline success. 10 jobs: deploy-perf, nr-baseline, load-test, stress-test, spike-test, duration-test, resource-profile, network-sim, e2e-under-load, nr-report
- `.github/workflows/staging-pipeline.yaml` — triggered by `workflow_run` on Perf Pipeline success. 6 jobs: deploy-staging, integration-tests, e2e-business, uat, security-compliance, observability
- `.github/workflows/release.yaml` — reusable workflow for releases

### Product repos (devonway, iqmc, lucidity, demo-product)

Replace all inline workflow files with a single `ci.yaml`:

```yaml
name: CI/CD Pipeline
on:
  workflow_dispatch:
  pull_request:
    branches: [main]
  push:
    branches: [main]
    tags: ["v*"]
jobs:
  pipeline:
    uses: shermanlye-ideagen/demo-cicd-platform/.github/workflows/standard-pipeline.yaml@main
    with:
      product_name: "{product}"
    secrets: inherit
```

### Chain trigger

Perf and staging pipelines in demo-cicd-platform use `workflow_run` to auto-trigger after the previous stage completes. Since `workflow_run` only triggers for workflows in the **same repo**, and the standard pipeline runs in the **product repo** (via `uses:`), the perf/staging chain triggers need to be in the product repos too.

**Revised approach:** Keep 3 thin callers per product repo:
- `ci.yaml` — calls standard-pipeline reusable workflow
- `perf.yaml` — `workflow_run` on ci.yaml success, calls perf-pipeline reusable workflow
- `staging.yaml` — `workflow_run` on perf.yaml success, calls staging-pipeline reusable workflow

Each is ~15 lines. All job logic remains in demo-cicd-platform.

## Files

| Repo | File | Action |
|------|------|--------|
| demo-cicd-platform | `.github/workflows/standard-pipeline.yaml` | Create |
| demo-cicd-platform | `.github/workflows/perf-pipeline.yaml` | Create |
| demo-cicd-platform | `.github/workflows/staging-pipeline.yaml` | Create |
| demo-cicd-platform | `.github/workflows/release.yaml` | Create |
| devonway | `.github/workflows/ci.yaml` | Create |
| devonway | `.github/workflows/perf.yaml` | Create |
| devonway | `.github/workflows/staging.yaml` | Create |
| devonway | `.github/workflows/standard-pipeline.yaml` | Delete |
| devonway | `.github/workflows/perf-pipeline.yaml` | Delete |
| devonway | `.github/workflows/staging-pipeline.yaml` | Delete |
| iqmc, lucidity, demo-product | Same as devonway | Same |
