# Washburn Service Desk — YTD Dashboard

An Apple-inspired bento grid dashboard for Washburn Center for Children's IT and EHR service desks. Pulls live ticket data from Jira, auto-refreshes every 30 minutes, and is protected behind Microsoft Entra ID SSO.

## Live URL

**https://purple-tree-0f595bf10.6.azurestaticapps.net**

Requires Washburn Entra ID login (tenant `fa52e603-adbe-4c95-8c80-627b064b7b75`).

## Features

- **IT / EHR toggle** — switch between IT Service Desk (WITS) and EHR project data
- **Interactive drill-downs** — click any stat, pill, bar, or assignee row for aggregate breakdowns
- **Auto-refresh** — GitHub Actions fetches fresh Jira data every 30 minutes; browser reloads every 30 minutes
- **Responsive** — desktop (4-col), tablet (2-col), and mobile (1-col) layouts
- **Animations** — subtle pulse, shimmer, float, and glow effects
- **Entra SSO** — Microsoft Entra ID authentication, restricted to Washburn tenant

## Dashboard Cards

| Card | Data Shown |
|------|-----------|
| Hero | Project title, date range (dynamic), Washburn logo, IT/EHR toggle |
| Total Tickets | YTD count with tickets/day rate |
| Resolved | Resolution percentage and count |
| Open | Unresolved tickets with waiting-for-support count |
| Median Resolution | Median and average resolution time |
| Monthly Volume | Bar chart for Jan / Feb / Mar |
| Top Requests | Top 5 request types as clickable pills |
| Incidents | Incident breakdown by category |
| Priority & Status | Status distribution as clickable pills |
| Team Workload | Horizontal bars per assignee |
| Quote | Auto-generated summary stat |

## Architecture

```
GitHub Repo (ARaquel-WCC/wits-ytd-dashboard)
├── index.html              # Dashboard UI (static, ~40KB)
├── data.json               # Ticket data (auto-updated by CI)
├── washburn-logo.png       # Washburn Center logo
├── staticwebapp.config.json # Auth config (Entra SSO)
├── scripts/
│   └── fetch-data.py       # Jira data fetcher
└── .github/workflows/
    ├── deploy.yml           # Deploy on push to main
    └── refresh-data.yml     # Fetch Jira data every 30 min
```

## Azure Resources

| Resource | Type | Resource Group | Details |
|----------|------|----------------|---------|
| `wits-ytd-dashboard` | Static Web App | IT-Operations | Standard tier, Central US |
| Entra App Registration | App Registration | — | App ID: `2afb4fb2-92c4-4fa4-9a5f-8c2ac525f566` |
| `wits-dashboard-budget` | Cost Budget | IT-Operations | $15/month, scoped to SWA resource only |

## CI/CD Workflows

### `deploy.yml` — Deploy on Push
- Triggers on push to `main` or PR events
- Deploys static files to Azure Static Web Apps

### `refresh-data.yml` — Refresh Jira Data
- Runs every 30 minutes (cron) or manually via workflow_dispatch
- Fetches YTD tickets from WITS and EHR Jira projects
- Writes `data.json` and commits if data changed
- Deploys updated data to Azure

## GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | SWA deployment token |
| `JIRA_EMAIL` | Jira API authentication email |
| `JIRA_TOKEN` | Jira API token |

## Jira Projects

| Project | Key | Description |
|---------|-----|-------------|
| IT Service Desk | WITS | General IT support tickets |
| EHR Service Desk | EHR | Electronic Health Records support (launched Mar 16, 2026) |

## Cost

| Item | Monthly Cost |
|------|-------------|
| Azure Static Web App (Standard) | ~$9 |
| GitHub Actions (~48 runs/day) | $0 (within free tier) |
| Entra App Registration | $0 |
| **Total** | **~$9/month** |

Budget alert at $12 (80%) and $15 (100%) → emails antonio.raquel@washburn.org.

## Local Development

```bash
# Clone
git clone https://github.com/ARaquel-WCC/wits-ytd-dashboard.git
cd wits-ytd-dashboard

# Fetch fresh data locally
export JIRA_EMAIL="your-email@washburn.org"
export JIRA_TOKEN="your-api-token"
python scripts/fetch-data.py

# Open in browser
open index.html
```

## Adding a New Jira Project

1. Edit `scripts/fetch-data.py` — add a new `fetch_project("PROJECT_KEY")` call
2. Add the data to the `output` dict with a new key
3. Edit `index.html` — add the key to `CONFIG` and a new toggle button in the `buildDashboard` function
