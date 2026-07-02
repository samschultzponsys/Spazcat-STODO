import os
import sqlite3
import threading
import time
import imaplib
import email
import json
from email.header import decode_header
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__, static_folder='static')
CORS(app)

@app.after_request
def allow_iframe(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

# ── Config from env (security only) ──────────────────────────────────────────
DB_PATH       = os.environ.get('DB_PATH', '/data/stodo.db')
TOKEN         = os.environ.get('TOKEN', '')
INGEST_SECRET = os.environ.get('INGEST_SECRET', '')
IMAP_HOST     = os.environ.get('IMAP_HOST', '')
IMAP_PORT     = int(os.environ.get('IMAP_PORT', '993'))
IMAP_USER     = os.environ.get('IMAP_USER', '')
IMAP_PASS     = os.environ.get('IMAP_PASS', '')
IMAP_INTERVAL = int(os.environ.get('IMAP_INTERVAL', '30'))
TIMEZONE      = os.environ.get('TIMEZONE', 'America/Chicago')

LAN_PREFIXES  = ('10.', '192.168.', '172.', '127.')

try:
    TZ = pytz.timezone(TIMEZONE)
except Exception:
    TZ = pytz.utc

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_real_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

def is_lan():
    return any(get_real_ip().startswith(p) for p in LAN_PREFIXES)

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

    conn.execute('''CREATE TABLE IF NOT EXISTS items (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        text             TEXT NOT NULL,
        pos              INTEGER NOT NULL DEFAULT 0,
        created          TEXT NOT NULL,
        item_type        TEXT NOT NULL DEFAULT 'normal',
        color_key        TEXT,
        item_color       TEXT,
        fired_at         TEXT,
        auto_remove_days INTEGER
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS scheduled (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        text             TEXT NOT NULL,
        sched_type       TEXT NOT NULL DEFAULT 'onetime',
        fire_at          TEXT,
        recur_days       TEXT,
        recur_time       TEXT,
        heads_up_days    INTEGER NOT NULL DEFAULT 1,
        auto_remove_days INTEGER,
        created          TEXT NOT NULL,
        next_fire        TEXT
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS tags (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT NOT NULL UNIQUE
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS item_tags (
        item_id INTEGER NOT NULL,
        tag_id  INTEGER NOT NULL,
        PRIMARY KEY (item_id, tag_id)
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    # Migrate existing items table
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    for col, typedef in [
        ('item_type',        'TEXT NOT NULL DEFAULT "normal"'),
        ('color_key',        'TEXT'),
        ('item_color',       'TEXT'),
        ('fired_at',         'TEXT'),
        ('auto_remove_days', 'INTEGER'),
    ]:
        if col not in existing_cols:
            conn.execute(f'ALTER TABLE items ADD COLUMN {col} {typedef}')

    # Default settings
    defaults = {
        'app_title':         'SPAZCAT TO DO',
        'app_subtitle':      'STODO',
        'accent_color':      '#5f249f',
        'bg_color':          '#0d0d0d',
        'surface_color':     '#161616',
        'title_color':       '#ffffff',
        'text_color':        '#f0f0f0',
        'font_size':         '18',
        'heads_up_days':     '1',
        'onetime_color':     '#5f249f',
        'recurring_color':   '#0e7490',
    }
    for k, v in defaults.items():
        conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))

    conn.commit()
    conn.close()

def get_settings():
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}

def set_setting(key, value):
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_local():
    return datetime.now(TZ)

def parse_local(dt_str):
    if not dt_str: return None
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
        'INSERT INTO items (text, pos, created, item_type, color_key, fired_at, auto_remove_days) VALUES (?,?,?,?,?,?,?)',
        (text, max_pos+1, now_local().isoformat(), item_type, color_key,
         now_local().isoformat(), auto_remove_days)
    )
    conn.commit()
    conn.close()

def get_item_tags(conn, item_id):
    rows = conn.execute('''
        SELECT t.id, t.name FROM tags t
        JOIN item_tags it ON it.tag_id = t.id
        WHERE it.item_id = ?
    ''', (item_id,)).fetchall()
    return [dict(r) for r in rows]

def calc_next_fire(sched):
    now = now_local()
    if sched['sched_type'] == 'onetime':
        fire = parse_local(sched['fire_at'])
        return fire if fire and fire > now else None
    else:
        days_map = {'sun':6,'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5}
        recur_days = [d.strip().lower() for d in (sched['recur_days'] or '').split(',') if d.strip()]
        day_nums = [days_map[d] for d in recur_days if d in days_map]
        if not day_nums or not sched['recur_time']:
            return None
        try:
            h, m = map(int, sched['recur_time'].split(':'))
        except Exception:
            return None
        for delta in range(8):
            candidate = now + timedelta(days=delta)
            if candidate.weekday() in day_nums:
                candidate = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                if candidate > now:
                    return candidate
        return None

# ── Scheduler tick ────────────────────────────────────────────────────────────
def run_scheduler_tick():
    try:
        now  = now_local()
        cfg  = get_settings()
        conn = get_db()
        rows = conn.execute('SELECT * FROM scheduled').fetchall()
        for row in rows:
            sched      = dict(row)
            next_fire  = parse_local(sched['next_fire']) if sched['next_fire'] else calc_next_fire(sched)
            if not next_fire:
                continue
            heads_up       = sched['heads_up_days'] or 1
            heads_up_start = next_fire - timedelta(days=heads_up)
            existing = conn.execute(
                "SELECT id FROM items WHERE text=? AND item_type IN ('onetime','recurring') AND fired_at>=?",
                (sched['text'], heads_up_start.isoformat())
            ).fetchone()
            if now >= heads_up_start and not existing:
                is_day_of  = now >= next_fire
                base_color = cfg.get('onetime_color', '#5f249f') if sched['sched_type'] == 'onetime' else cfg.get('recurring_color', '#0e7490')
                color_key  = f"{sched['sched_type']}-{'fired' if is_day_of else 'headsup'}"
                max_pos    = conn.execute('SELECT COALESCE(MAX(pos),0) FROM items').fetchone()[0]
                conn.execute(
                    'INSERT INTO items (text, pos, created, item_type, color_key, item_color, fired_at, auto_remove_days) VALUES (?,?,?,?,?,?,?,?)',
                    (sched['text'], max_pos+1, now.isoformat(), sched['sched_type'],
                     color_key, base_color, now.isoformat(), sched['auto_remove_days'])
                )
                if is_day_of:
                    if sched['sched_type'] == 'onetime':
                        conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?', (None, sched['id']))
                    else:
                        import copy
                        nf2 = calc_next_fire(copy.copy(sched))
                        conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?',
                                     (nf2.isoformat() if nf2 else None, sched['id']))
                else:
                    conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?',
                                 (next_fire.isoformat(), sched['id']))
            elif existing and now >= next_fire:
                item = conn.execute('SELECT * FROM items WHERE id=?', (existing[0],)).fetchone()
                if item and 'headsup' in (item['color_key'] or ''):
                    conn.execute('UPDATE items SET color_key=? WHERE id=?',
                                 (item['color_key'].replace('headsup','fired'), item['id']))
        # Auto-remove
        stale = conn.execute(
            "SELECT * FROM items WHERE item_type IN ('onetime','recurring') AND auto_remove_days IS NOT NULL AND fired_at IS NOT NULL"
        ).fetchall()
        for item in stale:
            fired = parse_local(item['fired_at'])
            if fired and now >= fired + timedelta(days=item['auto_remove_days']):
                conn.execute('DELETE FROM items WHERE id=?', (item['id'],))
        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.warning(f'Scheduler tick error: {e}')

# ── API: settings ─────────────────────────────────────────────────────────────
@app.route('/api/config')
def api_config():
    check_token()
    cfg = get_settings()
    return jsonify(cfg)

@app.route('/api/config', methods=['PUT'])
def api_config_put():
    check_token()
    data = request.json or {}
    allowed = {'app_title','app_subtitle','accent_color','bg_color','surface_color',
               'title_color','text_color','font_size','heads_up_days',
               'onetime_color','recurring_color'}
    for k, v in data.items():
        if k in allowed:
            set_setting(k, v)
    return jsonify({'ok': True})

# ── API: items ────────────────────────────────────────────────────────────────
@app.route('/api/items', methods=['GET'])
def list_items():
    check_token()
    conn = get_db()
    rows = conn.execute('SELECT * FROM items ORDER BY pos ASC, id ASC').fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item['tags'] = get_item_tags(conn, item['id'])
        result.append(item)
    conn.close()
    return jsonify(result)

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
    data = request.json or {}
    conn = get_db()
    if 'text' in data and data['text'].strip():
        conn.execute('UPDATE items SET text=? WHERE id=?', (data['text'].strip(), item_id))
    if 'item_color' in data:
        conn.execute('UPDATE items SET item_color=? WHERE id=?', (data['item_color'], item_id))
    if 'item_type' in data:
        conn.execute('UPDATE items SET item_type=? WHERE id=?', (data['item_type'], item_id))
    if 'color_key' in data:
        conn.execute('UPDATE items SET color_key=? WHERE id=?', (data['color_key'], item_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    check_token()
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE item_id=?', (item_id,))
    conn.execute('DELETE FROM items WHERE id=?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/items/reorder', methods=['POST'])
def reorder_items():
    check_token()
    order = request.json or []
    conn = get_db()
    for entry in order:
        conn.execute('UPDATE items SET pos=? WHERE id=?', (entry['pos'], entry['id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── API: item tags ────────────────────────────────────────────────────────────
@app.route('/api/items/<int:item_id>/tags', methods=['PUT'])
def set_item_tags(item_id):
    check_token()
    tag_names = request.json or []
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE item_id=?', (item_id,))
    for name in tag_names:
        name = name.strip()
        if not name: continue
        existing = conn.execute('SELECT id FROM tags WHERE name=?', (name,)).fetchone()
        if existing:
            tag_id = existing['id']
        else:
            cur = conn.execute('INSERT INTO tags (name) VALUES (?)', (name,))
            tag_id = cur.lastrowid
        conn.execute('INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?,?)', (item_id, tag_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── API: all tags ─────────────────────────────────────────────────────────────
@app.route('/api/tags', methods=['GET'])
def list_tags():
    check_token()
    conn = get_db()
    rows = conn.execute('SELECT * FROM tags ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    check_token()
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE tag_id=?', (tag_id,))
    conn.execute('DELETE FROM tags WHERE id=?', (tag_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── API: scheduled ────────────────────────────────────────────────────────────
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
    data             = request.json or {}
    text             = data.get('text','').strip()
    sched_type       = data.get('sched_type','onetime')
    fire_at          = data.get('fire_at')
    recur_days       = data.get('recur_days','')
    recur_time       = data.get('recur_time','')
    heads_up_days    = int(data.get('heads_up_days',1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    if not text:
        return jsonify({'error':'empty'}), 400
    dummy = {'sched_type':sched_type,'fire_at':fire_at,'recur_days':recur_days,'recur_time':recur_time}
    nf = calc_next_fire(dummy)
    conn = get_db()
    conn.execute(
        'INSERT INTO scheduled (text,sched_type,fire_at,recur_days,recur_time,heads_up_days,auto_remove_days,created,next_fire) VALUES (?,?,?,?,?,?,?,?,?)',
        (text,sched_type,fire_at,recur_days,recur_time,heads_up_days,auto_remove_days,
         now_local().isoformat(), nf.isoformat() if nf else None)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok':True}), 201

@app.route('/api/scheduled/<int:sched_id>', methods=['PUT'])
def update_scheduled(sched_id):
    check_token()
    data             = request.json or {}
    text             = data.get('text','').strip()
    sched_type       = data.get('sched_type','onetime')
    fire_at          = data.get('fire_at')
    recur_days       = data.get('recur_days','')
    recur_time       = data.get('recur_time','')
    heads_up_days    = int(data.get('heads_up_days',1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    dummy = {'sched_type':sched_type,'fire_at':fire_at,'recur_days':recur_days,'recur_time':recur_time}
    nf = calc_next_fire(dummy)
    conn = get_db()
    conn.execute(
        'UPDATE scheduled SET text=?,sched_type=?,fire_at=?,recur_days=?,recur_time=?,heads_up_days=?,auto_remove_days=?,next_fire=? WHERE id=?',
        (text,sched_type,fire_at,recur_days,recur_time,heads_up_days,auto_remove_days,
         nf.isoformat() if nf else None, sched_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/scheduled/<int:sched_id>', methods=['DELETE'])
def delete_scheduled(sched_id):
    check_token()
    conn = get_db()
    conn.execute('DELETE FROM scheduled WHERE id=?', (sched_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

# ── Ingest ────────────────────────────────────────────────────────────────────
@app.route('/ingest/sms', methods=['POST'])
def ingest_sms():
    check_ingest()
    body = (request.form.get('Body') or '').strip()
    if body: _add_text(body)
    return '<Response></Response>', 200, {'Content-Type': 'text/xml'}

@app.route('/ingest/android', methods=['POST'])
def ingest_android():
    check_ingest()
    data = request.json or {}
    if data.get('event') != 'sms:received':
        return jsonify({'ok':True})
    message = (data.get('payload') or {}).get('message','').strip()
    if message:
        _add_text(message)
        app.logger.info(f'Android SMS ingest: {message}')
    return jsonify({'ok':True}), 200

@app.route('/ingest/text', methods=['POST'])
def ingest_text():
    check_ingest()
    text = (request.json or {}).get('text','').strip()
    if not text:
        return jsonify({'error':'empty'}), 400
    _add_text(text)
    return jsonify({'ok':True}), 201

# ── Frontend ──────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def frontend(path='index.html'):
    if path and any(path.startswith(p) for p in ('fonts/','static/')):
        return send_from_directory(app.static_folder, path)
    check_token()
    return send_from_directory(app.static_folder, 'index.html' if (not path or path=='/') else path)

# ── IMAP ──────────────────────────────────────────────────────────────────────
def _decode_hdr(h):
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
        app.logger.info('IMAP not configured')
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
                subject = _decode_hdr(msg.get('Subject','')).strip()
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
