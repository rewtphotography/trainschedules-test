# Metuchen ⇄ NY Penn trains

A one-page web app listing today's scheduled NJ Transit departure and arrival times
between Metuchen and New York Penn Station, with a direction toggle.

A GitHub Action downloads NJ Transit's official rail schedule (GTFS) every morning,
writes `site/schedule.json`, and publishes `site/` to GitHub Pages.

## Setup
1. Register for free at https://developer.njtransit.com (RailData API access).
2. Repo → Settings → Secrets and variables → Actions: add `NJT_USERNAME` and `NJT_PASSWORD`.
3. Repo → Settings → Pages → Source: **GitHub Actions**.
4. Actions → "Update schedule" → Run workflow.
5. On iPhone, open the Pages URL in Safari → Share → **Add to Home Screen**.
