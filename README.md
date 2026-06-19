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
- **Custom font support** — drop your own `.otf`/`.ttf` in `app/static/fonts/`

> **Note:** This has been coded with assistance from AI, I am not a dev I am alright with frontend coding and a tiny bit of backend but I did have a real dev look over this and they did not see any glaring concerns, but by all means fork it and fix it. For this project I did NOT want a traditional local auth or embedded auth but would consider an integration to add one with env flags, OIDC would be hot on my list but at that point you might be better off with another project, I also use KanBN and really like it for more traditional project management here: https://github.com/kanbn/kan

---

## Screenshot! This is totally customizable.
<img width="1651" height="750" alt="image" src="https://github.com/user-attachments/assets/4f396fb1-b541-4a2c-b71d-9acfd031fbae" />

Mobile Dark and Light Mode Example, embedded into Home Assistant!:
<img width="1080" height="2520" alt="Screenshot_20260619_140629_Home Assistant (1)" src="https://github.com/user-attachments/assets/ab9289b4-48af-4b60-9d1a-16844ca91a0c" />
<img width="1080" height="2520" alt="Screenshot_20260619_140629_Home Assistant" src="https://github.com/user-attachments/assets/b5117205-f9ef-4788-b504-622040d1a7d2" />



---

## Installation

There are two ways to run STODO — pick whichever suits you.

---

### Method 1 — Pre-built Container (easiest)

No cloning required. Pull the image directly from GitHub Container Registry and run it.

**1. Create your directories**

```bash
mkdir -p stodo/data stodo/fonts
cd stodo
```

**2. Create a `compose.yaml`**

```yaml
services:
  stodo:
    image: ghcr.io/samschultzponsys/spazcat-stodo:latest
    container_name: stodo
    restart: unless-stopped
    environment:
      DB_PATH: /data/stodo.db

      # ── Access Control ─────────────────────────────────────────
      TOKEN: yourtoken
      INGEST_SECRET: yoursecret

      # ── Branding ───────────────────────────────────────────────
      APP_TITLE:    "MY TODO"
      APP_SUBTITLE: STODO

      # ── Colors ─────────────────────────────────────────────────
      ACCENT_COLOR:  "#5f249f"
      BG_COLOR:      "#0d0d0d"
      SURFACE_COLOR: "#161616"
      TITLE_COLOR:   "#ffffff"
      TEXT_COLOR:    "#f0f0f0"

      # ── Email Ingest (optional) ────────────────────────────────
      # IMAP_HOST:     imap.yourprovider.com
      # IMAP_PORT:     993
      # IMAP_USER:     stodo@yourdomain.com
      # IMAP_PASS:     your-app-password
      # IMAP_INTERVAL: 30

      # ── SMS Ingest (optional) ──────────────────────────────────
      # No config needed here — SMS ingest is always active.
      # Install android-sms-gateway on an Android phone, then
      # register a webhook pointing to:
      #   https://yourdomain.com/ingest/android?secret=yoursecret
      # See README for full setup instructions.

    volumes:
      - ./data:/data                   # database
      - ./fonts:/app/static/fonts      # optional: drop custom .otf/.ttf fonts here
    ports:
      - "8234:5000"
```

**3. Start**

```bash
docker compose up -d
```

> **Note:** When using the pre-built image, UI and backend changes require pulling a new image (`docker compose pull && docker compose up -d`). For active customization, use Method 2.

---

### Method 2 — Clone and Run (full control)

Clone the repo and bind-mount the source directly. Edit any file and changes take effect immediately — no rebuild needed.

**1. Clone**

```bash
git clone https://github.com/samschultzponsys/Spazcat-STODO.git
cd Spazcat-STODO
```

**2. Create the data directory**

```bash
mkdir -p data
```

**3. Create a `compose.yaml`**

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

      # ── Access Control ─────────────────────────────────────────
      TOKEN: yourtoken
      INGEST_SECRET: yoursecret

      # ── Branding ───────────────────────────────────────────────
      APP_TITLE:    "MY TODO"
      APP_SUBTITLE: STODO

      # ── Colors ─────────────────────────────────────────────────
      ACCENT_COLOR:  "#5f249f"
      BG_COLOR:      "#0d0d0d"
      SURFACE_COLOR: "#161616"
      TITLE_COLOR:   "#ffffff"
      TEXT_COLOR:    "#f0f0f0"

      # ── Email Ingest (optional) ────────────────────────────────
      # IMAP_HOST:     imap.yourprovider.com
      # IMAP_PORT:     993
      # IMAP_USER:     stodo@yourdomain.com
      # IMAP_PASS:     your-app-password
      # IMAP_INTERVAL: 30

      # ── SMS Ingest (optional) ──────────────────────────────────
      # No config needed here — SMS ingest is always active.
      # Install android-sms-gateway on an Android phone, then
      # register a webhook pointing to:
      #   https://yourdomain.com/ingest/android?secret=yoursecret
      # See README for full setup instructions.

    volumes:
      - ./app:/app
      - ./data:/data
    ports:
      - "8234:5000"
```

**4. Start**

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
│       └── fonts/
│           └── (optional: place custom .otf/.ttf files here)
└── data/                  ← SQLite database (auto-created)
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
2. Get your IMAP credentials. Please use app passwords! Common providers:

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
| Infimobile | ~$4.50/mo (annual) | 2500/mo | Good for low volume |

> **Note:** These prices are as of time of posting with some promotions so keep that in mind.

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

Drop `.otf` or `.ttf` files into `app/static/fonts/` (or `fonts/` if using the pre-built image) and reference them in `index.html`:

```css
@font-face {
  font-family: 'MyFont';
  src: url('/fonts/myfont.otf') format('opentype');
}
```

Then update `--font-disp` in the CSS variables to use your font. The default fallback is Orbitron (loaded from Google Fonts) if no custom font is present.

---

## Updating

**Pre-built image:**
```bash
docker compose pull
docker compose up -d
```

**Clone method** — changes take effect immediately:
- **UI changes** (`index.html`) — refresh the browser
- **Backend changes** (`app.py`) — `docker compose restart stodo`
- **Config/env changes** (`compose.yaml`) — `docker compose up -d`

---

## Security Notes

- `TOKEN` and `INGEST_SECRET` are set in `compose.yaml` only — never in the application code
- Do not commit `compose.yaml` with real credentials to a public repository
- Use a `.gitignore` to exclude it, or keep credentials in a separate env file
- The IMAP poller uses a lock file to prevent duplicate polling across gunicorn workers
- All ingest endpoints validate the secret before processing

---

## License

MIT — do whatever you want with it.
