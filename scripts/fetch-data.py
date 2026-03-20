#!/usr/bin/env python3
"""Fetch WITS and EHR ticket data from Jira and write data.json"""
import json
import os
import re
import subprocess
import urllib.parse

JIRA_BASE = "https://washburncfc.atlassian.net/rest/api/3/search/jql"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_TOKEN = os.environ["JIRA_TOKEN"]
FIELDS = "key,summary,status,priority,created,resolved,resolutiondate,issuetype,reporter,assignee,customfield_10010"


def parse_tz(s):
    """Convert -0500 to -05:00 for JS compatibility."""
    return re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s) if s else ""


def fetch_project(project):
    jql = f'project={project} AND created>="2026-01-01" ORDER BY created DESC'
    auth = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
    all_issues = []
    next_token = None

    while True:
        url = f"{JIRA_BASE}?jql={urllib.parse.quote(jql)}&maxResults=100&fields={FIELDS}"
        if next_token:
            url += f"&nextPageToken={urllib.parse.quote(next_token)}"
        result = subprocess.run(
            ["curl", "-s", "-u", auth, url],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        issues = data.get("issues", [])
        all_issues.extend(issues)
        if data.get("isLast", True):
            break
        next_token = data.get("nextPageToken")
        if not next_token:
            break

    tickets = []
    for issue in all_issues:
        f = issue["fields"]
        created = parse_tz(f.get("created", ""))
        resolved = parse_tz(f.get("resolutiondate") or f.get("resolved") or "")
        cf = f.get("customfield_10010")
        req_type = cf.get("requestType", {}).get("name", "") if cf and isinstance(cf, dict) else ""
        tickets.append({
            "key": issue["key"],
            "summary": (f.get("summary") or "")[:80],
            "status": (f.get("status") or {}).get("name", "Unknown"),
            "priority": (f.get("priority") or {}).get("name", "None"),
            "type": (f.get("issuetype") or {}).get("name", "Unknown"),
            "created": created,
            "resolved": resolved,
            "reporter": (f.get("reporter") or {}).get("displayName", "Unknown"),
            "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "reqType": req_type,
        })
    return tickets


if __name__ == "__main__":
    print("Fetching WITS data...")
    wits = fetch_project("WITS")
    print(f"  Got {len(wits)} tickets")

    print("Fetching EHR data...")
    ehr = fetch_project("EHR")
    print(f"  Got {len(ehr)} tickets")

    output = {"it": wits, "ehr": ehr}
    with open("data.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))
    print(f"Wrote data.json ({os.path.getsize('data.json')} bytes)")
