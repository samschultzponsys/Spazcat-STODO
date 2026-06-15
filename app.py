import os
import sqlite3
import threading
import time
import imaplib
import email
from email.header import decode_header
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app)

# ── Config from env ───────────────────────────────────────────────────────────
DB_PATH        = os.environ.get('DB_PATH', '/data/stodo.db')
TOKEN          = os.environ.get('TOKEN', '')
INGEST_SECRET  = os.environ.get('INGEST_SECRET', '')
APP_TITLE      = os.environ.get('APP_TITLE', 'SPAZCAT TO DO')
APP_SUBTITLE   = os.environ.get('APP_SUBTITLE', 'STODO')
ACCENT_COLOR   = os.environ.get('ACCENT_COLOR', '#5f249f')
BG_COLOR       = os.environ.get('BG_COLOR', '#0d0d0d')
SURFACE_COLOR  = os.environ.get('SURFACE_COLOR', '#161616')
TITLE_COLOR    = os.environ.get('TITLE_COLOR', '#ffffff')
TEXT_COLOR     = os.environ.get('TEXT_COLOR', '#f0f0f0')

IMAP_HOST      = os.environ.get('IMAP_HOST', '')
IMAP_PORT      = int(os.environ.get('IMAP_PORT', '993'))
IMAP_USER      = os.environ.get('IMAP_USER', '')
IMAP_PASS      = os.environ.get('IMAP_PASS', '')
IMAP_INTERVAL  = int(os.environ.get('IMAP_INTERVAL', '30'))

LAN_PREFIXES   = ('10.', '192.168.', '172.', '127.')

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_real_ip():
    # NPM and other reverse proxies forward the real client IP here
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

def is_lan():
    ip = get_real_ip()
    return any(ip.startswith(p) for p in LAN_PREFIXES)

def check_token():
    """Enforce TOKEN for non-LAN requests to the UI/API."""
    if not TOKEN:
        return
    if is_lan():
        return
    if request.args.get('token') == TOKEN:
        return
    abort(403)

def check_ingest():
    """Enforce INGEST_SECRET on ingest endpoints."""
    if not INGEST_SECRET:
        return
    if request.args.get('secret') == INGEST_SECRET:
        return
    abort(403)

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            text    TEXT NOT NULL,
            pos     INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/config')
def api_config():
    check_token()
    return jsonify({
        'title':        APP_TITLE,
        'subtitle':     APP_SUBTITLE,
        'accentColor':  ACCENT_COLOR,
        'bgColor':      BG_COLOR,
        'surfaceColor': SURFACE_COLOR,
        'titleColor':   TITLE_COLOR,
        'textColor':    TEXT_COLOR,
    })

@app.route('/api/items', methods=['GET'])
def list_items():
    check_token()
    conn = get_db()
    rows = conn.execute('SELECT * FROM items ORDER BY pos ASC, id ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/items', methods=['POST'])
def add_item():
    check_token()
    text = (request.json or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
    _add_text(text)
    return jsonify({'ok': True}), 201

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    check_token()
    conn = get_db()
    conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/items/reorder', methods=['POST'])
def reorder_items():
    check_token()
    order = request.json or []
    conn = get_db()
    for entry in order:
        conn.execute('UPDATE items SET pos = ? WHERE id = ?', (entry['pos'], entry['id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── Ingest endpoints ──────────────────────────────────────────────────────────
@app.route('/ingest/sms', methods=['POST'])
def ingest_sms():
    # Twilio format
    check_ingest()
    body = (request.form.get('Body') or '').strip()
    if body:
        _add_text(body)
    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}

@app.route('/ingest/android', methods=['POST'])
def ingest_android():
    check_ingest()
    data = request.json or {}
    event = data.get('event', '')
    if event != 'sms:received':
        return jsonify({'ok': True})
    message = (data.get('payload') or {}).get('message', '').strip()
    if message:
        _add_text(message)
        app.logger.info(f'Android SMS ingest: {message}')
    return jsonify({'ok': True}), 200

@app.route('/ingest/text', methods=['POST'])
def ingest_text():
    check_ingest()
    text = (request.json or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
    _add_text(text)
    return jsonify({'ok': True}), 201

def _add_text(text):
    conn = get_db()
    max_pos = conn.execute('SELECT COALESCE(MAX(pos),0) FROM items').fetchone()[0]
    conn.execute(
        'INSERT INTO items (text, pos, created) VALUES (?, ?, ?)',
        (text, max_pos + 1, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

# ── Frontend ──────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def frontend(path='index.html'):
    # Static assets (fonts, js, css) pass through without token check
    if path and any(path.startswith(p) for p in ('fonts/', 'static/')):
        return send_from_directory(app.static_folder, path)
    check_token()
    return send_from_directory(app.static_folder, 'index.html' if (not path or path == '/') else path)

# ── IMAP poller ───────────────────────────────────────────────────────────────
def _decode_header(h):
    parts = decode_header(h or '')
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            out.append(part)
    return ''.join(out)

def poll_imap():
    if not (IMAP_HOST and IMAP_USER and IMAP_PASS):
        app.logger.info('IMAP not configured — skipping email poller')
        return
    app.logger.info(f'IMAP poller started → {IMAP_USER}@{IMAP_HOST}')
    while True:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select('INBOX')
            _, data = mail.search(None, 'UNSEEN')
            for num in (data[0] or b'').split():
                _, msg_data = mail.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
                subject = _decode_header(msg.get('Subject', '')).strip()
                if subject:
                    _add_text(subject)
                    app.logger.info(f'Email ingest: {subject}')
                mail.store(num, '+FLAGS', '\\Seen')
            mail.logout()
        except Exception as e:
            app.logger.warning(f'IMAP error: {e}')
        time.sleep(IMAP_INTERVAL)

# ── Startup ───────────────────────────────────────────────────────────────────
init_db()

def _try_start_poller():
    lock_file = '/data/.imap_lock'
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        t = threading.Thread(target=poll_imap, daemon=True)
        t.start()
    except FileExistsError:
        pass

_try_start_poller()

if __name__ == '__main__':
    try:
        os.remove('/data/.imap_lock')
    except FileNotFoundError:
        pass
    app.run(host='0.0.0.0', port=5000, debug=False)
