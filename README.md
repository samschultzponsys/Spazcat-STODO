# SpazCat TODO (STODO)

A self-hosted, real-time todo wallboard. Add items from a browser, email, or SMS. Designed to live on a screen — a tablet on the wall, a monitor at your desk, a phone in the kitchen. No login required for display. No kanban, no projects, no friction.

Friction is the number one goal in this project — I needed something I could access quickly yet securely enough to be comfortable exposing to the global internet. Sure there are apps, sure there are kanban solutions, but most require login, have too many steps, or too many flows.

![Dark mode wallboard](https://img.shields.io/badge/theme-dark%20%2F%20light-5f249f?style=flat-square)
![Docker](https://img.shields.io/badge/docker-ghcr.io-0db7ed?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## Features

**The board**
- **Live updates** — every screen polls every 5 seconds, no refresh needed
- **Add items** — type in the browser, send an email, send an SMS, or POST from a script
- **Inline edit** — ✏️ on any item, Enter to save, Esc to cancel
- **Delete with confirmation** — tap ✕, it turns into ✓, tap again within 2.5 s
- **Reorder** — drag and drop on desktop and touch drag on mobile
- **Tags** — multiple per item, most-used tags suggested first, fully searchable
- **Per-item color** — palette or color wheel, shown as a color wash with a colored left border
- **Live search** — filters by text, tags, item type, and dates (including day names like "friday")

**Scheduling**
- **Scheduled tasks** — one-time, weekly, or monthly, with a heads-up preview and optional auto-remove
- **Per-task colors** — each schedule can have its own color, or use the one-time / recurring defaults
- **Upcoming list** — pending schedules shown under the board, editable in place
- **Scheduled Tasks overview** — 🗓 in the header lists every schedule and every board item it created
- **Convert any item** into a scheduled task from its ⚙ menu

**Look & feel**
- **Settings panel** — theme presets, branding, colors and scheduling defaults, saved server-side
- **Dark / light mode** and **font size** (A− / A+ / A↺) — remembered per device
- **Narrow-screen friendly** — header buttons collapse into a ⋯ menu on phones
- **Iframe friendly** — embeds cleanly in Home Assistant dashboards and kiosk pages
- **Custom display font** — swap in your own font file

**Access & security**
- **Authentication** — none / token / login / token + login, switchable from the UI with no restart
- **Multi-user login** — users managed in Settings, bcrypt-hashed passwords, 7-day sessions shared across workers
- **LAN is trusted** — no auth prompts on your home network
- **Security banner** — warns when no auth is configured

**Ingest**
- **Email** — IMAP polling, the subject line becomes an item
- **SMS** — Android SMS Gateway or Twilio, any text to the number hits the board
- **HTTP push** — `POST /ingest/text` from scripts, Home Assistant, Node-RED, etc.

**Releases**
- **Version bubble** next to the header title — click for the changelog
- **Update light** — flashes green when a newer release is on GitHub (works with private repos via a token)
- **Versioned images** — every release is published as `:vX.Y`, with `:vX` and `:latest` tracking the newest

> **Note:** This has been coded with assistance from AI. I am not a dev — I am alright with frontend coding and a tiny bit of backend — but I did have a real dev look it over and they did not see any glaring concerns. By all means fork it and fix it. For this project I did NOT want a traditional local auth or embedded auth, but would consider an integration to add one with env flags. OIDC would be hot on my list, but at that point you might be better off with another project. I also use KanBN and really like it for more traditional project management: https://github.com/kanbn/kan

---

## Screenshots

Desktop dark mode wallboard — fully customizable:
<img width="1651" height="750" alt="image" src="https://github.com/user-attachments/assets/4f396fb1-b541-4a2c-b71d-9acfd031fbae" />

Mobile dark and light mode, embedded in Home Assistant:
<img width="1080" height="2520" alt="Screenshot_20260619_140629_Home Assistant (1)" src="https://github.com/user-attachments/assets/ab9289b4-48af-4b60-9d1a-16844ca91a0c" />
<img width="1080" height="2520" alt="Screenshot_20260619_140629_Home Assistant" src="https://github.com/user-attachments/assets/b5117205-f9ef-4788-b504-622040d1a7d2" />

---

## Installation

Two ways to run STODO — pick whichever suits you.

---

### Method 1 — Pre-built Container (easiest)

No cloning required. Pull the image directly from GitHub Container Registry.

**1. Create directories**

```bash
mkdir -p stodo/data
cd stodo
```

**2. Create `compose.yaml`**

```yaml
services:
  stodo:
    image: ghcr.io/samschultzponsys/spazcat-stodo:latest
    container_name: stodo
    restart: unless-stopped
    environment:
      DB_PATH: /data/stodo.db

      # ── Security ───────────────────────────────────────────────
      # Auth mode is chosen in the UI settings panel.
      # TOKEN: yourtoken          # optional — overrides the UI token
      INGEST_SECRET: yoursecret   # protects /ingest/* — without it they're open to anyone

      # ── Branding (optional — first start only, then use Settings) ──
      # APP_TITLE:    "MY TODO"
      # APP_SUBTITLE: STODO       # browser tab title

      # ── Colors (optional — first start only, then use Settings) ─
      # ACCENT_COLOR:  "#5f249f"
      # BG_COLOR:      "#0d0d0d"
      # SURFACE_COLOR: "#161616"
      # TITLE_COLOR:   "#ffffff"
      # TEXT_COLOR:    "#f0f0f0"

      # ── Email Ingest (optional) ────────────────────────────────
      # IMAP_HOST:     imap.yourprovider.com
      # IMAP_PORT:     993
      # IMAP_USER:     stodo@yourdomain.com
      # IMAP_PASS:     your-app-password
      # IMAP_INTERVAL: 30

      # ── Timezone ───────────────────────────────────────────────
      # TIMEZONE: America/Chicago

      # ── Update checks (optional — these override Settings → Updates) ─
      # GITHUB_TOKEN:  github_pat_xxx               # only for private repos
      # UPDATE_REPO:   samschultzponsys/Spazcat-STODO
      # UPDATE_CHECK:  "true"                       # "false" disables checks

    volumes:
      - ./data:/data
      # - ./fonts:/app/static/fonts  # optional — see Custom Font
    ports:
      - "8234:5000"
```

**3. Start**

```bash
docker compose up -d
```

**4. Configure auth** — open the UI, click ⚙ → Authentication. Until you do, a security banner reminds you.

All environment variables are listed in the [Configuration reference](#configuration-reference).

---

### Method 2 — Clone and Run (full control)

Clone the repo and bind-mount source directly. Edit any file and changes take effect immediately.

**1. Clone**

```bash
git clone https://github.com/samschultzponsys/Spazcat-STODO.git
cd Spazcat-STODO
mkdir -p data
```

**2. Create `compose.yaml`** (same as above but with `./app:/app` volume and `python:3.12-slim` image)

```yaml
services:
  stodo:
    image: python:3.12-slim
    container_name: stodo
    restart: unless-stopped
    working_dir: /app
    command: /bin/sh /app/start.sh
    environment:
      DB_PATH: /data/stodo.db
      INGEST_SECRET: yoursecret
      # TIMEZONE: America/Chicago
    volumes:
      - ./app:/app
      - ./data:/data
    ports:
      - "8234:5000"
```

**3. Start**

```bash
docker compose up -d
```

First run installs Python dependencies (~20 seconds). Subsequent starts are instant.

---

## Directory Layout

```
Spazcat-STODO/
├── .github/
│   ├── workflows/docker.yml   ← builds images, tags and publishes releases
│   └── backfill-tags.txt      ← commits for backdated release tags
├── Dockerfile
├── compose.yaml
├── README.md
├── scripts/
│   └── bump-version.sh    ← start a new major / point release
├── app/
│   ├── VERSION            ← current version (MAJOR.MINOR)
│   ├── CHANGELOG.md       ← release notes, shown in the app
│   ├── app.py
│   ├── requirements.txt
│   ├── start.sh
│   └── static/
│       ├── index.html
│       ├── login.html
│       └── fonts/
│           ├── ethnocentric_rg.otf
│           └── ethnocentric_rg_it.otf
└── data/                  ← SQLite database (auto-created)
```

---

## Accessing STODO

### On your LAN
```
http://your-server-ip:8234
```
Requests from LAN addresses (`10.*`, `172.*`, `192.168.*`, `127.*`) are always trusted — no auth required regardless of settings.

### From the internet (via reverse proxy)
```
https://stodo.yourdomain.com/?token=yourtoken   ← token mode
https://stodo.yourdomain.com/                   ← login mode (redirects to /login)
```

### Wallboard mode
Open full-screen in any browser. Items update every 5 seconds and settings changes show up within about 30 seconds. On Android use Chrome → Add to Home Screen for kiosk-style display. For a wallboard outside your LAN, use a token URL so it never needs a login.

---

## Reverse Proxy (Nginx Proxy Manager)

- **Forward hostname:** `stodo` (or your container name)
- **Forward port:** `5000`
- **SSL:** enable with your certificate

STODO reads `X-Forwarded-For` automatically so LAN bypass works correctly through NPM.

---

## Authentication

Auth is configured entirely from the UI settings panel (⚙ → Authentication). No restart needed.

| Mode | Behavior |
|---|---|
| **None** | Fully open. Security banner shown until dismissed or auth configured. |
| **Token** | WAN requires `?token=yourtoken` in the URL. LAN bypasses. Wallboard-friendly. |
| **Login** | WAN redirects to `/login`. Username/password required. Session cookie lasts 7 days. |
| **Both** | WAN accepts either a valid token URL OR a login session. Best for mixed use (wallboards use token, humans use login). |

**LAN is always trusted** regardless of auth mode. From outside, API calls without valid auth get `401`/`403` instead of a redirect.

Changing the auth mode or the token **signs everyone out**.

### Managing users (Login / Both modes)
Go to ⚙ Settings → Authentication → add a username and a password (4+ characters) → ADD. Passwords are bcrypt hashed. Delete users with ✕. Sessions are stored in the database, so they survive restarts and work across all gunicorn workers.

### Token
Set the token in ⚙ Settings → Authentication. The field is never pre-filled; a status line shows whether one is set, and leaving it blank keeps the current one.

If `TOKEN` is set in `compose.yaml` it always wins over the UI token. This is useful for scripting or if you prefer secrets in compose rather than the DB.

---

## Email Ingest *(optional)*

The **subject line** of emails sent to your configured mailbox becomes a new list item.

| Provider | IMAP Host | Port |
|---|---|---|
| Gmail | `imap.gmail.com` | 993 |
| Purelymail | `imap.purelymail.com` | 993 |
| Fastmail | `imap.fastmail.com` | 993 |

> **Gmail users:** Use an [App Password](https://myaccount.google.com/apppasswords) — not your real password.

Set `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`, `IMAP_PORT`, `IMAP_INTERVAL` in your compose and restart. STODO checks the inbox every `IMAP_INTERVAL` seconds (default 30), only picks up **unread** mail, and marks each message read once it's on the board. Use a dedicated mailbox.

---

## SMS Ingest via Android SMS Gateway *(optional)*

Uses [android-sms-gateway](https://github.com/capcom6/android-sms-gateway) — free, open source, no carrier registration required.

**Requirements:** Android phone (5.0+), active SMS SIM, publicly accessible STODO URL with SSL.

**Setup:**
1. Install the APK from the releases page
2. Toggle **Cloud server** on, note Username and Password
3. Enable **Start on boot**
4. Register the webhook:

```bash
curl -X POST https://api.sms-gate.app/3rdparty/v1/webhooks \
  -u YOUR_USERNAME:YOUR_PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://stodo.yourdomain.com/ingest/android?secret=yoursecret",
    "event": "sms:received"
  }'
```

Text anything to the phone number → message appears on the board within seconds.

**Changing numbers:** STODO doesn't store or care about the number. Get a new SIM, re-register the webhook with new credentials, done.

**Recommended plans for a dedicated gateway phone:**

| Plan | Cost | SMS |
|---|---|---|
| Red Pocket ATT (eBay) | $5/mo | Unlimited |
| Red Pocket TMO (eBay) | $5/mo | Unlimited |
| Infimobile annual | ~$4.50/mo | 2500/mo |

> TextNow and VoIP services do **not** work — real carrier SIM required.

### Twilio
Point your Twilio number's incoming-message webhook at `https://stodo.yourdomain.com/ingest/sms?secret=yoursecret` (HTTP POST). The message body becomes an item.

---

## Scheduled Tasks

Click 🗓 in the add row to schedule a task. Pending schedules appear in the **Upcoming** section under the board (✏️ to edit, ✕ to delete). When a schedule's heads-up window opens, it puts an item on the board, tagged `Scheduled`.

**One-time:** Pick a date and optional time. Fires once. A date that has already passed fires right away.

**Recurring — Weekly:** Pick days of the week + optional time + interval (every N weeks).

**Recurring — Monthly:** Pick dates (1–31) from the grid + interval (every N months). Dates that don't exist in shorter months fall on the last day of the month.

**Heads-up:** The item appears N days before it's due in a light shade, then turns solid on the day. Set per task; the default is in ⚙ Settings → Scheduling.

**Color:** Pick a color per task, or use the defaults (purple for one-time, teal for recurring — both changeable in ⚙ Settings → Colors). Changing a task's color also recolors its item already on the board.

**Auto-remove:** Number of days after it fires before the item is removed. Blank or 0 = remove it yourself. Recurring tasks schedule their next occurrence as soon as one fires.

**Convert an existing item:** ⚙ on any item → **Schedule This Task**.

**Scheduled Tasks overview:** 🗓 in the header opens every pending schedule (edit / delete) and every board item that came from a schedule (remove). Editing a finished one-time task re-activates it.

---

## Tags

Each item can have multiple tags. Click `+` on any item row to open the tag popover:
- Click a tag to toggle it on or off the item
- Type a new tag name and press Enter or **Add** to create it
- Tags are shared across all items; the most-used show first, the rest behind **+N more**
- Tags display as gray pills on the item row
- The search bar matches tag names

---

## Per-item Color

Click ⚙ on any item → **Item Color**. Choose from the palette or use the color wheel. Items get a color wash background + colored left border (same style as IPAM). Click the strikethrough swatch to remove the color.

---

## Global Settings

Click ⚙ in the header to open the settings panel:

- **Presets** — Dark Purple, Light, Dark Teal, Dark Red, Midnight (fills in the colors; press Save to apply)
- **Branding** — header title and browser tab title
- **Colors** — accent, background, surface, title text, body text, one-time color, recurring color
- **Scheduling** — default heads-up days
- **Authentication** — auth mode, token, user management
- **Updates** — update checks on/off, repository to watch, GitHub token for private repos, and a **Check for updates** button that tests them

All settings are saved server-side in SQLite and apply to every screen. Dark/light mode and font size are per device. The branding and color environment variables only seed the first start; after that, Settings is the source of truth. Back up your settings (secrets excluded) from `GET /api/config/export`.

---

## Versions, Changelog & Updates

STODO uses `MAJOR.MINOR` versions:

| Bump | Example | When |
|---|---|---|
| **Major** | `v2.5` → `v3.0` | Big overhauls, breaking changes, anything that needs a compose change |
| **Point** | `v2.5` → `v2.6` | Features, fixes and polish that drop straight in |

The running version is shown in a bubble next to the header title. **Click it** to open the changelog. When a newer release is published on GitHub, a **green light flashes** on the bubble and the changelog shows what's new, with update instructions.

STODO checks GitHub's releases API at most every 6 hours (the result is cached in the database), plus whenever you press **Check now** in the changelog.

### Private repos / private containers

Update checks call the GitHub API, which needs a token if the repo is private:

1. GitHub → Settings → Developer settings → **Fine-grained tokens** → *Generate new token*
2. **Repository access:** *Only select repositories* → `Spazcat-STODO` (or your fork)
3. **Permissions:** Repository → **Contents: Read-only** (Metadata: Read-only is added automatically)
4. Paste it into ⚙ Settings → Updates → **GitHub token**, or set `GITHUB_TOKEN` in compose
5. Press **Check for updates** to test it, then **SAVE**

**Check for updates** tests whatever is in the form, even before you save, and tells you step by step:
- whether GitHub accepted the token, and when it expires
- whether it can read the repository (and whether that repo is private)
- whether it can read releases (if not, the token is missing *Contents: Read-only*)
- the latest release, and whether you're up to date

When it tests your saved settings, it also refreshes the version bubble.

The token is stored server-side and never sent to the browser or included in settings exports. Leave the field blank to keep the current token; use **Remove** to clear it.

> This token is only for *checking* for updates. To *pull* a private image, `docker login ghcr.io` needs a token with `read:packages`. At the time of writing GHCR only accepts classic personal access tokens for that, not fine-grained ones.

Point **Repository** at your fork if you run your own builds.

### Pinning a version

Every release has its own image, so you can pin instead of tracking `latest`:

```yaml
image: ghcr.io/samschultzponsys/spazcat-stodo:v2.5   # exact release
image: ghcr.io/samschultzponsys/spazcat-stodo:v2     # newest 2.x
image: ghcr.io/samschultzponsys/spazcat-stodo:latest # newest build of main
```

### Cutting a release (maintainers)

```bash
scripts/bump-version.sh minor   # or: major
# edit app/CHANGELOG.md — replace the TODO lines
git commit -am "Release v2.6" && git push   # then merge to main
```

On main, CI (`.github/workflows/docker.yml`):

1. Checks `app/VERSION` has a matching, TODO-free entry in `app/CHANGELOG.md`
2. Tags the commit `vX.Y`
3. Builds and pushes `:vX.Y` and `:vX` images, stamped with the version
4. Publishes a GitHub Release using that changelog entry as the notes

Every push to main also checks that each tagged version in the changelog has an image and a release, and builds whatever is missing. Older releases are backfilled the same way: `.github/backfill-tags.txt` lists the commit for each backdated version, and CI creates those tags (dated to the original commit) if they don't exist yet.

GitHub won't let the Actions token create a tag on a commit whose workflow file isn't on any current branch or tag (that's the case for `v1.1` and `v1.2`). CI skips those with a warning. Push them once from your own clone, then re-run the workflow from the Actions tab:

```bash
git fetch origin
GIT_COMMITTER_DATE="$(git show -s --format=%cI 8f8626b)" git tag -a v1.1 -m "STODO v1.1" 8f8626b
GIT_COMMITTER_DATE="$(git show -s --format=%cI b6d42f6)" git tag -a v1.2 -m "STODO v1.2" b6d42f6
git push origin v1.1 v1.2
```

To rebuild every release image, run the workflow manually with **rebuild** ticked.

---

## API

`/api/*` endpoints follow the auth settings: from outside your LAN, add `?token=yourtoken` or send the login session cookie. `/ingest/*` endpoints only check `?secret=` (`INGEST_SECRET`).

```
GET    /api/items                    → list items (with tags)
POST   /api/items                    → add item  { "text": "..." }
PUT    /api/items/:id                → update item { text?, item_color?, item_type?, color_key? }
DELETE /api/items/:id                → delete item
POST   /api/items/reorder            → reorder [{id, pos}, ...]
PUT    /api/items/:id/tags           → set tags ["tag1", "tag2"]
GET    /api/tags                     → list tags with usage_count, most used first
DELETE /api/tags/:id                 → delete a tag everywhere
GET    /api/scheduled                → list scheduled tasks (with next_fire_computed)
POST   /api/scheduled                → create scheduled task
PUT    /api/scheduled/:id            → update scheduled task
DELETE /api/scheduled/:id            → delete scheduled task
GET    /api/config                   → get settings (secrets removed)
PUT    /api/config                   → update settings
GET    /api/config/export            → settings backup (secrets removed)
GET    /api/version                  → running version, latest release, changelog (?refresh=1 to re-check)
POST   /api/version/check            → test repo/token { repo?, token? } without saving them
GET    /api/users                    → list users
POST   /api/users                    → create user { username, password }
DELETE /api/users/:id                → delete user
POST   /api/login                    → login { username, password } → sets session cookie
POST   /api/logout                   → logout
GET    /api/auth-status              → auth mode + title (public, used by the login page)

POST   /ingest/text?secret=...       → raw HTTP push { "text": "..." }
POST   /ingest/android?secret=...    → android-sms-gateway webhook
POST   /ingest/sms?secret=...        → Twilio webhook (form field Body)
```

### HTTP push example

```bash
curl -X POST "https://stodo.yourdomain.com/ingest/text?secret=yoursecret" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Pick up milk"}'
```

---

## Custom Font

The header title and headings use **Ethnocentric**, which ships in `app/static/fonts/`. If it can't load, STODO falls back to **Orbitron** from Google Fonts.

To use your own display font, name it `ethnocentric_rg.otf` (and optionally `ethnocentric_rg_it.otf` for italic) and either:
- **Pre-built image:** mount a folder over the fonts directory, e.g. `./fonts:/app/static/fonts`
- **Clone method:** replace the files in `app/static/fonts/`

Mounting a folder replaces the bundled fonts, so if it doesn't contain `ethnocentric_rg.otf` you'll get Orbitron.

---

## Updating

When the version bubble flashes green, a new release is out — click it to see what changed.

**Pre-built image:**
```bash
docker compose pull && docker compose up -d
```
(If you pinned a version like `:v2.5`, change the tag first.)

**Clone method:** `git pull`, then:
- `index.html` changes → browser refresh
- `app.py` changes → `docker compose restart stodo`
- `compose.yaml` changes → `docker compose up -d`

---

## Configuration reference

All optional except where noted. Everything else lives in ⚙ Settings.

| Variable | Default | What it does |
|---|---|---|
| `DB_PATH` | `/data/stodo.db` | SQLite database location |
| `TIMEZONE` | `America/Chicago` | Timezone for scheduled tasks (IANA name) |
| `TOKEN` | — | Access token; overrides the one set in Settings |
| `INGEST_SECRET` | — | Required `?secret=` for `/ingest/*`. **Unset = ingest open to anyone** |
| `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASS` | — / `993` / — / — | Email ingest mailbox |
| `IMAP_INTERVAL` | `30` | Seconds between inbox checks |
| `APP_TITLE` / `APP_SUBTITLE` | `SPAZCAT TO DO` / `STODO` | Header and tab title on first start |
| `ACCENT_COLOR`, `BG_COLOR`, `SURFACE_COLOR`, `TITLE_COLOR`, `TEXT_COLOR` | dark purple theme | Colors on first start |
| `GITHUB_TOKEN` | — | Token for update checks on a private repo; overrides Settings |
| `UPDATE_REPO` | `samschultzponsys/Spazcat-STODO` | Repo whose releases are checked; overrides Settings |
| `UPDATE_CHECK` | on | `"false"` turns update checks off; overrides Settings |
| `APP_VERSION` / `APP_COMMIT` | set by the image | Version shown in the app; you don't need to set these |

---

## Security Notes

- `TOKEN` and `INGEST_SECRET` in `compose.yaml` take priority over UI settings
- The update-check `GITHUB_TOKEN` only needs read-only *Contents* access to one repo — don't reuse a broader token
- Never commit `compose.yaml` with credentials to a public repo
- User passwords are bcrypt hashed — never stored in plaintext
- Sessions use secure random tokens, 7-day TTL, stored in the database; changing auth settings ends all sessions
- LAN is always trusted regardless of auth mode
- Tokens (`TOKEN`, `GITHUB_TOKEN`) are never sent to the browser or included in settings exports
- Set `INGEST_SECRET` if STODO is reachable from the internet — otherwise anyone can add items via `/ingest/*`
- The IMAP poller and scheduler use a lock file in `/data` so only one gunicorn worker runs them

---

## License

MIT — do whatever you want with it.
