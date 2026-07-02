# SpazCat TODO (STODO)

A self-hosted, real-time todo wallboard. Add items from a browser, email, or SMS. Designed to live on a screen — a tablet on the wall, a monitor at your desk, a phone in the kitchen. No login required for display. No kanban, no projects, no friction.

Friction is the number one goal in this project — I needed something I could access quickly yet securely enough to be comfortable exposing to the global internet. Sure there are apps, sure there are kanban solutions, but most require login, have too many steps, or too many flows.

![Dark mode wallboard](https://img.shields.io/badge/theme-dark%20%2F%20light-5f249f?style=flat-square)
![Docker](https://img.shields.io/badge/docker-ghcr.io-0db7ed?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## Features

- **Live updates** — board polls every 5 seconds, no refresh needed
- **Add items** — type in the browser, send an email, or send an SMS
- **Delete with confirmation** — two-tap ✕ prevents accidental deletes
- **Inline edit** — pencil icon per item for quick edits
- **Reorder** — drag and drop on desktop and mobile touch
- **Tags** — add multiple tags per item, auto-complete from existing tags, fully searchable
- **Per-item color** — color wheel + palette per item with IPAM-style color wash
- **Scheduled tasks** — one-time or recurring, with heads-up preview and auto-remove
- **Dark / light mode** — toggle per device
- **Font size control** — A− / A+ / A↺ in the header, scales everything
- **Live search** — collapsible search bar, filters by text, tags, and dates
- **UI-configurable settings** — colors, branding, auth, scheduling defaults all in the settings panel
- **Authentication** — none / token / login / both, configurable from the UI
- **Multi-user login** — add/delete users from the settings panel, bcrypt hashed passwords
- **Security banner** — warns when no auth is configured, dismissible
- **Email ingest** — IMAP polling, subject line becomes a list item
- **SMS ingest** — Android SMS Gateway, any text to the number hits the board
- **HTTP push** — POST to `/ingest/text` from scripts, Home Assistant, Node-RED, etc.
- **Iframe friendly** — embeds cleanly in Home Assistant dashboards and kiosk pages
- **Custom font support** — drop your own `.otf`/`.ttf` in `fonts/`

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
mkdir -p stodo/data stodo/fonts
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

      # ── Security (required) ────────────────────────────────────
      # Auth is configured in the UI settings panel.
      # TOKEN and INGEST_SECRET here override UI settings if set.
      # TOKEN: yourtoken          # overrides UI token setting
      INGEST_SECRET: yoursecret   # protects /ingest/* endpoints

      # ── Branding overrides (optional — UI settings take priority) ──
      # APP_TITLE:    "MY TODO"
      # APP_SUBTITLE: STODO

      # ── Color overrides (optional — UI settings take priority) ─
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

    volumes:
      - ./data:/data
      - ./fonts:/app/static/fonts    # optional custom fonts
    ports:
      - "8234:5000"
```

**3. Start**

```bash
docker compose up -d
```

**4. Configure auth** — open the UI, click ⚙ → Authentication section. On first launch a security banner will remind you.

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
├── Dockerfile
├── compose.example.yaml
├── README.md
├── app/
│   ├── app.py
│   ├── requirements.txt
│   ├── start.sh
│   └── static/
│       ├── index.html
│       ├── login.html
│       └── fonts/
│           └── (optional: drop .otf/.ttf files here)
└── data/                  ← SQLite database (auto-created)
```

---

## Accessing STODO

### On your LAN
```
http://your-server-ip:8234
```
LAN is always trusted — no auth required regardless of settings.

### From the internet (via reverse proxy)
```
https://stodo.yourdomain.com/?token=yourtoken   ← token mode
https://stodo.yourdomain.com/                   ← login mode (redirects to /login)
```

### Wallboard mode
Open full-screen in any browser. Updates automatically every 5 seconds. On Android use Chrome → Add to Home Screen for kiosk-style display.

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

**LAN is always trusted** regardless of auth mode.

### Managing users (Login / Both modes)
Go to ⚙ Settings → Authentication → add username + password → ADD. Passwords are bcrypt hashed. Delete users with ✕.

### Token via environment variable
If `TOKEN` is set in `compose.yaml` it takes priority over the UI token setting. This is useful for scripting or if you prefer secrets in compose rather than the DB.

---

## Email Ingest *(optional)*

The **subject line** of emails sent to your configured mailbox becomes a new list item.

| Provider | IMAP Host | Port |
|---|---|---|
| Gmail | `imap.gmail.com` | 993 |
| Purelymail | `imap.purelymail.com` | 993 |
| Fastmail | `imap.fastmail.com` | 993 |

> **Gmail users:** Use an [App Password](https://myaccount.google.com/apppasswords) — not your real password.

Set `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`, `IMAP_PORT`, `IMAP_INTERVAL` in your compose and restart.

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

---

## Scheduled Tasks

Click 🗓 in the add row to schedule a task. Tasks appear in the **Upcoming** section below the main list and graduate to the main list when their time comes.

**One-time:** Pick a date and optional time. Fires once.

**Recurring — Weekly:** Pick days of the week + optional time + interval (every N weeks).

**Recurring — Monthly:** Pick date numbers (1–31) from the grid + interval (every N months). Dates that don't exist in shorter months are clamped to the last day.

**Heads-up period:** Configurable per task — task appears in the list N days before the fire date in a lighter shade. Goes full color on the actual date.

**Colors:**
- One-time: purple family (heads-up = faint, fired = solid)
- Recurring: teal family (heads-up = faint, fired = solid)

**Auto-remove:** Set a number of days after firing. Blank = manual removal. Recurring tasks reschedule automatically after removal.

**Convert existing item:** Use the ⚙ button on any item → "Schedule This Task" to convert it to a scheduled task.

---

## Tags

Each item can have multiple tags. Click `+` on any item row to open the tag popover:
- Click existing tags to toggle them on/off the item
- Type a new tag name and press Enter or ADD to create it
- Tags are stored globally and suggested across all items
- Tags display as gray pills on the item row
- Search bar filters by tag name

---

## Per-item Color

Click ⚙ on any item → Item Color section. Choose from the palette or use the color wheel. Items get a color wash background + colored left border (same style as IPAM). Click the strikethrough swatch to remove color.

---

## Global Settings

Click ⚙ in the header to open the settings panel:

- **Presets** — Dark Purple, Light, Dark Teal, Dark Red, Midnight
- **Branding** — title and tab subtitle
- **Colors** — accent, background, surface, title text, body text, one-time color, recurring color
- **Scheduling** — default heads-up days
- **Authentication** — auth mode, token, user management

All settings saved server-side to SQLite.

---

## API

All endpoints respect auth settings.

```
GET    /api/items                    → list all items (includes tags)
POST   /api/items                    → add item  { "text": "..." }
PUT    /api/items/:id                → update item (text, item_color, color_key)
DELETE /api/items/:id                → delete item
POST   /api/items/reorder            → reorder [{id, pos}, ...]
PUT    /api/items/:id/tags           → set tags ["tag1", "tag2"]
GET    /api/tags                     → list all tags
DELETE /api/tags/:id                 → delete tag
GET    /api/scheduled                → list scheduled tasks
POST   /api/scheduled                → create scheduled task
PUT    /api/scheduled/:id            → update scheduled task
DELETE /api/scheduled/:id            → delete scheduled task
GET    /api/config                   → get settings
PUT    /api/config                   → update settings
GET    /api/users                    → list users
POST   /api/users                    → create user { username, password }
DELETE /api/users/:id                → delete user
POST   /api/login                    → login { username, password }
POST   /api/logout                   → logout

POST   /ingest/android?secret=...   → android-sms-gateway webhook
POST   /ingest/text?secret=...      → raw HTTP push { "text": "..." }
POST   /ingest/sms?secret=...       → Twilio webhook
```

### HTTP push example

```bash
curl -X POST "https://stodo.yourdomain.com/ingest/text?secret=yoursecret" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Pick up milk"}'
```

---

## Custom Fonts

Drop `.otf` or `.ttf` files into `fonts/` (pre-built image) or `app/static/fonts/` (clone method). The default fallback is Orbitron from Google Fonts. Ethnocentric is used if present (not included — commercial font).

---

## Updating

**Pre-built image:**
```bash
docker compose pull && docker compose up -d
```

**Clone method:**
- `index.html` changes → browser refresh
- `app.py` changes → `docker compose restart stodo`
- `compose.yaml` changes → `docker compose up -d`

---

## Security Notes

- `TOKEN` and `INGEST_SECRET` in `compose.yaml` take priority over UI settings
- Never commit `compose.yaml` with credentials to a public repo
- User passwords are bcrypt hashed — never stored in plaintext
- Sessions use secure random tokens, 7-day TTL
- LAN is always trusted regardless of auth mode
- The IMAP poller uses a lock file to prevent duplicate polling across gunicorn workers

---

## License

MIT — do whatever you want with it.
