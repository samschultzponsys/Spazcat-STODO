# CLAUDE.md

Guidance for Claude Code sessions working in this repo. Open work and known follow-ups live in `NOTES.md`.

## What this is

STODO (SpazCat TODO) — a self-hosted, real-time todo **wallboard**. One Flask app serves a single-page UI that polls every 5 s. Items come from the browser, email (IMAP), SMS (android-sms-gateway / Twilio) or `POST /ingest/text`. Built for tablets/kiosks and Home Assistant iframes. Owner's top goal: **low friction** — no kanban, no extra steps.

The owner is not a developer. Keep changes simple and explain trade-offs in plain language.

## Stack

- **Backend:** `app/app.py` — one Flask file (Python 3.12, gunicorn 2 workers × 2 threads, SQLite, APScheduler, bcrypt). No ORM; raw `sqlite3`.
- **Frontend:** `app/static/index.html` — one file, vanilla JS + inline CSS, no build step. `login.html` is the login page.
- **Packaging:** `Dockerfile` → `ghcr.io/samschultzponsys/spazcat-stodo`. `compose.yaml` is the example deploy.
- **CI:** `.github/workflows/docker.yml` (build, tag, release). `scripts/bump-version.sh` starts a release.
- No test suite, no linter config.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
cd app && env -u GITHUB_TOKEN DB_PATH=/tmp/stodo/stodo.db ../.venv/bin/python app.py   # http://localhost:5000
# or the real server:  ../.venv/bin/gunicorn app:app -b 127.0.0.1:5000 -w 2
```

- `DB_PATH` defaults to `/data/stodo.db`; set it anywhere writable. The scheduler lock file goes in the same folder.
- Clone-style deploy (README "Method 2") bind-mounts `./app` and runs `app/start.sh`.

## How to verify changes (no test suite)

- **Backend:** Flask `app.test_client()` scripts. Import `app` with `DB_PATH` pointing at a scratch DB. For IP and auth logic, use `test_request_context('/', environ_base={'REMOTE_ADDR': ...}, headers={...})`.
- **GitHub calls:** monkeypatch `app._github_get` to simulate 200/401/403/404 responses.
- **UI:** Playwright + Chromium are preinstalled in cloud sessions (`NODE_PATH=$(npm root -g)`). Screenshot desktop (1100 px) and mobile (390 px) in dark and light themes.
- **Workflow:** run `actionlint` on the workflow file. To dry-run the bash steps, extract them and run with `bash -eo pipefail` against a throwaway clone, with `docker`/`gh` stubbed.
- **Under gunicorn:** Flask drops `app.logger.info` by default. Set `logging.getLogger("app").setLevel(INFO)` before importing to see "Scheduler started".

## Releases and versioning

- Versions are **`MAJOR.MINOR`** (no patch number). The owner calls MINOR a "single point release".
  - **Major:** overhauls, breaking changes, or anything that needs a compose change.
  - **Minor:** features and fixes that drop straight in.
- **Source of truth:** `app/VERSION`. Release notes live in `app/CHANGELOG.md`, newest first:
  - Heading: `## [X.Y] - YYYY-MM-DD`
  - Sections: `### Added`, `### Changed`, `### Fixed`, `### Security`
  - Entries: `- bullets`
- **To release:**
  1. `scripts/bump-version.sh minor|major`
  2. Replace the `TODO` lines in the changelog
  3. Commit and push to `main`
- **CI on push to main:**
  - Fails if `VERSION` has no changelog entry, or the entry still contains `TODO`.
  - Tags `vX.Y` (annotated), and creates any missing tags listed in `.github/backfill-tags.txt`.
  - Then for every tagged changelog version missing an image or a GitHub Release: builds `:vX.Y` (+ `:vX` for the newest of each major) and publishes a release with that changelog section as notes.
  - Idempotent. A manual run with `rebuild` ticked rebuilds all release images.
- **Image tags:**
  - `:latest`: every push to main
  - `:dev`: dev branch, version shown as `X.Y-dev`
  - `:<sha>`, `:vX.Y`, `:vX`
- Ship each user-facing change as its own version bump plus changelog entry. That's how the in-app update light finds it.
- The owner works directly on `main` (no PR flow) and has asked that finished work be pushed there. Only fast-forward; never force-push.

## How versioning surfaces in the app

