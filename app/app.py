import os
import sqlite3
import threading
import time
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

app = Flask(__name__, static_folder='static')
CORS(app)

@app.after_request
def allow_iframe(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

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
TIMEZONE       = os.environ.get('TIMEZONE', 'America/Chicago')

IMAP_HOST      = os.environ.get('IMAP_HOST', '')
IMAP_PORT      = int(os.environ.get('IMAP_PORT', '993'))
IMAP_USER      = os.environ.get('IMAP_USER', '')
IMAP_PASS      = os.environ.get('IMAP_PASS', '')
IMAP_INTERVAL  = int(os.environ.get('IMAP_INTERVAL', '30'))

LAN_PREFIXES   = ('10.', '192.168.', '172.', '127.')

try:
    TZ = pytz.timezone(TIMEZONE)
except Exception:
    TZ = pytz.utc

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_real_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

def is_lan():
    ip = get_real_ip()
    return any(ip.startswith(p) for p in LAN_PREFIXES)

def check_token():
    if not TOKEN: return
    if is_lan(): return
    if request.args.get('token') == TOKEN: return
    abort(403)

def check_ingest():
    if not INGEST_SECRET: return
    if request.args.get('secret') == INGEST_SECRET: return
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
            created TEXT NOT NULL,
            item_type  TEXT NOT NULL DEFAULT 'normal',
            color_key  TEXT,
            fired_at   TEXT,
            auto_remove_days INTEGER
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scheduled (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            text            TEXT NOT NULL,
            sched_type      TEXT NOT NULL DEFAULT 'onetime',
            fire_at         TEXT,
            recur_days      TEXT,
            recur_time      TEXT,
            heads_up_days   INTEGER NOT NULL DEFAULT 1,
            auto_remove_days INTEGER,
            created         TEXT NOT NULL,
            next_fire       TEXT
        )
    ''')
    # Migrate existing items table if missing new columns
    existing = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    for col, typedef in [
        ('item_type', 'TEXT NOT NULL DEFAULT "normal"'),
        ('color_key', 'TEXT'),
        ('fired_at', 'TEXT'),
        ('auto_remove_days', 'INTEGER'),
    ]:
        if col not in existing:
            conn.execute(f'ALTER TABLE items ADD COLUMN {col} {typedef}')
    conn.commit()
    conn.close()

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_local():
    return datetime.now(TZ)

def parse_local(dt_str):
    """Parse an ISO datetime string as local time."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = TZ.localize(dt)
        return dt
    except Exception:
        return None

def _add_text(text, item_type='normal', color_key=None, auto_remove_days=None):
    conn = get_db()
    max_pos = conn.execute('SELECT COALESCE(MAX(pos),0) FROM items').fetchone()[0]
    conn.execute(
        'INSERT INTO items (text, pos, created, item_type, color_key, fired_at, auto_remove_days) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (text, max_pos + 1, now_local().isoformat(), item_type, color_key, now_local().isoformat(), auto_remove_days)
    )
    conn.commit()
    conn.close()

def calc_next_fire(sched):
    """Calculate next fire datetime for a scheduled item."""
    now = now_local()
    if sched['sched_type'] == 'onetime':
        fire = parse_local(sched['fire_at'])
        return fire if fire and fire > now else None
    else:
        # Recurring — find next occurrence of recur_days at recur_time
        days_map = {'sun':6,'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5}
        recur_days = [d.strip().lower() for d in (sched['recur_days'] or '').split(',') if d.strip()]
        day_nums = [days_map[d] for d in recur_days if d in days_map]
        if not day_nums or not sched['recur_time']:
            return None
        try:
            h, m = map(int, sched['recur_time'].split(':'))
        except Exception:
            return None
        # Find next matching day
        for delta in range(8):
            candidate = now + timedelta(days=delta)
            if candidate.weekday() in day_nums:
                candidate = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                if candidate > now:
                    return candidate
        return None

# ── Scheduler ─────────────────────────────────────────────────────────────────
def run_scheduler_tick():
    """Check scheduled items and fire any that are due or in heads-up window."""
    try:
        now = now_local()
        conn = get_db()
        rows = conn.execute('SELECT * FROM scheduled').fetchall()
        for row in rows:
            sched = dict(row)
            next_fire = parse_local(sched['next_fire']) if sched['next_fire'] else calc_next_fire(sched)
            if not next_fire:
                conn.close()
                continue

            heads_up = sched['heads_up_days'] or 1
            heads_up_start = next_fire - timedelta(days=heads_up)

            # Check if already in main list for this fire time
            existing = conn.execute(
                "SELECT id FROM items WHERE text=? AND item_type IN ('onetime','recurring') AND fired_at>=?",
                (sched['text'], heads_up_start.isoformat())
            ).fetchone()

            if now >= heads_up_start and not existing:
                # Determine color and type
                is_day_of = now >= next_fire
                if sched['sched_type'] == 'onetime':
                    color_key = 'onetime-fired' if is_day_of else 'onetime-headsup'
                else:
                    color_key = 'recurring-fired' if is_day_of else 'recurring-headsup'

                item_type = sched['sched_type']
                max_pos = conn.execute('SELECT COALESCE(MAX(pos),0) FROM items').fetchone()[0]
                conn.execute(
                    'INSERT INTO items (text, pos, created, item_type, color_key, fired_at, auto_remove_days) VALUES (?,?,?,?,?,?,?)',
                    (sched['text'], max_pos+1, now.isoformat(), item_type, color_key,
                     now.isoformat(), sched['auto_remove_days'])
                )

                # For one-time, update next_fire to null after firing
                if sched['sched_type'] == 'onetime' and is_day_of:
                    conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?', (None, sched['id']))
                elif sched['sched_type'] == 'recurring' and is_day_of:
                    # Calculate next recurrence after this one
                    future_now = next_fire + timedelta(minutes=1)
                    # Temporarily patch to calc next
                    import copy
                    sched_copy = copy.copy(sched)
                    next_next = calc_next_fire(sched_copy)
                    conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?',
                                 (next_next.isoformat() if next_next else None, sched['id']))
                else:
                    conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?',
                                 (next_fire.isoformat(), sched['id']))

            # Update color from headsup to fired when day-of arrives
            elif existing and now >= next_fire:
                item = conn.execute('SELECT * FROM items WHERE id=?', (existing[0],)).fetchone()
                if item and 'headsup' in (item['color_key'] or ''):
                    new_color = item['color_key'].replace('headsup', 'fired')
                    conn.execute('UPDATE items SET color_key=? WHERE id=?', (new_color, item['id']))

        # Auto-remove items past their remove date
        all_items = conn.execute(
            "SELECT * FROM items WHERE item_type IN ('onetime','recurring') AND auto_remove_days IS NOT NULL AND fired_at IS NOT NULL"
        ).fetchall()
        for item in all_items:
            fired = parse_local(item['fired_at'])
            if fired and now >= fired + timedelta(days=item['auto_remove_days']):
                conn.execute('DELETE FROM items WHERE id=?', (item['id'],))

        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.warning(f'Scheduler tick error: {e}')

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
        'timezone':     TIMEZONE,
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

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    check_token()
    text = (request.json or {}).get('text', '').strip()
    if not text:
        return jsonify({'error': 'empty'}), 400
    conn = get_db()
    conn.execute('UPDATE items SET text = ? WHERE id = ?', (text, item_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

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

# ── Scheduled items API ───────────────────────────────────────────────────────
@app.route('/api/scheduled', methods=['GET'])
def list_scheduled():
    check_token()
    conn = get_db()
    rows = conn.execute('SELECT * FROM scheduled ORDER BY next_fire ASC, id ASC').fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        nf = calc_next_fire(r)
        r['next_fire_computed'] = nf.isoformat() if nf else None
        result.append(r)
    return jsonify(result)

@app.route('/api/scheduled', methods=['POST'])
def create_scheduled():
    check_token()
    data = request.json or {}
    text            = data.get('text', '').strip()
    sched_type      = data.get('sched_type', 'onetime')
    fire_at         = data.get('fire_at')
    recur_days      = data.get('recur_days', '')
    recur_time      = data.get('recur_time', '')
    heads_up_days   = int(data.get('heads_up_days', 1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    if not text:
        return jsonify({'error': 'empty'}), 400
    conn = get_db()
    # Calculate initial next_fire
    dummy = {
        'sched_type': sched_type,
        'fire_at': fire_at,
        'recur_days': recur_days,
        'recur_time': recur_time,
    }
    nf = calc_next_fire(dummy)
    conn.execute(
        'INSERT INTO scheduled (text, sched_type, fire_at, recur_days, recur_time, heads_up_days, auto_remove_days, created, next_fire) VALUES (?,?,?,?,?,?,?,?,?)',
        (text, sched_type, fire_at, recur_days, recur_time, heads_up_days,
         auto_remove_days, now_local().isoformat(), nf.isoformat() if nf else None)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True}), 201

@app.route('/api/scheduled/<int:sched_id>', methods=['PUT'])
def update_scheduled(sched_id):
    check_token()
    data = request.json or {}
    text             = data.get('text', '').strip()
    sched_type       = data.get('sched_type', 'onetime')
    fire_at          = data.get('fire_at')
    recur_days       = data.get('recur_days', '')
    recur_time       = data.get('recur_time', '')
    heads_up_days    = int(data.get('heads_up_days', 1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    dummy = {'sched_type': sched_type, 'fire_at': fire_at, 'recur_days': recur_days, 'recur_time': recur_time}
    nf = calc_next_fire(dummy)
    conn = get_db()
    conn.execute(
        'UPDATE scheduled SET text=?,sched_type=?,fire_at=?,recur_days=?,recur_time=?,heads_up_days=?,auto_remove_days=?,next_fire=? WHERE id=?',
        (text, sched_type, fire_at, recur_days, recur_time, heads_up_days, auto_remove_days,
         nf.isoformat() if nf else None, sched_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/scheduled/<int:sched_id>', methods=['DELETE'])
def delete_scheduled(sched_id):
    check_token()
    conn = get_db()
    conn.execute('DELETE FROM scheduled WHERE id=?', (sched_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── Ingest endpoints ──────────────────────────────────────────────────────────
@app.route('/ingest/sms', methods=['POST'])
def ingest_sms():
    check_ingest()
    body = (request.form.get('Body') or '').strip()
    if body:
        _add_text(body)
    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}

@app.route('/ingest/android', methods=['POST'])
def ingest_android():
    check_ingest()
    data = request.json or {}
    if data.get('event') != 'sms:received':
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

# ── Frontend ──────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def frontend(path='index.html'):
    if path and any(path.startswith(p) for p in ('fonts/', 'static/')):
        return send_from_directory(app.static_folder, path)
    check_token()
    return send_from_directory(app.static_folder, 'index.html' if (not path or path == '/') else path)

# ── IMAP poller ───────────────────────────────────────────────────────────────
def _decode_header_str(h):
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
                subject = _decode_header_str(msg.get('Subject', '')).strip()
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
        # Start APScheduler for scheduled tasks (only in one worker)
        scheduler = BackgroundScheduler(timezone=TZ)
        scheduler.add_job(run_scheduler_tick, 'interval', minutes=1, id='scheduler_tick')
        scheduler.start()
        app.logger.info(f'Scheduler started (timezone: {TIMEZONE})')
    except FileExistsError:
        pass

_try_start_poller()

if __name__ == '__main__':
    try:
        os.remove('/data/.imap_lock')
    except FileNotFoundError:
        pass
    app.run(host='0.0.0.0', port=5000, debug=False)
