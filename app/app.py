import os
import sqlite3
import threading
import time
import imaplib
import email
import json
import secrets
import bcrypt
from email.header import decode_header
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, abort, redirect, make_response
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__, static_folder='static')
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

@app.after_request
def allow_iframe(response):
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

# ── Env config (security overrides only) ─────────────────────────────────────
DB_PATH       = os.environ.get('DB_PATH', '/data/stodo.db')
ENV_TOKEN     = os.environ.get('TOKEN', '')
INGEST_SECRET = os.environ.get('INGEST_SECRET', '')
IMAP_HOST     = os.environ.get('IMAP_HOST', '')
IMAP_PORT     = int(os.environ.get('IMAP_PORT', '993'))
IMAP_USER     = os.environ.get('IMAP_USER', '')
IMAP_PASS     = os.environ.get('IMAP_PASS', '')
IMAP_INTERVAL = int(os.environ.get('IMAP_INTERVAL', '30'))
TIMEZONE      = os.environ.get('TIMEZONE', 'America/Chicago')

# Note: branding/color env vars are used as initial defaults only.
# Once saved via UI they persist in the DB and env vars no longer apply.
# TOKEN env var always takes priority over UI token for security.

LAN_PREFIXES = ('10.', '192.168.', '172.', '127.')

try:
    TZ = pytz.timezone(TIMEZONE)
except Exception:
    TZ = pytz.utc

# ── Session store (DB-backed, shared across gunicorn workers) ────────────────
SESSION_TTL = 60 * 60 * 24 * 7  # 7 days

def create_session(username):
    token = secrets.token_hex(32)
    conn = get_db()
    conn.execute('INSERT INTO sessions (token, username, created) VALUES (?,?,?)',
                 (token, username, time.time()))
    conn.commit()
    conn.close()
    return token

def validate_session(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute('SELECT username, created FROM sessions WHERE token=?', (token,)).fetchone()
    conn.close()
    if not row:
        return None
    if time.time() - row['created'] > SESSION_TTL:
        delete_session(token)
        return None
    return row['username']

def delete_session(token):
    if not token:
        return
    conn = get_db()
    conn.execute('DELETE FROM sessions WHERE token=?', (token,))
    conn.commit()
    conn.close()

def clear_all_sessions():
    conn = get_db()
    conn.execute('DELETE FROM sessions')
    conn.commit()
    conn.close()

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
        auto_remove_days INTEGER,
        sched_source_id  INTEGER
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS scheduled (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        text             TEXT NOT NULL,
        sched_type       TEXT NOT NULL DEFAULT 'onetime',
        fire_at          TEXT,
        recur_days       TEXT,
        recur_time       TEXT,
        recur_mode       TEXT NOT NULL DEFAULT 'weekly',
        recur_interval   INTEGER NOT NULL DEFAULT 1,
        recur_dates      TEXT,
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

    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created      TEXT NOT NULL
    )''')

    conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token    TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        created  REAL NOT NULL
    )''')

    # Migrate items
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()]
    for col, typedef in [
        ('item_type','TEXT NOT NULL DEFAULT "normal"'),
        ('color_key','TEXT'),('item_color','TEXT'),
        ('fired_at','TEXT'),('auto_remove_days','INTEGER'),
        ('sched_source_id','INTEGER'),
    ]:
        if col not in existing_cols:
            conn.execute(f'ALTER TABLE items ADD COLUMN {col} {typedef}')

    # Migrate scheduled
    sched_cols = [r[1] for r in conn.execute("PRAGMA table_info(scheduled)").fetchall()]
    for col, typedef in [
        ('recur_mode','TEXT NOT NULL DEFAULT "weekly"'),
        ('recur_interval','INTEGER NOT NULL DEFAULT 1'),
        ('recur_dates','TEXT'),
    ]:
        if col not in sched_cols:
            conn.execute(f'ALTER TABLE scheduled ADD COLUMN {col} {typedef}')

    # Default settings — env vars seed initial values, UI changes persist
    defaults = {
        'app_title':       os.environ.get('APP_TITLE', 'SPAZCAT TO DO'),
        'app_subtitle':    os.environ.get('APP_SUBTITLE', 'STODO'),
        'accent_color':    os.environ.get('ACCENT_COLOR', '#5f249f'),
        'bg_color':        os.environ.get('BG_COLOR', '#0d0d0d'),
        'surface_color':   os.environ.get('SURFACE_COLOR', '#161616'),
        'title_color':     os.environ.get('TITLE_COLOR', '#ffffff'),
        'text_color':      os.environ.get('TEXT_COLOR', '#f0f0f0'),
        'font_size':       '26',
        'heads_up_days':   '1',
        'onetime_color':   '#5f249f',
        'recurring_color': '#0e7490',
        'auth_mode':       'none',
        'db_token':        '',
    }
    for k, v in defaults.items():
        conn.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))

    conn.commit()
    conn.close()

