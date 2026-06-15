# SpazCat TODO (STODO)

A self-hosted, real-time todo wallboard. Add items from a browser, email, or SMS. Designed to live on a screen — a tablet on the wall, a monitor at your desk, a phone in the kitchen. No login required for display. No kanban, no projects, no friction.

Friction is the number one goal in this project, I needed something I could access quickly yet securely enough where I would be comfortable exposing this to the global internet. Sure there are apps, sure there are kanban solutions but most require login, have too many steps or too many flows.

![Dark mode wallboard](https://img.shields.io/badge/theme-dark%20%2F%20light-5f249f?style=flat-square)
![Docker](https://img.shields.io/badge/docker-no%20build%20required-0db7ed?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## Features

- **Live updates** — board polls every 5 seconds, no refresh needed
- **Add items** — type in the browser, send an email, or send an SMS
- **Delete items** — tap ✕ when done
- **Reorder** — drag and drop on desktop and mobile
- **Dark / light mode** — toggle per device, preference saved locally
- **Token auth** — LAN access is always open, WAN requires a token in the URL
- **Fully configurable** — branding, colors, credentials all via environment variables
- **No Dockerfile** — uses stock `python:3.12-slim`, bind mounts for all files
- **Custom font support** — drop your own `.otf`/`.ttf` in `app/static/fonts/`

---

## Quick Start

### 1. Clone or download

```bash
git clone https://github.com/youruser/stodo.git
cd stodo
```

### 2. Create the data directory

```bash
mkdir -p data
```

### 3. Configure `compose.yaml`

At minimum set your `TOKEN` and `INGEST_SECRET`. See [Configuration](#configuration) below.

### 4. Start

```bash
docker compose up -d
```

First run installs Python dependencies (~20 seconds). Subsequent starts are instant.

---

## Directory Layout

```
stodo/
├── compose.yaml
├── app/
│   ├── app.py
│   ├── requirements.txt
│   ├── start.sh
│   └── static/
│       ├── index.html
│       └── fonts/
│           └── (optional: place custom .otf/.ttf files here)
└── data/                  ← SQLite database (auto-created)
```

---

## Configuration

All configuration is done via environment variables in `compose.yaml`. No values are hardcoded in the application.

```yaml
services:
  stodo:
    image: python:3.12-slim
    container_name: stodo
    restart: unless-stopped
    working_dir: /app
    command: /bin/sh /app/start.sh
    environment:

      # ── Database ───────────────────────────────────────────────
      DB_PATH: /data/stodo.db

      # ── Access Control ─────────────────────────────────────────
      # TOKEN: required in the URL for WAN access (?token=yourtoken)
      # Requests from LAN (10.x, 192.168.x, 172.x) always bypass this.
      # Leave blank to disable token auth entirely.
      TOKEN: yourtoken

      # INGEST_SECRET: appended to all webhook/ingest URLs as ?secret=
      # Protects /ingest/android and /ingest/text from unauthorized POSTs.
      # Leave blank to disable.
      INGEST_SECRET: yoursecret

      # ── Branding ───────────────────────────────────────────────
      APP_TITLE:    "MY TODO"        # displayed in the header
      APP_SUBTITLE: STODO            # browser tab title

      # ── Colors ─────────────────────────────────────────────────
      ACCENT_COLOR:  "#5f249f"       # buttons, highlights, live dot, title outline
      BG_COLOR:      "#0d0d0d"       # page background (dark mode)
      SURFACE_COLOR: "#161616"       # card / input background (dark mode)
      TITLE_COLOR:   "#ffffff"       # header title text color
      TEXT_COLOR:    "#f0f0f0"       # list item text color

      # ── Email Ingest (optional) ────────────────────────────────
      # See: Email Ingest section below
      # IMAP_HOST:     imap.yourprovider.com
      # IMAP_PORT:     993
      # IMAP_USER:     stodo@yourdomain.com
      # IMAP_PASS:     your-app-password
      # IMAP_INTERVAL: 30

    volumes:
      - ./app:/app
      - ./data:/data
    ports:
      - "8234:5000"
```

---

## Accessing STODO

### On your LAN
```
http://your-server-ip:8234
```
No token required. Works immediately.

### From the internet (via reverse proxy)
```
https://stodo.yourdomain.com/?token=yourtoken
```
Bookmark this URL on every device. The token persists in the URL — you never need to type it again.

### Wallboard mode
Open the URL full-screen in any browser. The board updates automatically every 5 seconds. On Android, use Chrome → Add to Home Screen for a full-screen kiosk-style experience.

---

## Reverse Proxy (Nginx Proxy Manager)

Add a proxy host:
- **Forward hostname:** `stodo` (or your container name)
- **Forward port:** `5000`
- **SSL:** enable with your certificate

STODO reads the `X-Forwarded-For` header automatically, so real client IPs are detected correctly for LAN bypass logic.

---

## Email Ingest *(optional)*

Send an email to your configured mailbox — the **subject line** becomes a new list item.

### Setup

1. Create a dedicated mailbox for STODO (recommended: a throwaway or subdomain address)
2. Get your IMAP credentials. Common providers:

   | Provider | IMAP Host | Port |
   |---|---|---|
   | Gmail | `imap.gmail.com` | 993 |
   | Purelymail | `imap.purelymail.com` | 993 |
   | Fastmail | `imap.fastmail.com` | 993 |
   | Any standard IMAP | your provider's host | 993 |

   > **Gmail users:** Enable 2FA and use an [App Password](https://myaccount.google.com/apppasswords) — do not use your real password.

3. Uncomment and fill in the IMAP variables in `compose.yaml`:

```yaml
IMAP_HOST:     imap.gmail.com
IMAP_PORT:     993
IMAP_USER:     stodo@gmail.com
IMAP_PASS:     xxxx-xxxx-xxxx-xxxx
IMAP_INTERVAL: 30
```

4. Restart: `docker compose restart stodo`

### Usage

Email `stodo@yourdomain.com` with whatever you want as the **subject**. It appears on the board within `IMAP_INTERVAL` seconds. The body of the email is ignored.

---

## SMS Ingest via Android SMS Gateway *(optional)*

Receive SMS messages on an Android phone and forward them to STODO as list items. Uses [android-sms-gateway](https://github.com/capcom6/android-sms-gateway) — free, open source, no carrier registration required.

### What you need

- An Android phone (Android 5.0+) with an active SMS-capable SIM
- The phone stays powered on (plugged in recommended)
- A publicly accessible STODO URL (via reverse proxy with a domain + SSL)

### Setup

**1. Install the app**

Download the latest release APK from:
```
https://github.com/capcom6/android-sms-gateway/releases
```

Install it on your Android phone (allow unknown sources in settings).

**2. Enable Cloud mode**

Open the app → toggle **Cloud server** on. Note the **Username** and **Password** shown on the home screen — you'll need these.

Enable **Start on boot** so it survives reboots.

**3. Grant SMS permissions**

When prompted, grant the app permission to read SMS messages.

**4. Register the webhook**

Run this from any machine (substituting your cloud credentials and domain):

```bash
curl -X POST https://api.sms-gate.app/3rdparty/v1/webhooks \
  -u YOUR_USERNAME:YOUR_PASSWORD \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://stodo.yourdomain.com/ingest/android?secret=yoursecret",
    "event": "sms:received"
  }'
```

**5. Test**

Text anything to the phone's number. The message body appears on the board within seconds.

### Changing the phone number

STODO doesn't store or care about the phone number — it just receives webhook POSTs. To change numbers:

1. Get a new SIM / phone number
2. Install the SMS gateway app on the new device (or swap the SIM)
3. Re-run the webhook registration curl command above with the new device's credentials
4. Done — no changes needed in STODO

### Recommended SIM plans for a dedicated gateway phone

Any prepaid SMS-capable plan works. The phone can live on WiFi — it only needs the SIM for SMS reception.

| Plan | Cost | SMS | Notes |
|---|---|---|---|
| Red Pocket (eBay, ATT) | $5/mo | Unlimited | Reliable, widely available |
| Red Pocket (eBay, TMO) | $5/mo | Unlimited | T-Mobile network |
| Helium Mobile | $5/mo | Unlimited | T-Mobile network |
| Infimobile | ~$4.50/mo (annual) | 2500/mo | Good for low volume |

> **Note:** TextNow and other VoIP-based services do **not** work — you need a real carrier SIM for SMS interception.

---

## API

All endpoints respect `TOKEN` and `INGEST_SECRET` when configured.

```
GET    /api/items                    → list all items
POST   /api/items                    → add item  { "text": "..." }
DELETE /api/items/:id                → delete item
POST   /api/items/reorder            → reorder   [{id, pos}, ...]
GET    /api/config                   → UI configuration (colors, title, etc.)

POST   /ingest/android?secret=...   → android-sms-gateway webhook
POST   /ingest/text?secret=...      → raw HTTP push { "text": "..." }
POST   /ingest/sms?secret=...       → Twilio webhook (if using Twilio)
```

### HTTP push example

Add items from scripts, Home Assistant, Node-RED, curl, anything:

```bash
curl -X POST "https://stodo.yourdomain.com/ingest/text?secret=yoursecret" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Pick up milk"}'
```

---

## Custom Fonts

Drop `.otf` or `.ttf` files into `app/static/fonts/` and reference them in `index.html`:

```css
@font-face {
  font-family: 'MyFont';
  src: url('/fonts/myfont.otf') format('opentype');
}
```

Then update `--font-disp` in the CSS variables to use your font.

---

## Updating

Since all source is bind-mounted, most changes take effect immediately:

- **UI changes** (`index.html`) — refresh the browser
- **Backend changes** (`app.py`) — `docker compose restart stodo`
- **Config/env changes** (`compose.yaml`) — `docker compose up -d`

---

## Security Notes

- `TOKEN` and `INGEST_SECRET` are set in `compose.yaml` only — never in the application code
- Do not commit `compose.yaml` with real credentials to a public repository
- Use a `.gitignore` to exclude it, or use a `compose.override.yaml` for secrets
- The IMAP poller uses a lock file to prevent duplicate polling across gunicorn workers
- All ingest endpoints validate the secret before processing

---

## License

MIT — do whatever you want with it.
