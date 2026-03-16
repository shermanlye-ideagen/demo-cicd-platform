#!/usr/bin/env python
"""Auto-detect tech stack from repository file markers with sub-variant detection.

Two-pass detection:
  Pass 1: File marker scan → identifies top-level stack
  Pass 2: Content inspection → determines variant, version, OS

Uses convention rules defined in config/conventions/stack-detection.yaml.

Usage:
    python scripts/detect-stack.py /path/to/repo
    python scripts/detect-stack.py /path/to/repo --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


def load_detection_rules(rules_path: Path) -> dict:
    """Load stack detection rules from YAML config."""
    with open(rules_path) as f:
        return yaml.safe_load(f)


def _extract_xml_element(repo_path: Path, glob_pattern: str, element_name: str) -> str | None:
    """Extract text content of an XML element from the first matching file.

    Searches for element_name anywhere in the XML tree (recursive find).
    Returns None if file not found or element missing.
    """
    matches = sorted(repo_path.glob(glob_pattern))
    if not matches:
        return None

    try:
        tree = ET.parse(matches[0])
        root = tree.getroot()
        # Handle XML namespaces — strip namespace for element search
        ns = ""
        ns_match = re.match(r"\{(.+?)\}", root.tag)
        if ns_match:
            ns = ns_match.group(0)

        # Try with namespace first, then without
        elem = root.find(f".//{ns}{element_name}")
        if elem is None:
            elem = root.find(f".//{element_name}")
        if elem is not None and elem.text:
            return elem.text.strip()
    except (ET.ParseError, OSError):
        pass
    return None


def _extract_json_value(repo_path: Path, filename: str, dotted_path: str) -> str | None:
    """Extract a value from a JSON file at a dotted path.

    Returns the string representation, or None if not found.
    """
    filepath = repo_path / filename
    if not filepath.exists():
        return None

    try:
        with open(filepath) as f:
            data = json.load(f)
        for key in dotted_path.split("."):
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
            if data is None:
                return None
        return str(data) if data is not None else None
    except (json.JSONDecodeError, OSError):
        return None


def _parse_version_constraint(constraint: str) -> tuple[str, float]:
    """Parse a version constraint like '>=8.0' or '<7.0'.

    Returns (operator, version_number).
    """
    constraint = constraint.strip()
    if constraint.startswith(">="):
        return ">=", float(constraint[2:])
    elif constraint.startswith("<="):
        return "<=", float(constraint[2:])
    elif constraint.startswith(">"):
        return ">", float(constraint[1:])
    elif constraint.startswith("<"):
        return "<", float(constraint[1:])
    elif constraint.startswith("=="):
        return "==", float(constraint[2:])
    else:
        return "==", float(constraint)


def _extract_version_number(version_str: str) -> float | None:
    """Extract a numeric version from a constraint string like '>=5.5', '^8.0', '~7.4'.

    Strips common prefixes (>=, ^, ~, v) and returns major.minor as a float.
    """
    cleaned = re.sub(r'^[>=<^~v!|\s]+', '', version_str.strip())
    match = re.match(r'(\d+)(?:\.(\d+))?', cleaned)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        return major + minor / 10.0 if minor < 10 else major + minor / 100.0
    return None


def _match_version_range(version_str: str, ranges: dict) -> dict | None:
    """Match a version string against a set of version range constraints.

    Each key in `ranges` is a comma-separated set of constraints like '>=7.0,<8.0'.
    Returns the mapped value dict for the first matching range, or None.
    """
    version = _extract_version_number(version_str)
    if version is None:
        return None

    for range_key, result in ranges.items():
        constraints = [c.strip() for c in range_key.split(",")]
        all_match = True
        for constraint in constraints:
            op, threshold = _parse_version_constraint(constraint)
            if op == ">=" and not (version >= threshold):
                all_match = False
            elif op == ">" and not (version > threshold):
                all_match = False
            elif op == "<=" and not (version <= threshold):
                all_match = False
            elif op == "<" and not (version < threshold):
                all_match = False
            elif op == "==" and not (version == threshold):
                all_match = False
        if all_match:
            return result
    return None


def inspect_content(repo_path: Path, rule: dict) -> dict:
    """Run Pass 2 content inspection on a matched rule.

    Iterates the rule's `inspect` list and runs the appropriate extraction.
    Later inspections override earlier ones (last-write-wins).

    Returns dict with keys: variant, version, os, inspections (audit trail).
    """
    result = {}
    inspections = []

    for spec in rule.get("inspect", []):
        inspection_type = spec["type"]
        file_pattern = spec["file"]

        if inspection_type == "xml_element":
            value = _extract_xml_element(repo_path, file_pattern, spec["element"])
            if value is not None:
                inspections.append({
                    "file": file_pattern,
                    "field": spec["element"],
                    "value": value,
                })
                mapped = spec.get("map", {}).get(value)
                if mapped:
                    result.update(mapped)
                elif "default" in spec:
                    result.update(spec["default"])
            elif "default" in spec:
                result.update(spec["default"])

        elif inspection_type == "json_value":
            value = _extract_json_value(repo_path, file_pattern, spec["path"])
            if value is not None:
                inspections.append({
                    "file": file_pattern,
                    "field": spec["path"],
                    "value": value,
                })
                # Try version_ranges first, then exact map
                if "version_ranges" in spec:
                    mapped = _match_version_range(value, spec["version_ranges"])
                    if mapped:
                        result.update(mapped)
                    elif "default" in spec:
                        result.update(spec["default"])
                elif "map" in spec:
                    mapped = spec["map"].get(value)
                    if mapped:
                        result.update(mapped)
                    elif "default" in spec:
                        result.update(spec["default"])
            elif "default" in spec:
                result.update(spec["default"])

        elif inspection_type == "presence":
            # For presence checks, handle both glob patterns and exact filenames
            if "*" in file_pattern:
                exists = bool(list(repo_path.glob(file_pattern)))
            else:
                exists = (repo_path / file_pattern).exists()

            if exists:
                inspections.append({
                    "file": file_pattern,
                    "presence": True,
                })
                result.update(spec.get("set", {}))

    result["inspections"] = inspections
    return result


def detect_stack(repo_path: Path, rules_path: Path | None = None) -> dict:
    """Detect tech stack from repository file markers and content inspection.

    Two-pass detection:
      Pass 1: File marker scan → identifies top-level stack
      Pass 2: Content inspection → determines variant, version, OS

    Args:
        repo_path: Path to the repository root.
        rules_path: Path to stack-detection.yaml. Defaults to
                     config/conventions/stack-detection.yaml relative to project root.

    Returns:
        dict with keys: stack, variant, version, os, build_tool, confidence,
                        matched_markers, inspections
    """
    if rules_path is None:
        project_root = Path(__file__).resolve().parent.parent
        rules_path = project_root / "config" / "conventions" / "stack-detection.yaml"

    config = load_detection_rules(rules_path)

    for rule in config.get("rules", []):
        matched = []
        for marker in rule["markers"]:
            # Support glob patterns (*.csproj, *.sln)
            if "*" in marker:
                matches = list(repo_path.glob(marker))
                if matches:
                    matched.append(marker)
            else:
                if (repo_path / marker).exists():
                    matched.append(marker)

        if matched:
            # Pass 1 result
            result = {
                "stack": rule["stack"],
                "variant": None,
                "version": None,
                "os": "linux",
                "build_tool": rule.get("build_tool", "unknown"),
                "confidence": rule.get("confidence", 0.5),
                "matched_markers": matched,
                "inspections": [],
            }

            # Pass 2: Content inspection
            if "inspect" in rule:
                inspection = inspect_content(repo_path, rule)
                if "variant" in inspection:
                    result["variant"] = inspection["variant"]
                if "version" in inspection:
                    result["version"] = inspection["version"]
                if "os" in inspection:
                    result["os"] = inspection["os"]
                result["inspections"] = inspection.get("inspections", [])

            return result

    # No rules matched — use fallback
    fallback = config.get("fallback", {})
    return {
        "stack": fallback.get("stack", "legacy-vm"),
        "variant": None,
        "version": None,
        "os": "linux",
        "build_tool": fallback.get("build_tool", "custom"),
        "confidence": fallback.get("confidence", 0.5),
        "matched_markers": [],
        "inspections": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-detect tech stack from repository file markers"
    )
    parser.add_argument(
        "repo_path",
        type=Path,
        help="Path to the repository root directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON for machine consumption",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=None,
        help="Path to stack-detection.yaml (defaults to config/conventions/stack-detection.yaml)",
    )
    args = parser.parse_args()

    if not args.repo_path.is_dir():
        print(f"Error: {args.repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    result = detect_stack(args.repo_path, args.rules)

    if args.json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Stack:    {result['stack']}")
        variant_str = result['variant'] or "(none)"
        print(f"Variant:  {variant_str}")
        if result['version']:
            print(f"Version:  {result['version']}")
        print(f"OS:       {result['os']}")
        print(f"Build:    {result['build_tool']}")
        print(f"Confidence: {result['confidence']:.0%}")
        if result["matched_markers"]:
            print(f"Markers:  {', '.join(result['matched_markers'])}")
        else:
            print("Markers:  (none — using fallback)")
        if result["inspections"]:
            print("Inspections:")
            for insp in result["inspections"]:
                if "field" in insp:
                    print(f"  {insp['file']}:{insp['field']} = {insp['value']}")
                else:
                    print(f"  {insp['file']}: present")


if __name__ == "__main__":
    main()
