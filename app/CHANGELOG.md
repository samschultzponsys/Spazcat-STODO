# Changelog

All notable changes to STODO are listed here, newest first.

Versions are `MAJOR.MINOR`:

- **MAJOR** (`v2.0`, `v3.0`) — big overhauls, breaking changes, or anything that needs you to touch your compose file.
- **MINOR** (`v2.4`, `v2.5`) — single point releases: features, fixes, and polish that drop straight in.

Each release gets a git tag (`vX.Y`), a GitHub Release, and a matching container image at
`ghcr.io/samschultzponsys/spazcat-stodo:vX.Y`. This file is also what the in-app changelog bubble shows.

## [2.6] - 2026-10-08
### Added
- **Check for updates** button in Settings → Updates that tests the repo and token, even before saving: token accepted or rejected, token expiry date, repo access, missing Contents permission, and whether you're up to date
- `POST /api/version/check` endpoint behind it

### Changed
- README rewritten to cover every current feature, with a full API list and configuration reference

## [2.5] - 2026-10-08
### Added
- Version bubble next to the header title — click it to open the changelog
- Update notification light that flashes on the version bubble when a newer release is published
- Settings → Updates: turn update checks on/off, set the repo to watch, and add a fine-grained GitHub token so checks work on private repos/containers
- `GITHUB_TOKEN`, `UPDATE_REPO` and `UPDATE_CHECK` environment variables (override the UI settings)
- `/api/version` endpoint returning the running version, latest release and changelog
- Every release now ships as a GitHub Release with its own versioned image (`:vX.Y` and `:vX`)
- `scripts/bump-version.sh` helper for cutting major / point releases

### Changed
- Container images are labelled with their version, commit and release date

## [2.4] - 2026-07-26
### Added
- Per-task color picker for scheduled tasks (new task panel and edit modal)
- Color changes on a schedule carry over to any item it already placed on the board

### Changed
- Tag popover lists the most-used tags first, with a "show all" option

### Fixed
- Auto-remove set to 0 or blank now correctly means "never auto-remove"
- Editing a completed schedule re-activates it cleanly, even when the new date is already in the past

## [2.3] - 2026-07-24
### Added
- Header buttons collapse into a ⋯ overflow menu on narrow screens
- Token status indicator in Settings → Authentication

### Changed
- Login sessions are stored in the database, so they are shared across gunicorn workers and survive restarts
- Changing auth settings signs out all existing sessions

### Fixed
- One-time tasks scheduled for a time that has already passed now fire instead of being skipped
- Heads-up → fired color transitions and auto-remove timing for scheduled items

## [2.2] - 2026-07-20
### Added
- `/api/config/export` endpoint for backing up settings (secrets excluded)

### Fixed
- Stray quotes around saved setting values are cleaned up automatically on startup
- An empty token can no longer match an empty `?token=` in the URL
- Login page explains how to use an access token in the URL

## [2.1] - 2026-07-20
### Added
- 🗓 Scheduled Tasks overview: see, edit and delete every pending schedule and the items it has put on the board
- Items created by a schedule are automatically tagged `Scheduled`

### Fixed
- Scheduled items are tracked by their source schedule instead of by text, so duplicates and renames behave
- Heads-up items switch to the solid "fired" color on the day they are due
- Auto-remove only counts down after an item has actually fired

## [2.0] - 2026-07-02
### Added
- Authentication modes: none, token, login, or token + login — configured from the UI
- Multi-user login page with bcrypt-hashed passwords and 7-day sessions
- Security banner when no authentication is configured
- Tags on items, with auto-complete and search
- Per-item colors with a palette and color wheel
- Scheduled tasks: one-time or recurring (weekly / monthly), heads-up preview and auto-remove
- Settings panel with theme presets, branding and colors stored in the database
- Live search across text, tags and dates
- Font size controls (A− / A+ / A↺) and per-device dark / light mode
- `TIMEZONE` environment variable

### Changed
- Branding and color environment variables are now first-run defaults; the settings panel takes over after that

## [1.2] - 2026-06-19
### Added
- Inline edit (✏️) for list items
- Two-tap delete confirmation to prevent accidental removals

## [1.1] - 2026-06-15
### Added
- Pre-built container image published to GHCR, plus a `Dockerfile` and `compose.yaml`
- Can be embedded in iframes (Home Assistant dashboards, kiosk pages)
- Orbitron fallback when the Ethnocentric font isn't installed

## [1.0] - 2026-06-15
### Added
- Initial release: real-time todo wallboard with browser, email (IMAP) and SMS ingest
