#!/usr/bin/env python
"""Standardized Pipeline Platform — Config Resolver.

Resolves a product's full configuration by composing:
  Convention (stack detection + pipeline defaults) →
  Policy (org rules that generate config) →
  Accounts (AWS environment mapping) →
  Provenance (trace every field to its origin)

No traits, no exceptions, no product-level overrides.
Platform decides everything based on detection + policies.

Usage:
    python scripts/resolve-config.py my-app
    python scripts/resolve-config.py --all
    python scripts/resolve-config.py my-app --explain pipeline.sonarqube
    python scripts/resolve-config.py my-app --output .resolved/my-app.json
    python scripts/resolve-config.py --all --output .resolved/ --validate
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def set_nested(d: dict, dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using a dotted key path."""
    keys = dotted_key.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def get_nested(d: dict, dotted_key: str, default: Any = None) -> Any:
    """Get a value from a nested dict using a dotted key path."""
    keys = dotted_key.split(".")
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
        if d is default:
            return default
    return d


def _load_detect_stack_module():
    """Dynamically import the detect-stack.py module."""
    spec = importlib.util.spec_from_file_location(
        "detect_stack",
        PROJECT_ROOT / "scripts" / "detect-stack.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Step 1 & 2: Convention Engine
# ---------------------------------------------------------------------------

def resolve_stack(product: dict, repo_path: Path | None = None) -> tuple[str, str | None, str | None, str, str, dict]:
    """Determine tech stack via detectedStack field or convention detection.

    Returns (stack, variant, version, os, build_tool, provenance_entry).
    """
    variant = None
    version = None
    os_name = "linux"

    # Use platform-set detectedStack field (set during onboarding)
    if "detectedStack" in product:
        stack = product["detectedStack"]
        routing = load_yaml(PROJECT_ROOT / "config" / "conventions" / "deploy-routing.yaml")
        route = routing.get("routing", {}).get(stack, {})
        build_tool = route.get("build_tool", "unknown") if route else "unknown"
        if build_tool == "unknown":
            build_tool = {"nodejs": "npm", "python": "pip", "dotnet": "dotnet",
                          "java": "maven", "php": "composer",
                          "legacy-vm": "custom"}.get(stack, "unknown")
        os_name = route.get("os", "linux") if route else "linux"

        return stack, variant, version, os_name, build_tool, {
            "source": "product:detectedStack",
            "reason": "Set by platform during onboarding via detect-stack.py"
        }

    # Auto-detect from repo path
    if repo_path and repo_path.is_dir():
        detect_mod = _load_detect_stack_module()
        detection = detect_mod.detect_stack(repo_path)
        stack = detection["stack"]
        variant = detection.get("variant")
        version = detection.get("version")
        os_name = detection.get("os", "linux")
        build_tool = detection["build_tool"]
        return stack, variant, version, os_name, build_tool, {
            "source": "convention:stack-detection",
            "reason": f"Auto-detected from repo markers: {', '.join(detection.get('matched_markers', []))}"
        }

    # Fallback
    return "legacy-vm", variant, version, os_name, "custom", {
        "source": "convention:fallback",
        "reason": "No detectedStack and no repo path for auto-detection"
    }


def resolve_pipeline_defaults() -> dict:
    """Load pipeline defaults from conventions.

    All products get the same pipeline config — no tier differentiation.
    """
    return load_yaml(PROJECT_ROOT / "config" / "conventions" / "pipeline-defaults.yaml")


def resolve_deploy_routing(stack: str, variant: str | None) -> dict:
    """Determine deploy target and runtime info from stack + variant.

    Uses hierarchical lookup: stack defaults → variant overrides.
    """
    routing = load_yaml(PROJECT_ROOT / "config" / "conventions" / "deploy-routing.yaml")
    route = routing.get("routing", {}).get(stack, {})
    if not route:
        return {}

    # Start with stack-level defaults (exclude 'variants' key)
    result = {k: v for k, v in route.items() if k != "variants"}

    # Merge variant-specific overrides
    if variant:
        variant_overrides = route.get("variants", {}).get(variant, {})
        result.update(variant_overrides)

    # All products use the same deploy target (standardized)
    result["deploy_target"] = result.get("default_deploy_target", "eks")

    return result


# ---------------------------------------------------------------------------
# Step 3: Policy Engine
# ---------------------------------------------------------------------------

def load_all_policies() -> list[dict]:
    """Load all policy YAML files from config/policies/."""
    policies_dir = PROJECT_ROOT / "config" / "policies"
    policies = []
    for yaml_file in sorted(policies_dir.rglob("*.yaml")):
        policies.append(load_yaml(yaml_file))
    return policies


def policy_applies(policy: dict, product_meta: dict) -> bool:
    """Check if a policy's applies_when conditions match the product."""
    conditions = policy.get("applies_when", {})

    for key, expected in conditions.items():
        if key == "_custom":
            continue  # Custom conditions handled separately

        actual = product_meta.get(key)
        if actual is None:
            return False

        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False

    return True


def evaluate_policies(product_meta: dict) -> tuple[dict, dict]:
    """Evaluate all policies against product metadata.

    No exceptions — all policies are non-negotiable.
    Returns (generated_config, provenance_entries).
    """
    policies = load_all_policies()
    generated = {}
    provenance = {}

    for policy in policies:
        name = policy.get("name", "unknown")

        if not policy_applies(policy, product_meta):
            continue

        # Apply policy generates — no exception checks
        generates = policy.get("generates", {})
        for key, value in _flatten_generates(generates):
            if not key.startswith("_"):  # Skip internal directives
                set_nested(generated, key, value)
                provenance[key] = {
                    "source": f"policy:{name}",
                    "reason": f"{policy.get('description', '')} ({_conditions_str(policy, product_meta)})"
                }

    return generated, provenance


def _conditions_str(policy: dict, meta: dict) -> str:
    """Build a human-readable string of matched conditions."""
    parts = []
    for key in policy.get("applies_when", {}):
        if key == "_custom":
            continue
        if key in meta:
            parts.append(f"{key}={meta[key]}")
    return ", ".join(parts) if parts else "always"


def _flatten_generates(generates: dict, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested generates dict into dotted-key pairs.

    Skips keys starting with _ (internal directives like _environments).
    """
    items = []
    for key, value in generates.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and not key.startswith("_"):
            items.extend(_flatten_generates(value, full_key))
        else:
            items.append((full_key, value))
    return items


# ---------------------------------------------------------------------------
# Step 4: Account Mapping + Environment Resolution
# ---------------------------------------------------------------------------

def resolve_environments(
    pipeline_defaults: dict,
    accounts: dict,
    trait_envs: dict,
    approval_rules: dict,
    deploy_target: str,
    cloud: str = "aws",
) -> tuple[dict, dict]:
    """Build full environment config from conventions + accounts + traits.

    Supports both AWS (aws_account_id) and Azure (subscription_id + resource_group).

    Returns (environments_dict, provenance_entries).
    """
    env_names = pipeline_defaults.get("environments", [])
    environments = {}
    provenance = {}

    if cloud == "azure":
        azure_config = load_yaml(PROJECT_ROOT / "config" / "accounts" / "azure-subscriptions.yaml")
        azure_subs = azure_config.get("subscriptions", {})

        for env_name in env_names:
            sub = azure_subs.get(env_name, {})
            approval = "none"
            if approval_rules and env_name in approval_rules:
                approval = approval_rules[env_name].get("approval", "none")

            environments[env_name] = {
                "subscription_id": sub.get("subscription_id", "UNKNOWN"),
                "resource_group": f"{sub.get('resource_group_prefix', 'rg-ideagen')}-{env_name}",
                "region": sub.get("region", "australiaeast"),
                "deploy_target": deploy_target,
                "approval": approval,
            }
            provenance[f"environments.{env_name}"] = {
                "source": "convention:pipeline-defaults + accounts:azure-subscriptions",
                "reason": "Standard environment from pipeline defaults (Azure)"
            }
    else:
        # AWS (default)
        accounts_config = load_yaml(PROJECT_ROOT / "config" / "accounts" / "aws-accounts.yaml")
        env_accounts = accounts_config.get("environments", {})

        for env_name in env_names:
            account = env_accounts.get(env_name, {})
            approval = "none"
            if approval_rules and env_name in approval_rules:
                approval = approval_rules[env_name].get("approval", "none")

            environments[env_name] = {
                "aws_account_id": account.get("aws_account_id", "UNKNOWN"),
                "region": account.get("region", "us-east-1"),
                "deploy_target": deploy_target,
                "approval": approval,
            }
            provenance[f"environments.{env_name}"] = {
                "source": "convention:pipeline-defaults + accounts:aws-accounts",
                "reason": "Standard environment from pipeline defaults"
            }

    # Add trait-generated environments
    for env_name, env_config in trait_envs.items():
        if cloud == "azure":
            azure_subs = load_yaml(PROJECT_ROOT / "config" / "accounts" / "azure-subscriptions.yaml").get("subscriptions", {})
            sub = azure_subs.get(env_name, {})
            environments[env_name] = {
                "subscription_id": sub.get("subscription_id", "UNKNOWN"),
                "resource_group": f"{sub.get('resource_group_prefix', 'rg-ideagen')}-{env_name}",
                "region": env_config.get("region", sub.get("region", "australiaeast")),
                "deploy_target": deploy_target,
                "approval": env_config.get("approval", "none"),
            }
        else:
            accounts_config = load_yaml(PROJECT_ROOT / "config" / "accounts" / "aws-accounts.yaml")
            env_accounts = accounts_config.get("environments", {})
            account = env_accounts.get(env_name, {})
            region = env_config.get("region", "us-east-1")
            environments[env_name] = {
                "aws_account_id": account.get("aws_account_id", "UNKNOWN"),
                "region": region if isinstance(region, str) else account.get("region", region),
                "deploy_target": deploy_target,
                "approval": env_config.get("approval", "none"),
            }
        provenance[f"environments.{env_name}"] = {
            "source": "trait:demo-environments",
            "reason": "Added by demo-environments trait"
        }

    return environments, provenance


def build_pipeline_order(env_names: list[str], trait_inserts: dict | None = None) -> list:
    """Build pipeline order from environment names with trait insertions."""
    # Default order follows the pipeline-defaults environment list
    order = list(env_names)

    if trait_inserts:
        after = trait_inserts.get("after")
        new_envs = trait_inserts.get("envs", [])
        if after and after in order:
            idx = order.index(after) + 1
            # Insert as parallel group
            order.insert(idx, new_envs)
        else:
            order.extend(new_envs)

    return order


# ---------------------------------------------------------------------------
# Main Resolution Pipeline
# ---------------------------------------------------------------------------

def _resolve_single_product(product_path: Path, product: dict) -> dict:
    """Run the full resolution pipeline for a product.

    Pipeline: Convention → Policy → Accounts → Provenance
    No traits, no exceptions, no product-level overrides.
    """
    name = product["name"]
    team = product["team"]
    provenance: dict[str, dict] = {}

    # --- Step 1: Convention — Resolve Stack ---
    stack, variant, version, os_name, build_tool, stack_prov = resolve_stack(product)
    provenance["stack"] = stack_prov
    if variant:
        provenance["variant"] = {
            "source": stack_prov["source"],
            "reason": f"Variant '{variant}' from stack detection"
        }

    # --- Step 2: Convention — Pipeline Defaults + Deploy Routing ---
    pipeline_defaults = resolve_pipeline_defaults()
    routing = resolve_deploy_routing(stack, variant)
    deploy_target = routing.get("deploy_target", "eks")
    cloud = routing.get("cloud", "aws")
    os_resolved = routing.get("os", os_name)

    provenance["deployTarget"] = {
        "source": "convention:deploy-routing",
        "reason": f"stack={stack}, variant={variant}"
    }

    # Build pipeline config from pipeline defaults (uniform for all products)
    pipeline = copy.deepcopy(pipeline_defaults.get("pipeline", {}))
    for key in pipeline:
        prov_key = f"pipeline.{key}"
        if prov_key not in provenance:
            provenance[prov_key] = {
                "source": "convention:pipeline-defaults",
                "reason": "Uniform pipeline default for all products"
            }

    # --- Step 3: Policy Evaluation (no exceptions) ---
    product_meta = {
        "stack": stack,
        "variant": variant,
        "deploy_target": deploy_target,
        "cloud": cloud,
        "os": os_resolved,
    }
    policy_config, policy_prov = evaluate_policies(product_meta)

    # Merge policy config into pipeline
    policy_pipeline = policy_config.pop("pipeline", {}) if "pipeline" in policy_config else {}
    for key, value in policy_pipeline.items():
        if isinstance(value, dict) and isinstance(pipeline.get(key), dict):
            pipeline[key].update(value)
        else:
            pipeline[key] = value
    provenance.update(policy_prov)

    # --- Step 4: Account Mapping + Environment Resolution ---
    approval_rules = {}
    for policy in load_all_policies():
        generates = policy.get("generates", {})
        if "_approval_rules" in generates:
            approval_rules.update(generates["_approval_rules"])

    environments, env_prov = resolve_environments(
        pipeline_defaults, {}, {}, approval_rules, deploy_target, cloud
    )
    provenance.update(env_prov)

    # --- Step 5: Build Pipeline Order ---
    pipeline_order = build_pipeline_order(
        pipeline_defaults.get("environments", []),
        None
    )

    # --- Step 6: Materialize Final Config ---
    resolved = {
        "product": {
            "name": name,
            "displayName": product.get("displayName", name),
            "team": team,
            "tenancy": product.get("tenancy", "single"),
        },
        "stack": stack,
        "variant": variant,
        "os": os_resolved,
        "cloud": cloud,
        "buildTool": build_tool,
        "deployTarget": deploy_target,
        "containerized": routing.get("containerized", True),
        "dockerRegistryPrefix": routing.get("docker_registry_prefix"),
        "environments": environments,
        "pipeline": pipeline,
        "runtimeVersions": routing.get("runtime_versions", {}),
        "pipelineOrder": pipeline_order,
        "provenance": provenance,
    }

    # Merge remaining policy config (sonarqube, newrelic, veracode, etc.)
    for key, value in policy_config.items():
        if not key.startswith("_"):
            resolved[key] = value

    # Add pipeline.requires_cab from pipeline defaults
    resolved["pipeline"]["requires_cab"] = pipeline_defaults.get("requires_cab", True)
    provenance["pipeline.requires_cab"] = {
        "source": "convention:pipeline-defaults",
        "reason": "Uniform pipeline default for all products"
    }

    return resolved


def resolve_product(product_path: Path) -> dict:
    """Run the full resolution pipeline for a product."""
    product = load_json(product_path)
    return _resolve_single_product(product_path, product)


def find_all_products() -> list[Path]:
    """Find all product.json files in the products/ directory."""
    products_dir = PROJECT_ROOT / "products"
    return sorted(products_dir.glob("*/product.json"))


def explain_field(resolved: dict, field_path: str) -> str:
    """Explain where a resolved config field came from."""
    value = get_nested(resolved, field_path)
    prov = resolved.get("provenance", {}).get(field_path)

    lines = [f"Field:  {field_path}"]
    lines.append(f"Value:  {json.dumps(value) if value is not None else 'not set'}")
    if prov:
        lines.append(f"Source: {prov['source']}")
        lines.append(f"Reason: {prov['reason']}")
    else:
        lines.append("Source: (no provenance — check parent path)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve product config: Convention + Policy → final config (standardized)"
    )
    parser.add_argument(
        "product",
        nargs="?",
        help="Product name to resolve (e.g. my-app)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Resolve all products",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path (file for single product, directory for --all)",
    )
    parser.add_argument(
        "--explain",
        type=str,
        help="Explain provenance of a specific field (dotted path)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate resolved config against schema",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation)",
    )
    args = parser.parse_args()

    if not args.product and not args.all:
        parser.error("Specify a product name or --all")

    indent = None if args.compact else 2

    if args.all:
        products = find_all_products()
        if not products:
            print("No products found in products/*/product.json", file=sys.stderr)
            sys.exit(1)

        results = {}
        errors = []
        for product_path in products:
            name = product_path.parent.name
            try:
                results[name] = resolve_product(product_path)
                print(f"  OK  {name}")
            except Exception as e:
                errors.append(f"{name}: {e}")
                print(f"  FAIL  {name}: {e}", file=sys.stderr)

        if args.output:
            output_dir = args.output
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, resolved in results.items():
                out_path = output_dir / f"{name}.json"
                with open(out_path, "w") as f:
                    json.dump(resolved, f, indent=indent)
            print(f"\nResolved {len(results)} products to {output_dir}/")

        if errors:
            print(f"\n{len(errors)} error(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)
    else:
        product_path = PROJECT_ROOT / "products" / args.product / "product.json"
        if not product_path.exists():
            print(f"Error: Product '{args.product}' not found at {product_path}", file=sys.stderr)
            sys.exit(1)

        try:
            resolved = resolve_product(product_path)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if args.explain:
            print(explain_field(resolved, args.explain))
            return

        output = json.dumps(resolved, indent=indent)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Resolved config written to {args.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