def get_settings():
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    d = {r['key']: r['value'] for r in rows}
    # ENV_TOKEN always overrides DB token (security)
    if ENV_TOKEN:
        d['db_token'] = ENV_TOKEN
    return d

def set_setting(key, value):
    # Strip stray surrounding quotes that legacy data may have introduced
    v = str(value)
    if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
        v = v[1:-1]
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, v))
    conn.commit()
    conn.close()

# One-time cleanup of legacy quoted values on startup
def cleanup_quoted_settings():
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    for r in rows:
        v = r['value']
        if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
            conn.execute('UPDATE settings SET value=? WHERE key=?', (v[1:-1], r['key']))
    conn.commit()
    conn.close()

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_real_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''

def is_lan():
    return any(get_real_ip().startswith(p) for p in LAN_PREFIXES)

def get_active_token():
    """Returns the active token (env takes priority over DB)."""
    if ENV_TOKEN:
        return ENV_TOKEN
    # Read directly from DB to avoid caching issues
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='db_token'").fetchone()
    conn.close()
    return row['value'] if row else ''

def get_auth_mode():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='auth_mode'").fetchone()
    conn.close()
    return row['value'] if row else 'none'

def check_session():
    """Check if request has a valid session cookie."""
    cookie = request.cookies.get('stodo_session')
    if cookie and validate_session(cookie):
        return True
    return False

def check_auth():
    """Main auth gate. Returns None if allowed, or aborts/redirects."""
    if is_lan():
        return  # LAN always trusted

    mode = get_auth_mode()

    if mode == 'none':
        return  # Open

    token = get_active_token()
    url_token = request.args.get('token', '')

    # A valid token match requires a non-empty configured token AND exact match
    token_valid = bool(token) and bool(url_token) and (url_token == token)

    if mode == 'token':
        if token_valid:
            return
        abort(403)

    if mode == 'login':
        if check_session():
            return
        if request.path.startswith('/api/') or request.path.startswith('/ingest/'):
            abort(401)
        return redirect('/login')

    if mode == 'both':
        if token_valid:
            return
        if check_session():
            return
        if request.path.startswith('/api/') or request.path.startswith('/ingest/'):
            abort(401)
        return redirect('/login')

def check_token():
    result = check_auth()
    if result is not None:
        return result

def check_ingest():
    if not INGEST_SECRET: return
    if request.args.get('secret') == INGEST_SECRET: return
    abort(403)

# ── Time helpers ──────────────────────────────────────────────────────────────
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

