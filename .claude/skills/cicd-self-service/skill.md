---
name: cicd-self-service
description: "Developer self-service portal. Provision tenants and add new services via natural language. Creates PRs with self-service label for automated AI validation."
user_invocable: true
arguments: "<request> — Natural language request like 'Provision tenant acme for demo-product' or 'Add a notification Lambda'"
---

# CICD Self-Service — Developer Self-Service Portal

This is a **rigid** skill. Follow every step exactly.

## Scope (STRICT)

Self-service allows ONLY two operations:

| Allowed | Description |
|---------|-------------|
| **Provision tenant** | Add a new tenant to an existing product |
| **Add new service** | Register a new microservice/component and scaffold its pipeline |

**NOT allowed (platform team only):** tier changes, environment changes, deploy target changes, infrastructure modifications, security policy overrides, account/region changes.

## Step 1: Parse Request

Read the user's request and classify as one of:
- `provision-tenant` — mentions: tenant, provision, new tenant, add tenant
- `add-service` — mentions: new service, add service, new lambda, new API, new worker, new frontend
- `query` — mentions: what can I, help, boundaries, allowed

If unclear, ask using AskUserQuestion:

**"What would you like to do?"**
- **Provision a tenant** — Add a new tenant to an existing product
- **Add a new service** — Register and scaffold a new microservice
- **What can I do?** — See self-service boundaries

## Step 2: Identify Product

If the request mentions a product name, read `config/products.json` and validate it exists.
If not mentioned, ask using AskUserQuestion with options from the products registry.

## Step 3: Route

### Route A: Provision Tenant

1. **Ask tenant name** using AskUserQuestion (free text)
   - Validate: `^[a-z][a-z0-9-]{2,40}$` (lowercase, starts with letter, 3-41 chars, hyphens allowed)
   - If invalid, explain the format and ask again

2. **Ask tier** using AskUserQuestion:
   - **Bronze** — Development/small customers. Shared DB, minimal compute.
   - **Silver** — Production customers. Dedicated RDS (t4g.medium).
   - **Gold** — Enterprise/regulated. Dedicated RDS (r6g.large, multi-AZ), CMK encryption.

3. **Ask region** using AskUserQuestion:
   - us-east-1 (Recommended)
   - eu-west-1
   - ap-southeast-1

4. **Gold compliance** (gold tier only) — Ask using AskUserQuestion (multi-select):
   - Data residency (restrict to specific region group: eu, us, ap)
   - CMK encryption (customer-managed KMS key)
   - Extended backup retention (specify days, default 30)

5. **Generate** `tenants/registry.yaml` — If the file exists, read it and append. If not, create:

```yaml
apiVersion: v1
kind: TenantRegistry
product: {PRODUCT_NAME}

tenants:
  - name: {TENANT_NAME}
    tier: {TIER}
    region: {REGION}
    status: active
    created_at: "{TODAY_DATE}"
```

Add `compliance` block only for gold tier with compliance options selected.

6. **Generate** `.github/workflows/tenant.yaml` if it doesn't exist:

```yaml
name: Tenant Provisioning
on:
  pull_request:
    paths: ["tenants/**"]
  push:
    branches: [main]
    paths: ["tenants/**"]

jobs:
  provision:
    uses: shermanlye-ideagen/demo-cicd-platform/.github/workflows/_provision-tenant.yaml@main
    with:
      product_name: "{PRODUCT_NAME}"
      environment: ${{ github.event_name == 'push' && 'prod' || 'dev' }}
    secrets: inherit
```

7. **Create PR** with `self-service` label:
   - Branch: `self-service/tenant-{TENANT_NAME}`
   - Title: `feat: provision tenant {TENANT_NAME} ({TIER} tier)`
   - Body: Summary of tenant config + link to platform standards

8. **Summary** — Output a table with tenant details and next steps.

### Route B: Add New Service

1. **Ask service name** using AskUserQuestion (free text)
   - Validate: `^[a-z][a-z0-9-]{2,40}$`

2. **Ask service type** using AskUserQuestion:
   - **API** — REST/GraphQL backend service
   - **Worker** — Background processing service
   - **Frontend** — Web application (SPA)
   - **Function** — Serverless (Lambda)

3. **Ask tech stack** using AskUserQuestion:
   - Python (FastAPI/Flask)
   - Node.js (Express/NestJS)
   - .NET (ASP.NET Core)
   - Java (Spring Boot)
   - Go

4. **Register** — Create `products/{SERVICE_NAME}/product.json`:

```json
{
  "$schema": "../../config/schema/product-schema.json",
  "name": "{SERVICE_NAME}",
  "displayName": "{DISPLAY_NAME}",
  "team": "{PARENT_PRODUCT_TEAM}",
  "tier": "{PARENT_PRODUCT_TIER}",
  "repo": "shermanlye-ideagen/{SERVICE_NAME}",
  "tenancy": "single",
  "detectedStack": "{DETECTED_STACK}"
}
```

5. **Update** `config/products.json` — Add new entry to the products array.

6. **Scaffold** — Create `.platform/` directory for the new service using templates from `config/templates/`.

7. **Create PR** with `self-service` label:
   - Branch: `self-service/add-{SERVICE_NAME}`
   - Title: `feat: register new service {SERVICE_NAME}`
   - Body: What was registered, inherited tier/governance rules, platform standards enforced

8. **Summary** — Output created files and next steps.

### Route C: Query ("What can I do?")

Read `config/conventions/self-service-boundaries.yaml` and present:

```
## Self-Service Boundaries

As a product team, you can:

### ✅ Allowed
1. **Provision tenants** — Add new tenants with tier-appropriate infrastructure
   - Choose tier (bronze/silver/gold), region, and compliance requirements
   - Crossplane auto-provisions: namespace, RDS, S3, IAM, KMS, monitoring

2. **Add new services** — Register new microservices and scaffold pipelines
   - Inherits parent product's tier and governance rules
   - Auto-scaffolds: .platform/ config, CI/CD pipeline, security scanning

### ❌ Platform Team Only
- Security policies (SAST, SBOM, FedRAMP)
- Account/environment mappings
- Approval gates
- Tier assignments
- Deploy targets
- Infrastructure modifications

For platform changes, raise a JIRA ticket under the IDEVOPS project.
```

### Denied Requests

If the user requests something outside self-service scope:

1. Identify what they're asking for
2. Explain: "**{Requested change}** is managed by the platform team."
3. Read and quote the relevant section from `config/conventions/self-service-boundaries.yaml` under `protected`
4. Suggest: "Please raise a JIRA ticket under the IDEVOPS project, or contact the platform team at #platform-support."
