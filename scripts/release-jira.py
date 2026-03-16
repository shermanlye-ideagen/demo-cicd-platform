#!/usr/bin/env python
"""JIRA Release — Create version and link resolved tickets.

Called by release.yaml GitHub Actions workflow on tag push.

Author: Sherman Lye
Created: 2026-03-16

Usage:
    python scripts/release-jira.py \
        --version v1.0.0 \
        --project-key IDEVOPS \
        --base-url https://ideagen.atlassian.net
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date


def get_auth_header() -> str:
    """Build Basic auth header from environment variables."""
    email = os.environ.get("ATLASSIAN_EMAIL")
    token = os.environ.get("ATLASSIAN_TOKEN")
    if not email or not token:
        print("ERROR: ATLASSIAN_EMAIL and ATLASSIAN_TOKEN must be set", file=sys.stderr)
        sys.exit(1)
    return "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()


def api_request(base_url: str, path: str, method: str = "GET",
                data: dict | None = None) -> dict:
    """Make an Atlassian REST API request."""
    url = f"{base_url}/rest/api/3{path}"
    body = json.dumps(data).encode() if data else None

    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", get_auth_header())
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read()) if resp.status != 204 else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"JIRA API error {e.code} on {method} {path}: {error_body}", file=sys.stderr)
        if e.code == 404:
            return {"error": "not_found"}
        raise


def create_version(base_url: str, project_key: str, version_name: str) -> dict:
    """Create a new JIRA version."""
    # Get project ID
    project = api_request(base_url, f"/project/{project_key}")
    if "error" in project:
        print(f"Project {project_key} not found", file=sys.stderr)
        sys.exit(1)

    payload = {
        "name": version_name,
        "projectId": int(project["id"]),
        "released": False,
        "releaseDate": date.today().isoformat(),
        "description": f"Release {version_name}",
    }

    version = api_request(base_url, "/version", method="POST", data=payload)
    print(f"Created JIRA version: {version.get('name', version_name)} (ID: {version.get('id', 'unknown')})")
    return version


def find_resolved_tickets(base_url: str, project_key: str, max_results: int = 20) -> list[dict]:
    """Find recently resolved tickets without a fix version."""
    jql = (
        f"project = {project_key} AND status = Done "
        f"AND fixVersion is EMPTY ORDER BY updated DESC"
    )
    params = urllib.parse.urlencode({"jql": jql, "maxResults": max_results, "fields": "summary,status"})
    result = api_request(base_url, f"/search?{params}")
    return result.get("issues", [])


def link_tickets_to_version(base_url: str, issues: list[dict], version_id: str) -> int:
    """Update issues to set the fix version."""
    linked = 0
    for issue in issues:
        key = issue["key"]
        payload = {
            "update": {
                "fixVersions": [{"add": {"id": version_id}}]
            }
        }
        try:
            api_request(base_url, f"/issue/{key}", method="PUT", data=payload)
            print(f"  Linked {key}: {issue['fields']['summary'][:60]}")
            linked += 1
        except Exception as e:
            print(f"  Failed to link {key}: {e}", file=sys.stderr)
    return linked


def main():
    import urllib.parse

    parser = argparse.ArgumentParser(description="Create JIRA release version")
    parser.add_argument("--version", required=True, help="Version tag (e.g., v1.0.0)")
    parser.add_argument("--project-key", required=True, help="JIRA project key")
    parser.add_argument("--base-url", required=True, help="Atlassian base URL")
    args = parser.parse_args()

    print(f"\n=== JIRA Release: {args.version} ===\n")

    # Create version
    version = create_version(args.base_url, args.project_key, args.version)
    version_id = version.get("id")

    if not version_id:
        print("Failed to create version", file=sys.stderr)
        sys.exit(1)

    # Find and link tickets
    print(f"\nSearching for resolved tickets in {args.project_key}...")
    issues = find_resolved_tickets(args.base_url, args.project_key)
    print(f"Found {len(issues)} resolved tickets without fix version")

    if issues:
        linked = link_tickets_to_version(args.base_url, issues, version_id)
        print(f"\nLinked {linked}/{len(issues)} tickets to {args.version}")

    print(f"\n✅ JIRA version {args.version} created successfully")
    print(f"   URL: {args.base_url}/projects/{args.project_key}/versions/{version_id}")


if __name__ == "__main__":
    main()