- **Running version:** `APP_VERSION`/`APP_COMMIT` env vars (baked in by the Dockerfile build args), falling back to `app/VERSION`.
- **`GET /api/version`:** merges newer GitHub releases (flagged `new`) with the bundled `CHANGELOG.md` (the running one is flagged `installed`).
- **Parsing:** `parse_changelog()` parses the changelog. Release bodies are parsed only up to the `---` footer, and `Released: YYYY-MM-DD` in the footer gives the real date. Keep the CI notes format and these parsers in sync.
- **Update cache:** stored in the `settings` table under key `update_cache`, so all workers share one result.
  - TTLs: 6 h normally, 30 min after an error.
  - A forced check is ignored if the last one was under 15 s ago.
- **`POST /api/version/check`:** tests the repo/token from the settings form without saving them. When it tests the saved settings, it also writes the cache.
- **Settings keys:** `update_check`, `update_repo`, `github_token`. Env `GITHUB_TOKEN`/`UPDATE_REPO`/`UPDATE_CHECK` override them.

## Conventions

- **New API route:** start with `result = check_token()` / `if result: return result`. Ingest routes use `check_ingest()` instead.
- **Frontend fetches:** every `/api` call must append the `QS` token query string. Escape any user or remote text with `escHtml()`. Only render links that match `^https://`.
- **Secrets:** never send them to the browser. Add new secret settings to `SECRET_KEYS` (and internal blobs to `INTERNAL_KEYS`) so `/api/config` and `/api/config/export` strip them. Expose a `has_*` boolean instead.
- **Settings:** add defaults in `init_db()` with `INSERT OR IGNORE`. New columns go in the ad-hoc `ALTER TABLE` migration lists there.
- **Code style:** match the existing style — aligned assignments, terse comments, section banners (`# ── Name ───`). UI copy is short and friendly.
- **Commits:** imperative subject, body explaining *why*. Mention the version when releasing, e.g. "… (v2.7)".

## Non-obvious decisions and gotchas

- **LAN trust** (`is_lan`) — LAN clients skip auth entirely.
  - `X-Forwarded-For` is trusted **only** when `remote_addr` is private (i.e. the reverse proxy), and only its **last** entry is used.
  - Using the first entry was an auth bypass (fixed in v2.7). Don't revert to prefix matching or the first entry.
  - Private ranges come from `ipaddress`; the old `'172.'` string prefix wrongly matched public IPs.
- **Scheduler + IMAP poller** must run in exactly one gunicorn worker.
  - It uses `fcntl.flock` on `<db dir>/.imap_lock`, held open for the worker's lifetime.
  - The old `O_EXCL` lock file survived restarts in the `/data` volume and silently stopped scheduling (fixed in v2.7). Don't go back to create-if-missing locks.
- **Branding/color env vars** (`APP_TITLE`, `ACCENT_COLOR`, …) only seed the DB on first start. `TOKEN`, `GITHUB_TOKEN` and `UPDATE_*` always override.
- `set_setting()` strips one pair of surrounding quotes (legacy data cleanup). Don't store values that legitimately start and end with quotes.
- Changing `auth_mode` or the token clears all sessions (DB-backed, 7-day TTL).
- `INGEST_SECRET` unset means `/ingest/*` is open to anyone. Ingest routes ignore the auth mode.
- **Fonts:** CSS only loads `/fonts/ethnocentric_rg.otf` and `ethnocentric_rg_it.otf` (bundled), falling back to Orbitron. A custom font must use those filenames. Mounting a folder over `app/static/fonts` hides the bundled files.
- **Backfilled releases:**
  - GitHub won't let `GITHUB_TOKEN` create a tag on a commit whose `.github/workflows/*` content isn't on any existing ref ("refusing to allow a GitHub App to create or update workflow"). CI warns and skips such tags.
  - Releases are ordered by the tag's commit date, so backdated releases sort correctly even though `published_at` is recent.
- **Cloud-session limits seen so far:**
  - The git proxy only allows pushes to the session branch and `main`. Tag pushes get 403.
  - The auto-mode classifier blocks force-pushes and pushing workflow-file reverts.
  - Workflow job logs aren't reachable via `gh` (blob host blocked). Use the GitHub MCP `get_job_logs` with `return_content`.
- **Sandbox env:** the sandbox sets its own `GITHUB_TOKEN`. Run the app with `env -u GITHUB_TOKEN`, or it overrides the settings token. The proxy also injects GitHub auth, so a fake token won't produce a 401 there. For outbound HTTPS from Python, set `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt`.

## Deploy (owner's setup)

- Pre-built image on `:latest`, behind Nginx Proxy Manager on a shared Docker network.
- Updating: `docker compose pull && docker compose up -d`.
- Never put real credentials in the repo, commits or docs. Compose examples use placeholders.
