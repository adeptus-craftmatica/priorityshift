# PriorityShift

A Flask platform for managing development priorities, workload, interruptions,
and the business decisions behind them. Every priority change, deadline
revision, and interruption is logged as a permanent, auditable record — so
"why was this late?" has a documented answer instead of a guess.

## Stack

- Flask, SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- SQLite (swap `DATABASE_URL` for Postgres later — no code changes needed)
- Tailwind CSS (compiled, committed output — no build step required to run)
- HTMX + Alpine.js for interactivity, Chart.js for report charts
- PySide6 for the desktop Control Panel (`main.py`), styled to match the
  web app's dark theme

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Option A: the Control Panel (recommended — no terminal needed after this)

Run `main.py` with the project's venv:

```bash
.venv/bin/python main.py
```

This opens a desktop **Control Panel** window. From there:

1. **Create Admin Account** — sets up the database and creates your own
   account (President role, full access). This is the normal way to get
   your first login — no CLI, no pre-made demo credentials to remember.
2. **Start Server**, then **Open in Browser →** to launch the app and sign
   in with the account you just created.
3. **Load Sample Data** (optional) — populates demo departments, users, and
   sample projects/chores/ideas so you can see the app fully populated
   instead of empty. Only does anything on a database that has no accounts
   yet.

The activity log at the bottom shows what's happening (migrations, server
output, errors) — the panel keeps things visible without requiring you to
read a terminal.

### Option B: the CLI

```bash
export FLASK_APP=wsgi.py
flask db upgrade
flask seed-db      # optional — demo departments, users, sample work items
flask run --port 8000
```

If you use `flask seed-db`, the demo accounts it prints all use the password
`priorityshift`, e.g. `sarah.president` (President), `dana.director`
(Director), `mike.manager` (Manager), `eli.dev` (Employee).

**Why port 8000, not Flask's default 5000**: on macOS (Monterey and later),
Apple's AirPlay Receiver already listens on port 5000 by default. A server
started on 5000 will fail to bind and exit immediately, and opening
`http://127.0.0.1:5000` in a browser connects to AirPlay Receiver instead of
Flask — which looks exactly like "the app won't start" and "the page is
blank." The Control Panel already defaults to 8000 for this reason; if you
turn off AirPlay Receiver in System Settings → General → AirDrop & Handoff,
5000 works fine too, but 8000 avoids the whole issue.

## Working on styles

The compiled CSS (`app/static/css/output.css`) is committed, so `flask run`
works without Node installed. If you're changing Tailwind classes:

```bash
npm install
npm run watch:css   # or `npm run build:css` for a one-off build
```

## Tests

```bash
python -m pytest
```

## Project layout

- `app/models/` — SQLAlchemy models (users/roles, projects, chores, ideas,
  priority events, deadline revisions, interruptions, comments, etc.)
- `app/services/` — the domain logic: permissions, the priority-change
  workflow (impact preview → acknowledgment → commit → audit trail),
  recurring-chore scheduling, dashboards, reports.
- `app/blueprints/` — routes, one folder per area of the app.
- `app/templates/` — Jinja templates; `macros/ui.html` holds the shared
  design-system components (priority badges, stat tiles, cards, etc.)
