#!/usr/bin/env python
"""Validate all products and policies in the Standardized Pipeline Platform.

Checks:
  1. All product.json files validate against product-schema.json
  2. All policy YAML files have required fields
  3. All products resolve successfully (full pipeline)
  4. products.json registry is in sync with product directories

Usage:
    python scripts/validate-all.py
    python scripts/validate-all.py --verbose
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import yaml

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def validate_products_against_schema(verbose: bool = False) -> list[str]:
    """Validate all product.json files against the product schema."""
    errors = []
    schema_path = PROJECT_ROOT / "config" / "schema" / "product-schema.json"

    if not schema_path.exists():
        return ["product-schema.json not found"]

    schema = load_json(schema_path)
    products_dir = PROJECT_ROOT / "products"

    for product_json in sorted(products_dir.glob("*/product.json")):
        name = product_json.parent.name
        try:
            product = load_json(product_json)
            if HAS_JSONSCHEMA:
                jsonschema.validate(product, schema)
            if verbose:
                print(f"  OK  {name} (schema)")
        except jsonschema.ValidationError as e:
            errors.append(f"{name}: Schema validation failed — {e.message}")
        except Exception as e:
            errors.append(f"{name}: {e}")

    return errors


def validate_policies(verbose: bool = False) -> list[str]:
    """Validate all policy YAML files have required fields."""
    errors = []
    policies_dir = PROJECT_ROOT / "config" / "policies"

    required_fields = {"name", "description", "severity", "applies_when", "generates"}

    for yaml_file in sorted(policies_dir.rglob("*.yaml")):
        rel = yaml_file.relative_to(PROJECT_ROOT)
        try:
            policy = load_yaml(yaml_file)
            missing = required_fields - set(policy.keys())
            if missing:
                errors.append(f"{rel}: Missing required fields: {missing}")
            elif verbose:
                print(f"  OK  {rel}")

            # Validate severity enum
            if policy.get("severity") not in ("error", "warning", "info"):
                errors.append(f"{rel}: Invalid severity '{policy.get('severity')}'")

        except Exception as e:
            errors.append(f"{rel}: {e}")

    return errors


def validate_resolution(verbose: bool = False) -> list[str]:
    """Attempt to resolve all products and check for errors."""
    errors = []

    spec = importlib.util.spec_from_file_location(
        "resolve_config",
        PROJECT_ROOT / "scripts" / "resolve-config.py"
    )
    resolve_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resolve_mod)

    for product_path in sorted((PROJECT_ROOT / "products").glob("*/product.json")):
        name = product_path.parent.name
        try:
            resolve_mod.resolve_product(product_path)
            if verbose:
                print(f"  OK  {name} (resolution)")
        except Exception as e:
            errors.append(f"{name}: Resolution failed — {e}")

    return errors


def validate_registry_sync(verbose: bool = False) -> list[str]:
    """Check that products.json is in sync with product directories."""
    errors = []
    registry_path = PROJECT_ROOT / "config" / "products.json"

    if not registry_path.exists():
        return ["config/products.json not found"]

    registry = load_json(registry_path)
    registered_names = {p["name"] for p in registry.get("products", [])}
    dir_names = {p.parent.name for p in (PROJECT_ROOT / "products").glob("*/product.json")}

    missing_from_registry = dir_names - registered_names
    missing_from_dirs = registered_names - dir_names

    for name in missing_from_registry:
        errors.append(f"products/{name}/ exists but not in products.json")
    for name in missing_from_dirs:
        errors.append(f"'{name}' in products.json but no products/{name}/product.json")

    if verbose and not errors:
        print(f"  OK  Registry sync ({len(registered_names)} products)")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate all platform config (standardized)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    all_errors = []

    checks = [
        ("Product schemas", validate_products_against_schema),
        ("Policy definitions", validate_policies),
        ("Config resolution", validate_resolution),
        ("Registry sync", validate_registry_sync),
    ]

    for label, check_fn in checks:
        print(f"\n--- {label} ---")
        errors = check_fn(verbose=args.verbose)
        all_errors.extend(errors)
        if errors:
            for err in errors:
                print(f"  FAIL  {err}", file=sys.stderr)
        elif not args.verbose:
            print(f"  OK")

    print(f"\n{'='*50}")
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s)")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
