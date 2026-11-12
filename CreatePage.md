# Create a page manually

Pages and categories are configured in `dashboard/pages.yaml`. The same file
drives the Home category cards, the expandable sidebar groups, and page URLs.
Page permissions remain in `dashboard/page_access.yaml`.

## Change categories or move an existing page

The initial groups are:

- **Monitoring**: Executive Summary, Model Performance, Campaigns, Drift Monitoring, Loadings Monitoring.
- **Members**: Member Profile.
- **Settings**: Configuration, Models Availability, Connections Checker, Page Access.

Edit `dashboard/pages.yaml` to rename a category, change its description/icon,
reorder categories or pages, or move a page's entire entry into another category's
`pages` list. No Python change is needed for these layout changes.

```yaml
categories:
  - title: Monitoring
    description: Review model performance and campaigns.
    icon: ':material/monitoring:'
    pages:
      - title: Executive Summary
        path: /monitoring
        renderer: executive_summary
        description: Review model health and performance indicators.
        icon: ':material/dashboard:'

  - title: Settings
    description: View configuration and model availability.
    icon: ':material/settings:'
    pages:
      - title: Configuration
        path: /settings
        renderer: configuration
      - title: Models Availability
        path: /models-availability
        renderer: models_availability
```

This is a shortened example. Keep the other page entries in your real file.
The order of YAML entries controls the display order. Description and icon are
optional; icons use the `:material/name:` format and must be quoted in YAML.

Home shows only categories containing pages the user can access. Clicking **Open
category** shows those pages; **All categories** goes back. Sidebar groups start
collapsed on Home. The active page's group opens automatically. **Home** returns
to the category cards.

## Add a new page: Daily Report

This example adds **Daily Report** under Monitoring at
`http://localhost:8501/daily-report`. Replace the host/port for your deployment;
Docker publishes port `8501` by default.

### 1. Create its renderer

Create `dashboard/pages/daily_report.py`:

```python
import streamlit as st


def render_daily_report_page() -> None:
    st.title("Daily Report")
    st.caption("View the daily report.")
    report_date = st.date_input("Report date")
    if st.button("Load report", type="primary"):
        st.info(f"The report for {report_date:%Y-%m-%d} is not connected yet.")
```

Keep rendering and data reads inside the function. Modules are imported before
access checks, so do not query databases or read report data at import time.
Login, access checks, Home, the sidebar, and Sign out are provided by the app.

### 2. Register the Python renderer

In `dashboard/application.py`, add this import beside the other page imports:

```python
from dashboard.pages.daily_report import render_daily_report_page
```

Inside the existing `page_renderers` dictionary in `main()`, add:

```python
        "daily_report": render_daily_report_page,
```

This gives the function a stable renderer name for YAML. The dispatcher runs it
only after authorization. Do not add a separate dispatch branch or sidebar button.
Use `model_renderers` only for a page that takes `(config, selected_cycle)` and
needs the existing model/cycle filter flow.

### 3. Add the page to a category

In `dashboard/pages.yaml`, append this entry to Monitoring's existing `pages`
list, using the same indentation as its other pages:

```yaml
      - title: Daily Report
        path: /daily-report
        renderer: daily_report
        description: View daily report results.
        icon: ':material/description:'
```

The `renderer` must match the key registered in Python. The `title` is the label
shown to users; the `path` is the URL and access-rule key. Titles and paths must
be unique across all categories. Home (`/`) is built in and should not be added.
Paths use a single segment: `/daily-report` is valid; `/reports/daily` is not.
Paths are case-sensitive; the existing `/Loadings` uses a capital L.

Changing a title or moving a page does not change its URL or permissions. If you
change a path, update its access-rule key and any bookmarks that use the old URL.

### 4. Add access rules

You can edit `dashboard/page_access.yaml` in **Settings → Page Access**, then
choose **Save changes**. Append this top-level entry:

```yaml
/daily-report:
  SM - Gaming Analytics: 6
  Operations: 4
  LoyaltyMarketing: 6
```

The key must match `path` in `pages.yaml`. A user must belong to at least one
listed LDAP group and have `tigerLevel` less than or equal to that group's limit.
For example, Operations level 4 qualifies; Operations alone at level 5 does not.
Group names are case-insensitive. Use unquoted, non-negative integer limits.

An omitted rule or `/daily-report: {}` denies access. Missing/invalid levels also
deny access. Unauthorized pages are hidden inside categories, and a category
with no accessible pages is hidden entirely. Direct page URLs enforce the same
rules before rendering or reading data. Categories themselves do not grant access.

The authenticated master account `Rinzai.Terrado` is the exception: it can access
every page, including new pages, without a YAML grant or matching group/level.
This case-insensitive username rule is held in `dashboard/access.py`, separately
from the editable YAML. LDAP login is still required.

### 5. Relaunch and check

For local use, stop the app and relaunch `run-local.bat`. It copies `dashboard/`,
including both YAML files, into the local app directory. For Docker:

```powershell
docker compose build --pull=false
docker compose up -d --no-build --pull never
```

Verify:

1. Home shows Monitoring. Open it and confirm Daily Report appears for an allowed account.
2. Expand Monitoring in the sidebar and open Daily Report. The URL becomes `/daily-report`.
3. Open that URL while signed out. Sign in with a network username, not an email address.
4. Refresh the page; login and the current page should persist.
5. With an unauthorized account, confirm the page is hidden and its direct URL is blocked.

The running app rereads both YAML files on each interaction. Relaunch/rebuild for
`pages.yaml` navigation changes. Access-rule edits apply on the next interaction:
the local launcher uses the source access file, and Compose mounts the host file's
directory for persistent edits. LDAP membership/level changes require signing out
and in again. The Page Access editor validates before saving and keeps the previous
file as `page_access.yaml.bak`; only accounts allowed by `/page-access` may edit it.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Missing page/category | The page entry in `pages.yaml`, its URL-keyed access rule, and the user's group/level |
| Unknown page renderer | The YAML `renderer` must match a key in `page_renderers` or `model_renderers` |
| Invalid navigation configuration | YAML structure, unique titles/paths, valid icons, and required `title`, `path`, `renderer` fields |
| Direct link denied | Exact path spelling and case, group CN, and LDAP `tigerLevel` |
| Wrong category/order | Move/reorder entries in `pages.yaml` |
| Changes do not appear | Relaunch the local copy or rebuild/recreate Docker |