- `seed.py` — `ensure_catalog()` (roles/priority levels/phases, idempotent),
  `create_admin_user()` (used by the Control Panel), and `run_seed()` (full
  demo dataset, used by both `flask seed-db` and the Control Panel's "Load
  Sample Data").
- `main.py` — the PySide6 desktop Control Panel (start/stop the server,
  create your admin account, load sample data — all without a terminal).

## What's here vs. what's next

**Phase One**: auth, roles/permissions, personal and organization dashboards,
Projects/Chores/Ideas, the priority-change workflow with audit trail,
deadline history, interruption logging, comments, basic recurring chores,
activity timeline, reports (with CSV export), and global search.

**Phase Two (complete)**:
- File attachments — upload/download/delete on projects, chores, and ideas
  (`app/services/attachments.py`, `app/blueprints/attachments/`).
- Notifications actually get created now, not just displayed: new
  assignments, deadline changes, comment `@mentions`, decisions, blockers,
  capacity conflicts on assignment, and opportunistic due-soon/overdue
  reminders generated (de-duplicated) when someone loads their own
  dashboard. See `app/services/notifications.py`.
- Fixed along the way: manually editing a project's deadline used to
  silently overwrite it with no audit trail — it now goes through the same
  `deadline_service.revise_deadline()` path as priority-driven pushes, so
  every deadline change is preserved and notifies assignees.
- PDF/Excel export alongside CSV on every report (`app/services/exports.py`),
  dispatched through a shared `export_response()` helper.
- A live interruption timer on the project detail page (Alpine.js) — start
  it the moment you're pulled away, stop it to auto-fill the minutes field.
- System-projected completion dates: `deadline_service.get_projected_completion()`
  computes a finish date from remaining effort, each assignee's capacity
  split across their active projects, and the project's own interruption
  drag, then flags when that's later than the current deadline.
- Management dashboard enhancements: capacity utilization (committed vs.
  weekly capacity) added to the Workload report, plus a new Chore
  Compliance report (on-time/late/missed, by assignee).
- A calendar view (`/calendar`) — a server-rendered month grid of project
  deadlines and chore due dates, no external calendar JS library needed.
- A deadline-change approval workflow: an admin-configurable
  `WorkflowRule` (`require_approval_for_deadline_push`, threshold in days)
  decides when a deadline push needs sign-off. Requests that need approval
  land in `/deadline-approvals` as `DeadlineRevision` rows with
  `status="pending"` and don't touch the project until approved or
  rejected — mirroring the same guardrail pattern the priority-change
  workflow already uses.

**Phase Three (complete)**:
- Workload forecasting (`app/services/forecast_service.py`): projects each
  developer's weekly load for the next 4/8/12 weeks by spreading each active
  project's remaining hours across the weeks until its deadline, adding
  upcoming chore load, and comparing against an *effective* weekly capacity
  (their stated capacity minus their own recent interruption drag). Surfaces
  as `/reports/workload-forecast` — an org-wide load-vs-capacity chart plus
  a table of developers projected to be overloaded, with CSV/Excel/PDF
  export.
- A Kanban board (`/projects?view=board`) — native HTML5 drag-and-drop
  between phase columns, no external library, backed by a small JSON
  endpoint (`projects.update_phase_ajax`).
- A project timeline (`/projects?view=timeline`) — a plain CSS Gantt-lite:
  each project becomes a positioned/sized bar within a rolling 16-week
  window, colored by priority, with a "today" marker.
- Real notification delivery (`app/services/delivery.py`): email via stdlib
  `smtplib`, Slack/Teams via incoming webhook. Off by default
  (`NOTIFICATION_DELIVERY_ENABLED=false`) and each channel independently
  no-ops if unconfigured, so a fresh checkout never tries to send anything.
  Set the `MAIL_*` / `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` env vars (see
  `.env.example`) to actually wire it up.
- Optional TOTP-based two-factor authentication (`app/services/mfa_service.py`,
  using `pyotp`): enable/disable from `/auth/account`, enforced as a second
  login step when turned on. Off by default — this app's whole premise is
  low-friction internal auth, so MFA stays opt-in per user rather than
  mandatory.
- Generic OIDC SSO login (Authlib): a "Sign in with {provider}" button on
  the login page that only appears once `OIDC_CLIENT_ID` and
  `OIDC_DISCOVERY_URL` are set — dormant otherwise. It matches the signed-in
  identity to an existing account by email; it does not auto-provision new
  accounts (an admin still creates those, same as everywhere else in this
  app). Username/password login stays available either way.
- A client portal (`/portal`, `app/blueprints/portal/`): a deliberately
  narrow, separately-chromed view for external client contacts
  (`User.client_id` set via the admin Users screen). Shows only that
  client's own projects, with a restricted field set — no financial
  classification, no internal notes/risks/roadblocks, no priority-change or
  interruption history — plus a comment thread limited to comments either
  side has explicitly marked `client_visible`. A `before_request` hook
  redirects client-contact accounts to the portal if they hit any internal
  URL, so the boundary doesn't depend on every internal route remembering
  to check for it.

Still deferred: drag-and-drop *within* the calendar view (the Kanban board
covers the "board" case; the calendar itself stays read-only), and workload
forecasting doesn't yet factor in PTO/holidays.
