#!/usr/bin/env python3
"""Fetch WITS and EHR ticket data from Jira and write data.json

Writes two structures per project:
  - Full YTD ticket list for dashboard stats
  - Last 10 activity events (create/status/assign/priority/comment) for the live ticker
"""
import json
import os
import re
import subprocess
import urllib.parse

JIRA_BASE = "https://washburncfc.atlassian.net/rest/api/3/search/jql"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_TOKEN = os.environ["JIRA_TOKEN"]
FIELDS = "key,summary,status,priority,created,resolved,resolutiondate,issuetype,reporter,assignee,customfield_10010"
ACTIVITY_FIELDS = "key,summary,status,created,reporter,assignee,comment"
# Status names that indicate a ticket was resolved (used to distinguish "resolved" from generic "status" events)
RESOLVED_STATUSES = {"done", "resolved", "closed", "cancelled", "canceled"}


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


def fetch_activity(project, limit=10):
    """Fetch the 10 most recent activity events (create, status, assign, priority, comment)
    from tickets updated in the last 14 days. Uses one search call with expand=changelog."""
    jql = f'project={project} AND updated>=-14d ORDER BY updated DESC'
    auth = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
    url = (
        f"{JIRA_BASE}?jql={urllib.parse.quote(jql)}&maxResults=30"
        f"&fields={ACTIVITY_FIELDS}&expand=changelog"
    )
    result = subprocess.run(
        ["curl", "-s", "-u", auth, url],
        capture_output=True, text=True, timeout=30
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    events = []
    for issue in data.get("issues", []):
        key = issue["key"]
        f = issue["fields"]
        summary = (f.get("summary") or "")[:60]

        # "Ticket created" event
        reporter = (f.get("reporter") or {}).get("displayName", "Unknown")
        events.append({
            "type": "created",
            "actor": reporter,
            "ticket": key,
            "summary": summary,
            "detail": "",
            "time": parse_tz(f.get("created", "")),
        })

        # Walk the changelog to extract status/assignee/priority changes
        changelog = issue.get("changelog", {})
        for history in changelog.get("histories", []):
            author = (history.get("author") or {}).get("displayName", "System")
            h_time = parse_tz(history.get("created", ""))
            for item in history.get("items", []):
                field = item.get("field", "")
                to_str = item.get("toString", "") or ""
                from_str = item.get("fromString", "") or ""
                if field == "status":
                    is_resolved = to_str.lower() in RESOLVED_STATUSES
                    events.append({
                        "type": "resolved" if is_resolved else "status",
                        "actor": author,
                        "ticket": key,
                        "summary": summary,
                        "detail": f"{from_str} → {to_str}" if from_str else to_str,
                        "time": h_time,
                    })
                elif field == "assignee":
                    events.append({
                        "type": "assigned",
                        "actor": author,
                        "ticket": key,
                        "summary": summary,
                        "detail": f"→ {to_str}" if to_str else "unassigned",
                        "time": h_time,
                    })
                elif field == "priority":
                    events.append({
                        "type": "priority",
                        "actor": author,
                        "ticket": key,
                        "summary": summary,
                        "detail": f"{from_str} → {to_str}",
                        "time": h_time,
                    })

        # Comment events (last 2 per ticket to avoid flooding)
        comments = (f.get("comment") or {}).get("comments", [])
        for c in comments[-2:]:
            author = (c.get("author") or {}).get("displayName", "Unknown")
            events.append({
                "type": "comment",
                "actor": author,
                "ticket": key,
                "summary": summary,
                "detail": "",
                "time": parse_tz(c.get("created", "")),
            })

    # Sort by timestamp desc and return the N most recent
    events.sort(key=lambda e: e.get("time", ""), reverse=True)
    return events[:limit]


if __name__ == "__main__":
    print("Fetching WITS data...")
    wits = fetch_project("WITS")
    print(f"  Got {len(wits)} tickets")

    print("Fetching EHR data...")
    ehr = fetch_project("EHR")
    print(f"  Got {len(ehr)} tickets")

    print("Fetching WITS activity...")
    wits_activity = fetch_activity("WITS")
    print(f"  Got {len(wits_activity)} events")

    print("Fetching EHR activity...")
    ehr_activity = fetch_activity("EHR")
    print(f"  Got {len(ehr_activity)} events")

    output = {
        "it": wits,
        "ehr": ehr,
        "activity": {"it": wits_activity, "ehr": ehr_activity},
    }
    with open("data.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))
    print(f"Wrote data.json ({os.path.getsize('data.json')} bytes)")