# ── Scheduler ─────────────────────────────────────────────────────────────────
def calc_next_fire(sched):
    now = now_local()
    if sched['sched_type'] == 'onetime':
        fire = parse_local(sched['fire_at'])
        return fire if fire and fire > now else None

    mode     = sched.get('recur_mode', 'weekly') or 'weekly'
    interval = int(sched.get('recur_interval', 1) or 1)
    recur_time = sched.get('recur_time', '') or ''
    try:
        h, m = map(int, recur_time.split(':')) if recur_time else (0, 0)
    except Exception:
        h, m = 0, 0

    if mode == 'weekly':
        days_map = {'sun':6,'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5}
        recur_days = [d.strip().lower() for d in (sched.get('recur_days','') or '').split(',') if d.strip()]
        day_nums = [days_map[d] for d in recur_days if d in days_map]
        if not day_nums: return None
        for delta in range(interval * 7 + 7):
            candidate = now + timedelta(days=delta)
            if candidate.weekday() in day_nums:
                week_num = candidate.toordinal() // 7
                if interval == 1 or week_num % interval == 0:
                    candidate = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                    if candidate > now:
                        return candidate
        return None

    elif mode == 'monthly':
        import calendar
        dates_str = sched.get('recur_dates', '') or ''
        date_nums = [int(d.strip()) for d in dates_str.split(',') if d.strip().isdigit()]
        if not date_nums: return None
        check = now.replace(day=1)
        for _ in range(interval * 13):
            max_day = calendar.monthrange(check.year, check.month)[1]
            for day_num in sorted(date_nums):
                actual_day = min(day_num, max_day)
                try:
                    candidate = check.replace(day=actual_day, hour=h, minute=m, second=0, microsecond=0)
                    if candidate > now:
                        return candidate
                except ValueError:
                    pass
            month = check.month + interval
            year  = check.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            check = check.replace(year=year, month=month, day=1)
        return None
    return None

def ensure_scheduled_tag(conn, item_id):
    """Attach the 'Scheduled' tag to an item."""
    row = conn.execute("SELECT id FROM tags WHERE name='Scheduled'").fetchone()
    if row:
        tag_id = row['id']
    else:
        tag_id = conn.execute("INSERT INTO tags (name) VALUES ('Scheduled')").lastrowid
    conn.execute('INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?,?)', (item_id, tag_id))

def run_scheduler_tick():
    try:
        now = now_local()
        cfg = get_settings()
        conn = get_db()
        rows = conn.execute('SELECT * FROM scheduled').fetchall()
        for row in rows:
            sched = dict(row)

            # Compute the target fire time. For one-time, use fire_at directly
            # (don't rely on calc_next_fire which returns None once past).
            if sched['sched_type'] == 'onetime':
                target_fire = parse_local(sched['fire_at'])
            else:
                target_fire = parse_local(sched['next_fire']) if sched['next_fire'] else calc_next_fire(sched)

            if not target_fire:
                continue

            heads_up       = sched['heads_up_days'] or 0
            heads_up_start = target_fire - timedelta(days=heads_up)
            base_color     = cfg.get('onetime_color','#5f249f') if sched['sched_type']=='onetime' else cfg.get('recurring_color','#0e7490')
            is_day_of      = now >= target_fire

            # Find existing board item spawned from this scheduled task for THIS fire cycle
            existing = conn.execute(
                "SELECT * FROM items WHERE sched_source_id=? AND item_type IN ('onetime','recurring') ORDER BY id DESC LIMIT 1",
                (sched['id'],)
            ).fetchone()

            # Determine desired color_key based on current time
            desired_key = f"{sched['sched_type']}-{'fired' if is_day_of else 'headsup'}"

            if now < heads_up_start:
                # Not yet in heads-up window — nothing to do
                continue

            if not existing:
                # Spawn the board item (heads-up or day-of, whichever applies now)
                max_pos = conn.execute('SELECT COALESCE(MAX(pos),0) FROM items').fetchone()[0]
                cur = conn.execute(
                    'INSERT INTO items (text,pos,created,item_type,color_key,item_color,fired_at,auto_remove_days,sched_source_id) VALUES (?,?,?,?,?,?,?,?,?)',
                    (sched['text'],max_pos+1,now.isoformat(),sched['sched_type'],desired_key,base_color,
                     target_fire.isoformat(),sched['auto_remove_days'],sched['id'])
                )
                ensure_scheduled_tag(conn, cur.lastrowid)
                # If we spawned it already fired (day-of), advance the schedule
                if is_day_of:
                    _advance_schedule(conn, sched)
            else:
                # Board item exists — update its color_key if it needs to transition
                if existing['color_key'] != desired_key:
                    conn.execute('UPDATE items SET color_key=?, fired_at=? WHERE id=?',
                                 (desired_key, target_fire.isoformat(), existing['id']))
                    ensure_scheduled_tag(conn, existing['id'])
                    # If transitioning INTO fired state, advance the schedule
                    if is_day_of and 'fired' in desired_key:
                        _advance_schedule(conn, sched)

        # Auto-remove: count from actual fire date, only after it has fired
        stale = conn.execute(
            "SELECT * FROM items WHERE item_type IN ('onetime','recurring') AND auto_remove_days IS NOT NULL AND fired_at IS NOT NULL AND color_key LIKE '%fired%'"
        ).fetchall()
        for item in stale:
            fired = parse_local(item['fired_at'])
            if fired and now >= fired + timedelta(days=item['auto_remove_days']):
                conn.execute('DELETE FROM item_tags WHERE item_id=?',(item['id'],))
                conn.execute('DELETE FROM items WHERE id=?',(item['id'],))

        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.warning(f'Scheduler tick error: {e}')

def _advance_schedule(conn, sched):
    """Advance a schedule's next_fire after it has fired."""
    if sched['sched_type'] == 'onetime':
        conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?', (None, sched['id']))
    else:
        import copy
        # Recompute from a point just after the current fire
        s = copy.copy(sched)
        nf2 = calc_next_fire(s)
        conn.execute('UPDATE scheduled SET next_fire=? WHERE id=?',
                     (nf2.isoformat() if nf2 else None, sched['id']))

# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.route('/login')
def login_page():
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    try:
        if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return jsonify({'error': 'Invalid credentials'}), 401
    except Exception:
        return jsonify({'error': 'Invalid credentials'}), 401
    session_token = create_session(username)
    resp = make_response(jsonify({'ok': True}))
    resp.set_cookie('stodo_session', session_token, httponly=True, samesite='Lax', max_age=SESSION_TTL)
    return resp

@app.route('/api/logout', methods=['POST'])
def api_logout():
    cookie = request.cookies.get('stodo_session','')
    delete_session(cookie)
    resp = make_response(jsonify({'ok': True}))
    resp.delete_cookie('stodo_session')
    return resp

# ── Config API ────────────────────────────────────────────────────────────────
@app.route('/api/auth-status')
def api_auth_status():
    # PUBLIC endpoint — no auth required. Used by the login page.
    return jsonify({
        'auth_mode': get_auth_mode(),
        'has_token': bool(get_active_token()),
        'app_title': get_settings().get('app_title', 'STODO'),
    })

@app.route('/api/config')
def api_config():
    result = check_token()
    if result: return result
    cfg = get_settings()
    # Don't expose token value to frontend
    cfg.pop('db_token', None)
    cfg['auth_mode'] = cfg.get('auth_mode','none')
    cfg['has_token'] = bool(get_active_token())
    return jsonify(cfg)

@app.route('/api/config', methods=['PUT'])
def api_config_put():
    result = check_token()
    if result: return result
    data = request.json or {}
    allowed = {'app_title','app_subtitle','accent_color','bg_color','surface_color',
               'title_color','text_color','font_size','heads_up_days',
               'onetime_color','recurring_color','auth_mode','db_token'}
    auth_changed = 'auth_mode' in data or 'db_token' in data
    for k, v in data.items():
        if k in allowed:
            if k == 'db_token' and ENV_TOKEN:
                continue
            set_setting(k, v)
    # Invalidate all sessions when auth settings change
    if auth_changed:
        clear_all_sessions()
        app.logger.info('Auth settings changed — all sessions invalidated')
    return jsonify({'ok': True, 'auth_changed': auth_changed})

# ── Settings backup/restore ───────────────────────────────────────────────────
@app.route('/api/config/export')
def config_export():
    result = check_token()
    if result: return result
    cfg = get_settings()
    cfg.pop('db_token', None)  # don't export secrets
    return jsonify(cfg)

# ── Users API ─────────────────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
def list_users():
    result = check_token()
    if result: return result
    conn = get_db()
    rows = conn.execute('SELECT id, username, created FROM users ORDER BY username').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/users', methods=['POST'])
def create_user():
    result = check_token()
    if result: return result
    data = request.json or {}
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn = get_db()
        conn.execute('INSERT INTO users (username, password_hash, created) VALUES (?,?,?)',
                     (username, pw_hash, now_local().isoformat()))
        conn.commit()
        conn.close()
        return jsonify({'ok': True}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    result = check_token()
    if result: return result
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=?',(user_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── Items API ─────────────────────────────────────────────────────────────────
@app.route('/api/items', methods=['GET'])
def list_items():
    result = check_token()
    if result: return result
    conn = get_db()
    rows = conn.execute('SELECT * FROM items ORDER BY pos ASC, id ASC').fetchall()
    result2 = []
    for row in rows:
        item = dict(row)
        item['tags'] = get_item_tags(conn, item['id'])
        result2.append(item)
    conn.close()
    return jsonify(result2)

@app.route('/api/items', methods=['POST'])
def add_item():
    result = check_token()
    if result: return result
    text = (request.json or {}).get('text','').strip()
    if not text: return jsonify({'error':'empty'}), 400
    _add_text(text)
    return jsonify({'ok':True}), 201

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    result = check_token()
    if result: return result
    data = request.json or {}
    conn = get_db()
    if 'text' in data and data['text'].strip():
        conn.execute('UPDATE items SET text=? WHERE id=?',(data['text'].strip(),item_id))
    if 'item_color' in data:
        conn.execute('UPDATE items SET item_color=? WHERE id=?',(data['item_color'],item_id))
    if 'item_type' in data:
        conn.execute('UPDATE items SET item_type=? WHERE id=?',(data['item_type'],item_id))
    if 'color_key' in data:
        conn.execute('UPDATE items SET color_key=? WHERE id=?',(data['color_key'],item_id))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    result = check_token()
    if result: return result
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE item_id=?',(item_id,))
    conn.execute('DELETE FROM items WHERE id=?',(item_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/items/reorder', methods=['POST'])
def reorder_items():
    result = check_token()
    if result: return result
    order = request.json or []
    conn = get_db()
    for entry in order:
        conn.execute('UPDATE items SET pos=? WHERE id=?',(entry['pos'],entry['id']))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/items/<int:item_id>/tags', methods=['PUT'])
def set_item_tags(item_id):
    result = check_token()
    if result: return result
    tag_names = request.json or []
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE item_id=?',(item_id,))
    for name in tag_names:
        name = name.strip()
        if not name: continue
        existing = conn.execute('SELECT id FROM tags WHERE name=?',(name,)).fetchone()
        tag_id = existing['id'] if existing else conn.execute('INSERT INTO tags (name) VALUES (?)',(name,)).lastrowid
        conn.execute('INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?,?)',(item_id,tag_id))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/tags', methods=['GET'])
def list_tags():
    result = check_token()
    if result: return result
    conn = get_db()
    rows = conn.execute('SELECT * FROM tags ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    result = check_token()
    if result: return result
    conn = get_db()
    conn.execute('DELETE FROM item_tags WHERE tag_id=?',(tag_id,))
    conn.execute('DELETE FROM tags WHERE id=?',(tag_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

# ── Scheduled API ─────────────────────────────────────────────────────────────
@app.route('/api/scheduled', methods=['GET'])
def list_scheduled():
    result = check_token()
    if result: return result
    conn = get_db()
    rows = conn.execute('SELECT * FROM scheduled ORDER BY next_fire ASC, id ASC').fetchall()
    conn.close()
    result2 = []
    for row in rows:
        r = dict(row)
        nf = calc_next_fire(r)
        r['next_fire_computed'] = nf.isoformat() if nf else None
        result2.append(r)
    return jsonify(result2)

@app.route('/api/scheduled', methods=['POST'])
def create_scheduled():
    result = check_token()
    if result: return result
    data = request.json or {}
    text           = data.get('text','').strip()
    sched_type     = data.get('sched_type','onetime')
    fire_at        = data.get('fire_at')
    recur_days     = data.get('recur_days','')
    recur_time     = data.get('recur_time','')
    recur_mode     = data.get('recur_mode','weekly')
    recur_interval = int(data.get('recur_interval',1) or 1)
    recur_dates    = data.get('recur_dates','')
    heads_up_days  = int(data.get('heads_up_days',1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    if not text: return jsonify({'error':'empty'}), 400
    dummy = {'sched_type':sched_type,'fire_at':fire_at,'recur_days':recur_days,'recur_time':recur_time,'recur_mode':recur_mode,'recur_interval':recur_interval,'recur_dates':recur_dates}
    nf = calc_next_fire(dummy)
    conn = get_db()
    conn.execute(
        'INSERT INTO scheduled (text,sched_type,fire_at,recur_days,recur_time,recur_mode,recur_interval,recur_dates,heads_up_days,auto_remove_days,created,next_fire) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (text,sched_type,fire_at,recur_days,recur_time,recur_mode,recur_interval,recur_dates,heads_up_days,auto_remove_days,now_local().isoformat(),nf.isoformat() if nf else None)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok':True}), 201

@app.route('/api/scheduled/<int:sched_id>', methods=['PUT'])
def update_scheduled(sched_id):
    result = check_token()
    if result: return result
    data = request.json or {}
    text           = data.get('text','').strip()
    sched_type     = data.get('sched_type','onetime')
    fire_at        = data.get('fire_at')
    recur_days     = data.get('recur_days','')
    recur_time     = data.get('recur_time','')
    recur_mode     = data.get('recur_mode','weekly')
    recur_interval = int(data.get('recur_interval',1) or 1)
    recur_dates    = data.get('recur_dates','')
    heads_up_days  = int(data.get('heads_up_days',1))
    auto_remove_days = data.get('auto_remove_days')
    if auto_remove_days is not None:
        auto_remove_days = int(auto_remove_days)
    dummy = {'sched_type':sched_type,'fire_at':fire_at,'recur_days':recur_days,'recur_time':recur_time,'recur_mode':recur_mode,'recur_interval':recur_interval,'recur_dates':recur_dates}
    nf = calc_next_fire(dummy)
    conn = get_db()
    # Check if this schedule was previously completed (had no next_fire)
    old_row = conn.execute('SELECT next_fire FROM scheduled WHERE id=?', (sched_id,)).fetchone()
    was_completed = old_row and not old_row['next_fire']
    conn.execute(
        'UPDATE scheduled SET text=?,sched_type=?,fire_at=?,recur_days=?,recur_time=?,recur_mode=?,recur_interval=?,recur_dates=?,heads_up_days=?,auto_remove_days=?,next_fire=? WHERE id=?',
        (text,sched_type,fire_at,recur_days,recur_time,recur_mode,recur_interval,recur_dates,heads_up_days,auto_remove_days,nf.isoformat() if nf else None,sched_id)
    )
    # If reactivating a completed schedule with a new future fire, clear stale
    # board items so the scheduler spawns a fresh one at the right time
    if was_completed and nf:
        stale = conn.execute("SELECT id FROM items WHERE sched_source_id=?", (sched_id,)).fetchall()
        for it in stale:
            conn.execute('DELETE FROM item_tags WHERE item_id=?', (it['id'],))
            conn.execute('DELETE FROM items WHERE id=?', (it['id'],))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/scheduled/<int:sched_id>', methods=['DELETE'])
def delete_scheduled(sched_id):
    result = check_token()
    if result: return result
    conn = get_db()
    conn.execute('DELETE FROM scheduled WHERE id=?',(sched_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

# ── Ingest ────────────────────────────────────────────────────────────────────
@app.route('/ingest/sms', methods=['POST'])
def ingest_sms():
    check_ingest()
    body = (request.form.get('Body') or '').strip()
    if body: _add_text(body)
    return '<Response></Response>', 200, {'Content-Type':'text/xml'}

@app.route('/ingest/android', methods=['POST'])
def ingest_android():
    check_ingest()
    data = request.json or {}
    if data.get('event') != 'sms:received': return jsonify({'ok':True})
    message = (data.get('payload') or {}).get('message','').strip()
    if message:
        _add_text(message)
        app.logger.info(f'Android SMS ingest: {message}')
    return jsonify({'ok':True}), 200

@app.route('/ingest/text', methods=['POST'])
def ingest_text():
    check_ingest()
    text = (request.json or {}).get('text','').strip()
    if not text: return jsonify({'error':'empty'}), 400
    _add_text(text)
    return jsonify({'ok':True}), 201

# ── Frontend ──────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/<path:path>')
def frontend(path='index.html'):
    if path and any(path.startswith(p) for p in ('fonts/','static/')):
        return send_from_directory(app.static_folder, path)
    if path == 'login':
        return send_from_directory(app.static_folder, 'login.html')
    result = check_auth()
    if result is not None and hasattr(result, 'status_code'):
        return result
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
cleanup_quoted_settings()

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
