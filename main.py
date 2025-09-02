"""
Flask URL Shortener — single-file app
Run: pip install flask validators
Then: python app.py

This single file contains:
- Flask app
- Inline HTML/CSS/JS (render_template_string)
- SQLite DB (shortcodes -> target URL)

Features:
- Create short links
- Redirect by short code
- Responsive beautiful UI (desktop + mobile)
- Copy button
- Basic URL validation
- Simple statistics (clicks)

"""
from flask import Flask, request, redirect, abort, g, jsonify, render_template_string, url_for, render_template
import sqlite3
import string
import random
import validators
from urllib.parse import urlparse
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'shortener.db')

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# ---------- Database helpers ----------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            target TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            clicks INTEGER DEFAULT 0
        )
    ''')
    db.commit()
    db.close()

# ---------- Utilities ----------
CHARS = string.ascii_letters + string.digits

def generate_code(length=6):
    return ''.join(random.choice(CHARS) for _ in range(length))

def make_full_url(code):
    return request.url_root.rstrip('/') + '/' + code

def clean_url(u: str) -> str:
    u = u.strip()
    # if no scheme, assume https
    parsed = urlparse(u)
    if not parsed.scheme:
        u = 'https://' + u
    return u


@app.route('/')
def index():
    return render_template('index.html')



@app.route('/api/shorten', methods=['POST'])
def api_shorten():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL не указан'}), 400
    url = clean_url(url)
    if not validators.url(url):
        return jsonify({'error': 'Неверный URL'}), 400

    db = get_db()
    cur = db.cursor()
    # Try to generate unique code
    for _ in range(8):
        code = generate_code(6)
        try:
            cur.execute('INSERT INTO links (code, target) VALUES (?,?)', (code, url))
            db.commit()
            short = make_full_url(code)
            return jsonify({'short': short, 'code': code})
        except sqlite3.IntegrityError:
            continue
    return jsonify({'error': 'Не удалось сгенерировать код, попробуйте снова'}), 500




@app.route('/api/list')
def api_list():
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT code, target, clicks FROM links ORDER BY id DESC LIMIT 100')
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({'code': r['code'], 'target': r['target'], 'clicks': r['clicks'], 'short': request.url_root.rstrip('/') + '/' + r['code'], 'url': r['target']})
    return jsonify(out)



@app.route('/<code>')
def redirect_code(code):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT id, target, clicks FROM links WHERE code = ?', (code,))
    row = cur.fetchone()
    if not row:
        return render_template_string('<h2>Ссылка не найдена</h2><p><a href="/">На главную</a></p>'), 404
    # increment clicks
    cur.execute('UPDATE links SET clicks = clicks + 1 WHERE id = ?', (row['id'],))
    db.commit()
    target = row['target']
    return redirect(target)

# ---------- Run ----------

init_db()
