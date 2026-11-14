#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TĐH Chemistry — lớp học Hoá học số: LMS + thi trực tuyến.

Chỉ dùng thư viện chuẩn của Python 3 và SQLite. Chạy:  python3 server.py
Mọi quyền truy cập, đáp án và việc chấm điểm đều xử lí ở máy chủ.
"""
import argparse, base64, csv, hashlib, hmac, io, json, mimetypes, os, random, re, secrets
import socket, sqlite3, sys, time, traceback, unicodedata
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, 'static')
DATA = os.path.join(BASE, 'data')
DB_PATH = None
SESSION_TTL = 12 * 3600
MAX_BODY = 2 * 1024 * 1024
GRACE = 15                      # giây châm chước khi lưu/nộp sát giờ
PBKDF_ITERS = 240_000
COOKIE = 'tdh_session'
SECURE_COOKIE = os.environ.get('TDH_SECURE_COOKIE') == '1'
TRUST_PROXY = os.environ.get('TDH_TRUST_PROXY') == '1'

TYPES = ('single_choice', 'true_false', 'short_answer')
LEVELS = ('NB', 'TH', 'VD')
SHOW = ('none', 'score', 'after_close', 'answers')
T, S, A, ANY = ('teacher', 'admin'), ('student',), ('admin',), ('admin', 'teacher', 'student')

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, login_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN('admin','teacher','student')),
  pw TEXT NOT NULL, must_change INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','locked')),
  created_by INTEGER REFERENCES users(id), created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS login_failures(login_id TEXT, ip TEXT, at INTEGER);
CREATE TABLE IF NOT EXISTS classes(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, year TEXT NOT NULL DEFAULT '',
  teacher_id INTEGER NOT NULL REFERENCES users(id), created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS enrollments(
  class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY(class_id, student_id));
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN('draft','approved')),
  grade INTEGER NOT NULL, chapter TEXT NOT NULL DEFAULT '', topic TEXT NOT NULL DEFAULT '',
  outcome TEXT NOT NULL DEFAULT '', level TEXT NOT NULL CHECK(level IN('NB','TH','VD')),
  type TEXT NOT NULL CHECK(type IN('single_choice','true_false','short_answer')),
  stem TEXT NOT NULL, payload TEXT NOT NULL, answer_key TEXT NOT NULL,
  explanation TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_q_owner ON questions(owner_id, grade, type, level);
CREATE TABLE IF NOT EXISTS exams(
  id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  start_at INTEGER, end_at INTEGER, duration_min INTEGER NOT NULL DEFAULT 45,
  max_attempts INTEGER NOT NULL DEFAULT 1, shuffle_q INTEGER NOT NULL DEFAULT 0,
  shuffle_opt INTEGER NOT NULL DEFAULT 0, show_result TEXT NOT NULL DEFAULT 'score',
  tf_policy TEXT NOT NULL DEFAULT 'scale', status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN('draft','open','closed')),
  created_at INTEGER NOT NULL, published_at INTEGER);
CREATE TABLE IF NOT EXISTS exam_questions(
  id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  question_id INTEGER, order_index INTEGER NOT NULL, points REAL NOT NULL,
  snapshot TEXT, answer_key TEXT, explanation TEXT);
CREATE INDEX IF NOT EXISTS ix_eq_exam ON exam_questions(exam_id, order_index);
CREATE TABLE IF NOT EXISTS exam_classes(
  exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  PRIMARY KEY(exam_id, class_id));
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  attempt_no INTEGER NOT NULL, started_at INTEGER NOT NULL, deadline_at INTEGER NOT NULL,
  submitted_at INTEGER, status TEXT NOT NULL DEFAULT 'in_progress'
    CHECK(status IN('in_progress','submitted')),
  score REAL, max_score REAL, layout TEXT NOT NULL, auto INTEGER NOT NULL DEFAULT 0,
  UNIQUE(exam_id, student_id, attempt_no));
CREATE TABLE IF NOT EXISTS attempt_answers(
  attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
  eq_id INTEGER NOT NULL, answer TEXT, saved_at INTEGER, awarded REAL,
  PRIMARY KEY(attempt_id, eq_id));
CREATE TABLE IF NOT EXISTS lessons(
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  teacher_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'link', url TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',
  published INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS lesson_done(
  lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
  student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, at INTEGER NOT NULL,
  PRIMARY KEY(lesson_id, student_id));
CREATE TABLE IF NOT EXISTS live_sessions(
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  teacher_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  starts_at INTEGER NOT NULL, duration_min INTEGER NOT NULL DEFAULT 45,
  join_url TEXT NOT NULL, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS news(
  id INTEGER PRIMARY KEY, author_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '', pinned INTEGER NOT NULL DEFAULT 0,
  published INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY, actor_id INTEGER, action TEXT NOT NULL, target TEXT NOT NULL DEFAULT '',
  meta TEXT NOT NULL DEFAULT '{}', at INTEGER NOT NULL);
"""


# ───────────────────────── tiện ích chung ─────────────────────────
def now():
    return int(time.time())


def db():
    con = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con


@contextmanager
def tx(con):
    con.execute('BEGIN IMMEDIATE')
    try:
        yield
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise


class ApiError(Exception):
    def __init__(self, status, msg, code=None):
        super().__init__(msg)
        self.status, self.msg, self.code = status, msg, code


class Raw:
    def __init__(self, ctype, data, headers=None):
        self.ctype, self.data, self.headers = ctype, data, headers or []


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def hash_pw(pw, salt=None, iters=PBKDF_ITERS):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, iters)
    return 'pbkdf2$%d$%s$%s' % (iters, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def check_pw(pw, stored):
    try:
        _, iters, salt, dk = stored.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), base64.b64decode(salt), int(iters))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


DUMMY_PW = hash_pw('không-dùng')
PW_ALPHA = 'abcdefghjkmnpqrstuvwxyz23456789'


def gen_password(n=10):
    return ''.join(secrets.choice(PW_ALPHA) for _ in range(n))


def norm_login(v):
    return unicodedata.normalize('NFC', str(v or '')).strip().lower()[:64]


def slug(s, maxlen=10):
    s = unicodedata.normalize('NFD', str(s).lower().replace('đ', 'd'))
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]', '', s)[:maxlen]


def txt(v, maxlen=300, required=False, field='nội dung'):
    s = '' if v is None else str(v)
    s = unicodedata.normalize('NFC', s).replace('\r\n', '\n').replace('\x00', '').strip()
    if len(s) > maxlen:
        raise ApiError(400, '%s quá dài (tối đa %d kí tự).' % (field.capitalize(), maxlen))
    if required and not s:
        raise ApiError(400, 'Chưa nhập %s.' % field)
    return s


def num(v, lo, hi, field, default=None, integer=True):
    if v is None or v == '':
        if default is not None:
            return default
        raise ApiError(400, 'Chưa nhập %s.' % field)
    try:
        x = int(v) if integer else float(v)
    except (TypeError, ValueError):
        raise ApiError(400, '%s không hợp lệ.' % field.capitalize())
    if isinstance(v, bool) or x != x or not (lo <= x <= hi):
        raise ApiError(400, '%s phải từ %s đến %s.' % (field.capitalize(), lo, hi))
    return x


def ts(v, field='thời gian'):
    if v is None or v == '':
        return None
    return num(v, 946684800, 4102444800, field)


def url_ok(v, field='liên kết', required=False):
    s = txt(v, 1000, required, field)
    if s and not re.match(r'^https?://[^\s<>"\']+$', s):
        raise ApiError(400, '%s phải bắt đầu bằng http:// hoặc https://' % field.capitalize())
    return s


def flag(v):
    return 1 if v in (True, 1, '1', 'true') else 0


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def audit(rq, action, target='', meta=None):
    rq.con.execute('INSERT INTO audit(actor_id, action, target, meta, at) VALUES(?,?,?,?,?)',
                   (rq.user['id'] if rq.user else None, action, target,
                    json.dumps(meta or {}, ensure_ascii=False), now()))


def user_public(u):
    return {'id': u['id'], 'login_id': u['login_id'], 'name': u['name'], 'role': u['role'],
            'must_change': bool(u['must_change'])}


ROUTES = []


def route(method, pattern, roles=None, use_tx=True):
    rx = re.compile('^' + re.sub(r'<(\w+)>', r'(?P<\1>[^/]+)', pattern) + '$')

    def deco(fn):
        ROUTES.append((method, rx, roles, use_tx, fn))
        return fn
    return deco


class Rq:
    def __init__(self, con, ip):
        self.con, self.ip = con, ip
        self.user = None
        self.body, self.query, self.params = {}, {}, {}
        self.token_hash = None
        self.set_cookie = None

    def pid(self, name='id'):
        try:
            return int(self.params[name])
        except (KeyError, ValueError):
            raise ApiError(404, 'Không tìm thấy.')

    @property
    def uid(self):
        return self.user['id']

    def q(self, name, default=''):
        return self.query.get(name, [default])[0]


# ───────────────────────── tài khoản, phiên ─────────────────────────
@route('POST', '/api/login', None, use_tx=False)
def login(rq):
    lid, pw = norm_login(rq.body.get('login_id')), str(rq.body.get('password') or '')
    con, t = rq.con, now()
    con.execute('DELETE FROM login_failures WHERE at < ?', (t - 3600,))
    by_id = con.execute('SELECT COUNT(*) FROM login_failures WHERE login_id=? AND at>?', (lid, t - 600)).fetchone()[0]
    by_ip = con.execute('SELECT COUNT(*) FROM login_failures WHERE ip=? AND at>?', (rq.ip, t - 600)).fetchone()[0]
    if by_id >= 8 or by_ip >= 150:
        raise ApiError(429, 'Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau khoảng 10 phút.')
    u = con.execute('SELECT * FROM users WHERE login_id=?', (lid,)).fetchone()
    ok = check_pw(pw, u['pw'] if u else DUMMY_PW) and u is not None and u['status'] == 'active'
    if not ok:
        con.execute('INSERT INTO login_failures VALUES(?,?,?)', (lid, rq.ip, t))
        raise ApiError(401, 'Mã đăng nhập hoặc mật khẩu không đúng.')
    token = secrets.token_urlsafe(32)
    with tx(con):
        con.execute('INSERT INTO sessions VALUES(?,?,?)', (sha(token), u['id'], t + SESSION_TTL))
        con.execute('DELETE FROM sessions WHERE expires_at < ?', (t,))
        con.execute('DELETE FROM login_failures WHERE login_id=?', (lid,))
    rq.set_cookie = token
    return user_public(u)


@route('POST', '/api/logout', None)
def logout(rq):
    if rq.token_hash:
        rq.con.execute('DELETE FROM sessions WHERE token=?', (rq.token_hash,))
    rq.set_cookie = ''
    return {'ok': True}


@route('GET', '/api/me', None)
def me(rq):
    return {'user': user_public(rq.user) if rq.user else None}


@route('POST', '/api/password', ANY, use_tx=False)
def change_password(rq):
    old, new = str(rq.body.get('old') or ''), str(rq.body.get('new') or '')
    u = rq.user
    if not check_pw(old, u['pw']):
        raise ApiError(400, 'Mật khẩu hiện tại không đúng.')
    if not (8 <= len(new) <= 128):
        raise ApiError(400, 'Mật khẩu mới cần từ 8 kí tự trở lên.')
    if new == old or new.lower() == u['login_id']:
        raise ApiError(400, 'Mật khẩu mới phải khác mật khẩu cũ và khác mã đăng nhập.')
    h = hash_pw(new)
    with tx(rq.con):
        rq.con.execute('UPDATE users SET pw=?, must_change=0 WHERE id=?', (h, u['id']))
        rq.con.execute('DELETE FROM sessions WHERE user_id=? AND token<>?', (u['id'], rq.token_hash))
        audit(rq, 'password.change')
    return {'ok': True}


@route('GET', '/api/public/news', None)
def public_news(rq):
    return {'news': rows(rq.con.execute(
        'SELECT n.id, n.title, n.body, n.pinned, n.created_at, u.name author FROM news n '
        'JOIN users u ON u.id=n.author_id WHERE n.published=1 ORDER BY n.pinned DESC, n.created_at DESC LIMIT 20'))}


# ───────────────────────── quản trị: giáo viên, nhật kí ─────────────────────────
@route('GET', '/api/a/teachers', A)
def a_teachers(rq):
    return {'teachers': rows(rq.con.execute(
        "SELECT id, login_id, name, role, status, must_change, created_at FROM users "
        "WHERE role IN('teacher','admin') ORDER BY id"))}


@route('POST', '/api/a/teachers', A, use_tx=False)
def a_teacher_create(rq):
    lid = norm_login(rq.body.get('login_id'))
    name = txt(rq.body.get('name'), 80, True, 'họ tên')
    if not re.match(r'^[a-z0-9][a-z0-9._-]{2,31}$', lid):
        raise ApiError(400, 'Mã đăng nhập gồm 3–32 kí tự: chữ không dấu, số, dấu chấm, gạch nối.')
    pw = gen_password()
    h = hash_pw(pw)
    with tx(rq.con):
        if rq.con.execute('SELECT 1 FROM users WHERE login_id=?', (lid,)).fetchone():
            raise ApiError(409, 'Mã đăng nhập này đã có người dùng.')
        rq.con.execute("INSERT INTO users(login_id,name,role,pw,must_change,created_by,created_at) "
                       "VALUES(?,?,'teacher',?,1,?,?)", (lid, name, h, rq.uid, now()))
        audit(rq, 'teacher.create', lid)
    return {'login_id': lid, 'name': name, 'password': pw}


def reset_account(rq, uid, action):
    pw = gen_password()
    h = hash_pw(pw)
    with tx(rq.con):
        rq.con.execute('UPDATE users SET pw=?, must_change=1 WHERE id=?', (h, uid))
        rq.con.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        audit(rq, action, 'user:%d' % uid)
    return {'password': pw}


def set_account_status(rq, uid, action):
    st = rq.body.get('status')
    if st not in ('active', 'locked'):
        raise ApiError(400, 'Trạng thái không hợp lệ.')
    rq.con.execute('UPDATE users SET status=? WHERE id=?', (st, uid))
    if st == 'locked':
        rq.con.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
    audit(rq, action, 'user:%d' % uid, {'status': st})
    return {'ok': True}


def teacher_account(rq):
    u = rq.con.execute("SELECT * FROM users WHERE id=? AND role='teacher'", (rq.pid(),)).fetchone()
    if not u:
        raise ApiError(404, 'Không tìm thấy giáo viên.')
    return u


@route('POST', '/api/a/teachers/<id>/reset', A, use_tx=False)
def a_teacher_reset(rq):
    return reset_account(rq, teacher_account(rq)['id'], 'teacher.reset')


@route('POST', '/api/a/teachers/<id>/status', A)
def a_teacher_status(rq):
    return set_account_status(rq, teacher_account(rq)['id'], 'teacher.status')


@route('GET', '/api/a/audit', A)
def a_audit(rq):
    return {'events': rows(rq.con.execute(
        'SELECT a.id, a.action, a.target, a.meta, a.at, u.name actor, u.login_id FROM audit a '
        'LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 200'))}


# ───────────────────────── lớp học, học sinh ─────────────────────────
def own_class(rq, cid):
    c = rq.con.execute('SELECT * FROM classes WHERE id=? AND teacher_id=?', (cid, rq.uid)).fetchone()
    if not c:
        raise ApiError(404, 'Không tìm thấy lớp.')
    return c


def own_student(rq, sid):
    u = rq.con.execute(
        "SELECT u.* FROM users u WHERE u.id=? AND u.role='student' AND (u.created_by=? OR EXISTS("
        "SELECT 1 FROM enrollments e JOIN classes c ON c.id=e.class_id "
        "WHERE e.student_id=u.id AND c.teacher_id=?))", (sid, rq.uid, rq.uid)).fetchone()
    if not u:
        raise ApiError(404, 'Không tìm thấy học sinh.')
    return u


@route('GET', '/api/t/classes', T)
def t_classes(rq):
    return {'classes': rows(rq.con.execute(
        'SELECT c.id, c.name, c.year, c.created_at, '
        '(SELECT COUNT(*) FROM enrollments e WHERE e.class_id=c.id) students '
        'FROM classes c WHERE c.teacher_id=? ORDER BY c.name', (rq.uid,)))}


@route('POST', '/api/t/classes', T)
def t_class_create(rq):
    name = txt(rq.body.get('name'), 60, True, 'tên lớp')
    cur = rq.con.execute('INSERT INTO classes(name, year, teacher_id, created_at) VALUES(?,?,?,?)',
                         (name, txt(rq.body.get('year'), 20), rq.uid, now()))
    return {'id': cur.lastrowid}


@route('PUT', '/api/t/classes/<id>', T)
def t_class_update(rq):
    c = own_class(rq, rq.pid())
    rq.con.execute('UPDATE classes SET name=?, year=? WHERE id=?',
                   (txt(rq.body.get('name'), 60, True, 'tên lớp'), txt(rq.body.get('year'), 20), c['id']))
    return {'ok': True}


@route('DELETE', '/api/t/classes/<id>', T)
def t_class_delete(rq):
    c = own_class(rq, rq.pid())
    if rq.con.execute('SELECT 1 FROM enrollments WHERE class_id=?', (c['id'],)).fetchone():
        raise ApiError(409, 'Lớp còn học sinh. Hãy gỡ học sinh khỏi lớp trước khi xoá.')
    rq.con.execute('DELETE FROM classes WHERE id=?', (c['id'],))
    audit(rq, 'class.delete', c['name'])
    return {'ok': True}


@route('GET', '/api/t/classes/<id>', T)
def t_class_detail(rq):
    c = own_class(rq, rq.pid())
    students = rows(rq.con.execute(
        'SELECT u.id, u.login_id, u.name, u.status, u.must_change FROM enrollments e '
        'JOIN users u ON u.id=e.student_id WHERE e.class_id=? ORDER BY u.login_id', (c['id'],)))
    return {'class': dict(c), 'students': students}


@route('POST', '/api/t/classes/<id>/students', T, use_tx=False)
def t_students_add(rq):
    c = own_class(rq, rq.pid())
    names = rq.body.get('names')
    if not isinstance(names, list):
        raise ApiError(400, 'Danh sách học sinh không hợp lệ.')
    names = [n for n in (txt(n, 80, field='họ tên') for n in names) if n]
    if not names or len(names) > 100:
        raise ApiError(400, 'Mỗi lần thêm từ 1 đến 100 học sinh.')
    prepared = []
    for nm in names:                       # băm mật khẩu ngoài giao dịch để không khoá CSDL lâu
        pw = gen_password()
        prepared.append((nm, pw, hash_pw(pw)))
    prefix = slug(c['name']) or 'hs'
    out = []
    with tx(rq.con):
        n = rq.con.execute('SELECT COUNT(*) FROM users WHERE login_id LIKE ?', (prefix + '-%',)).fetchone()[0]
        for nm, pw, h in prepared:
            while True:
                n += 1
                lid = '%s-%03d' % (prefix, n)
                if not rq.con.execute('SELECT 1 FROM users WHERE login_id=?', (lid,)).fetchone():
                    break
            cur = rq.con.execute("INSERT INTO users(login_id,name,role,pw,must_change,created_by,created_at) "
                                 "VALUES(?,?,'student',?,1,?,?)", (lid, nm, h, rq.uid, now()))
            rq.con.execute('INSERT INTO enrollments VALUES(?,?)', (c['id'], cur.lastrowid))
            out.append({'login_id': lid, 'name': nm, 'password': pw})
        audit(rq, 'student.create', 'class:%s' % c['name'], {'count': len(out)})
    return {'created': out}


@route('DELETE', '/api/t/classes/<id>/students/<sid>', T)
def t_student_remove(rq):
    c = own_class(rq, rq.pid())
    rq.con.execute('DELETE FROM enrollments WHERE class_id=? AND student_id=?', (c['id'], rq.pid('sid')))
    audit(rq, 'student.unenroll', 'class:%s' % c['name'], {'student': rq.pid('sid')})
    return {'ok': True}


@route('PUT', '/api/t/students/<id>', T)
def t_student_rename(rq):
    u = own_student(rq, rq.pid())
    rq.con.execute('UPDATE users SET name=? WHERE id=?', (txt(rq.body.get('name'), 80, True, 'họ tên'), u['id']))
    return {'ok': True}


@route('POST', '/api/t/students/<id>/reset', T, use_tx=False)
def t_student_reset(rq):
    return reset_account(rq, own_student(rq, rq.pid())['id'], 'student.reset')


@route('POST', '/api/t/students/<id>/status', T)
def t_student_status(rq):
    return set_account_status(rq, own_student(rq, rq.pid())['id'], 'student.status')


# ───────────────────────── ngân hàng câu hỏi ─────────────────────────
def clean_question(b):
    if not isinstance(b, dict):
        raise ApiError(400, 'Câu hỏi không hợp lệ.')
    qtype, level = b.get('type'), b.get('level')
    if qtype not in TYPES:
        raise ApiError(400, 'Dạng câu hỏi không hợp lệ.')
    if level not in LEVELS:
        raise ApiError(400, 'Mức độ phải là NB, TH hoặc VD.')
    q = {
        'grade': num(b.get('grade'), 10, 12, 'khối lớp'), 'level': level, 'type': qtype,
        'chapter': txt(b.get('chapter'), 150, field='chương'), 'topic': txt(b.get('topic'), 150, field='chủ đề'),
        'outcome': txt(b.get('outcome'), 500, field='yêu cầu cần đạt'),
        'stem': txt(b.get('stem'), 4000, True, 'nội dung câu hỏi'),
        'explanation': txt(b.get('explanation'), 4000, field='lời giải'),
        'source': txt(b.get('source'), 300, field='nguồn'),
        'status': 'approved' if b.get('status') == 'approved' else 'draft',
    }
    if qtype == 'single_choice':
        ch = b.get('choices')
        if not isinstance(ch, list) or not (2 <= len(ch) <= 6):
            raise ApiError(400, 'Câu trắc nghiệm cần từ 2 đến 6 phương án.')
        choices = [{'id': 'ABCDEF'[i], 'text': txt(c, 1000, True, 'phương án %s' % 'ABCDEF'[i])} for i, c in enumerate(ch)]
        correct = str(b.get('correct') or '').upper()
        if correct not in [c['id'] for c in choices]:
            raise ApiError(400, 'Chưa chọn đáp án đúng.')
        q['payload'], q['answer_key'] = {'choices': choices}, {'correct': correct}
    elif qtype == 'true_false':
        st = b.get('statements')
        if not isinstance(st, list) or len(st) != 4:
            raise ApiError(400, 'Câu đúng/sai cần đúng 4 mệnh đề a, b, c, d.')
        sts, key = [], {}
        for i, s in enumerate(st):
            if not isinstance(s, dict) or not isinstance(s.get('answer'), bool):
                raise ApiError(400, 'Mệnh đề %s chưa chọn Đúng/Sai.' % 'abcd'[i])
            sts.append({'id': 'abcd'[i], 'text': txt(s.get('text'), 1000, True, 'mệnh đề %s' % 'abcd'[i])})
            key['abcd'[i]] = s['answer']
        q['payload'], q['answer_key'] = {'statements': sts}, key
    else:
        a = b.get('answer') if isinstance(b.get('answer'), dict) else {}
        if a.get('mode') == 'text':
            acc = [txt(x, 200) for x in (a.get('accepts') or []) if txt(x, 200)]
            if not acc or len(acc) > 20:
                raise ApiError(400, 'Cần nhập từ 1 đến 20 đáp án được chấp nhận.')
            key = {'mode': 'text', 'accepts': acc}
        else:
            val = parse_num(a.get('value'))
            tol = parse_num(a.get('tol') if a.get('tol') not in (None, '') else 0)
            if val is None or tol is None or tol < 0:
                raise ApiError(400, 'Đáp án số hoặc sai số cho phép không hợp lệ.')
            key = {'mode': 'number', 'value': str(val), 'tol': str(tol)}
        q['payload'], q['answer_key'] = {}, key
    return q


def q_out(r):
    d = dict(r)
    d['payload'] = json.loads(d['payload'])
    d['answer_key'] = json.loads(d['answer_key'])
    return d


def insert_question(rq, q):
    t = now()
    return rq.con.execute(
        'INSERT INTO questions(owner_id,status,grade,chapter,topic,outcome,level,type,stem,payload,answer_key,'
        'explanation,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (rq.uid, q['status'], q['grade'], q['chapter'], q['topic'], q['outcome'], q['level'], q['type'], q['stem'],
         json.dumps(q['payload'], ensure_ascii=False), json.dumps(q['answer_key'], ensure_ascii=False),
         q['explanation'], q['source'], t, t)).lastrowid


@route('GET', '/api/t/questions', T)
def t_questions(rq):
    where, args = ['owner_id=?'], [rq.uid]
    for f in ('grade', 'chapter', 'level', 'type', 'status'):
        v = rq.q(f)
        if v != '':
            where.append('%s=?' % f)
            args.append(v)
    kw = rq.q('q').strip()
    if kw:
        where.append("stem LIKE ? ESCAPE '\\'")
        args.append('%' + kw.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
    w = ' AND '.join(where)
    try:
        limit = max(1, min(300, int(rq.q('limit', '50'))))
        offset = max(0, int(rq.q('offset', '0')))
    except ValueError:
        raise ApiError(400, 'Tham số phân trang không hợp lệ.')
    total = rq.con.execute('SELECT COUNT(*) FROM questions WHERE ' + w, args).fetchone()[0]
    cur = rq.con.execute('SELECT * FROM questions WHERE %s ORDER BY id DESC LIMIT ? OFFSET ?' % w, args + [limit, offset])
    return {'total': total, 'items': [q_out(r) for r in cur.fetchall()]}


@route('GET', '/api/t/questions/facets', T)
def t_facets(rq):
    return {'facets': rows(rq.con.execute(
        'SELECT grade, chapter, level, type, status, COUNT(*) n FROM questions WHERE owner_id=? '
        'GROUP BY grade, chapter, level, type, status', (rq.uid,)))}


@route('POST', '/api/t/questions', T)
def t_question_create(rq):
    return {'id': insert_question(rq, clean_question(rq.body))}


@route('POST', '/api/t/questions/import', T)
def t_question_import(rq):
    items = rq.body.get('questions')
    if not isinstance(items, list) or not items or len(items) > 500:
        raise ApiError(400, 'Mỗi lần nhập từ 1 đến 500 câu.')
    cleaned = []
    for i, it in enumerate(items):
        try:
            q = clean_question(it)
        except ApiError as e:
            raise ApiError(400, 'Câu thứ %d: %s' % (i + 1, e.msg))
        q['status'] = 'draft'              # câu nhập hàng loạt luôn chờ giáo viên duyệt
        cleaned.append(q)
    for q in cleaned:
        insert_question(rq, q)
    audit(rq, 'question.import', '', {'count': len(cleaned)})
    return {'imported': len(cleaned)}


def id_list(v, maxn=500):
    if not isinstance(v, list) or not v or len(v) > maxn or not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
        raise ApiError(400, 'Danh sách không hợp lệ.')
    return v


@route('POST', '/api/t/questions/bulk', T)
def t_question_bulk(rq):
    ids, act = id_list(rq.body.get('ids')), rq.body.get('action')
    marks = ','.join('?' * len(ids))
    if act in ('approve', 'draft'):
        rq.con.execute("UPDATE questions SET status=?, updated_at=? WHERE owner_id=? AND id IN (%s)" % marks,
                       ['approved' if act == 'approve' else 'draft', now(), rq.uid] + ids)
    elif act == 'delete':
        rq.con.execute('DELETE FROM exam_questions WHERE snapshot IS NULL AND question_id IN '
                       '(SELECT id FROM questions WHERE owner_id=? AND id IN (%s))' % marks, [rq.uid] + ids)
        rq.con.execute('DELETE FROM questions WHERE owner_id=? AND id IN (%s)' % marks, [rq.uid] + ids)
        audit(rq, 'question.delete', '', {'count': len(ids)})
    else:
        raise ApiError(400, 'Thao tác không hợp lệ.')
    return {'ok': True}


@route('PUT', '/api/t/questions/<id>', T)
def t_question_update(rq):
    qid = rq.pid()
    if not rq.con.execute('SELECT 1 FROM questions WHERE id=? AND owner_id=?', (qid, rq.uid)).fetchone():
        raise ApiError(404, 'Không tìm thấy câu hỏi.')
    q = clean_question(rq.body)
    rq.con.execute(
        'UPDATE questions SET status=?,grade=?,chapter=?,topic=?,outcome=?,level=?,type=?,stem=?,payload=?,'
        'answer_key=?,explanation=?,source=?,version=version+1,updated_at=? WHERE id=?',
        (q['status'], q['grade'], q['chapter'], q['topic'], q['outcome'], q['level'], q['type'], q['stem'],
         json.dumps(q['payload'], ensure_ascii=False), json.dumps(q['answer_key'], ensure_ascii=False),
         q['explanation'], q['source'], now(), qid))
    return {'ok': True}


# ───────────────────────── đề thi ─────────────────────────
def own_exam(rq, eid):
    e = rq.con.execute('SELECT * FROM exams WHERE id=? AND owner_id=?', (eid, rq.uid)).fetchone()
    if not e:
        raise ApiError(404, 'Không tìm thấy đề.')
    return e


def exam_fields(b, draft):
    f = {
        'title': txt(b.get('title'), 200, True, 'tên đề'),
        'description': txt(b.get('description'), 2000, field='ghi chú'),
        'start_at': ts(b.get('start_at'), 'thời điểm mở'), 'end_at': ts(b.get('end_at'), 'thời điểm đóng'),
        'duration_min': num(b.get('duration_min'), 1, 600, 'thời gian làm bài'),
        'max_attempts': num(b.get('max_attempts'), 1, 20, 'số lượt làm', 1),
        'show_result': b.get('show_result') if b.get('show_result') in SHOW else 'score',
    }
    if f['start_at'] and f['end_at'] and f['end_at'] <= f['start_at']:
        raise ApiError(400, 'Thời điểm đóng phải sau thời điểm mở.')
    if draft:
        f['shuffle_q'], f['shuffle_opt'] = flag(b.get('shuffle_q')), flag(b.get('shuffle_opt'))
        f['tf_policy'] = 'per_item' if b.get('tf_policy') == 'per_item' else 'scale'
    return f


def set_exam_classes(rq, eid, class_ids):
    ids = id_list(class_ids, 50) if class_ids else []
    for cid in ids:
        own_class(rq, cid)
    rq.con.execute('DELETE FROM exam_classes WHERE exam_id=?', (eid,))
    for cid in dict.fromkeys(ids):
        rq.con.execute('INSERT INTO exam_classes VALUES(?,?)', (eid, cid))


def set_exam_items(rq, eid, items):
    if not isinstance(items, list) or len(items) > 200:
        raise ApiError(400, 'Danh sách câu hỏi không hợp lệ (tối đa 200 câu).')
    seen, clean = set(), []
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get('question_id'), int):
            raise ApiError(400, 'Câu hỏi trong đề không hợp lệ.')
        qid = it['question_id']
        if qid in seen:
            continue
        seen.add(qid)
        r = rq.con.execute('SELECT type FROM questions WHERE id=? AND owner_id=?', (qid, rq.uid)).fetchone()
        if not r:
            raise ApiError(400, 'Có câu hỏi không còn trong ngân hàng.')
        clean.append((TYPES.index(r['type']), qid, num(it.get('points'), 0.01, 100, 'điểm của câu', integer=False)))
    clean.sort(key=lambda x: x[0])          # luôn xếp Phần I → II → III, giữ thứ tự trong từng phần
    rq.con.execute('DELETE FROM exam_questions WHERE exam_id=?', (eid,))
    for i, (_, qid, pts) in enumerate(clean):
        rq.con.execute('INSERT INTO exam_questions(exam_id, question_id, order_index, points) VALUES(?,?,?,?)',
                       (eid, qid, i, round(pts, 2)))


def create_exam(rq, f):
    return rq.con.execute(
        'INSERT INTO exams(owner_id,title,description,start_at,end_at,duration_min,max_attempts,shuffle_q,'
        'shuffle_opt,show_result,tf_policy,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (rq.uid, f['title'], f['description'], f['start_at'], f['end_at'], f['duration_min'], f['max_attempts'],
         f['shuffle_q'], f['shuffle_opt'], f['show_result'], f['tf_policy'], now())).lastrowid


@route('GET', '/api/t/exams', T)
def t_exams(rq):
    sweep(rq.con, 'AND exam_id IN (SELECT id FROM exams WHERE owner_id=?)', (rq.uid,))
    return {'exams': rows(rq.con.execute(
        "SELECT e.*, (SELECT COUNT(*) FROM exam_questions q WHERE q.exam_id=e.id) nq, "
        "(SELECT COALESCE(SUM(points),0) FROM exam_questions q WHERE q.exam_id=e.id) total, "
        "(SELECT COUNT(*) FROM attempts a WHERE a.exam_id=e.id AND a.status='submitted') nsub, "
        "(SELECT COUNT(*) FROM attempts a WHERE a.exam_id=e.id AND a.status='in_progress') ndoing, "
        "(SELECT GROUP_CONCAT(c.name, ', ') FROM exam_classes x JOIN classes c ON c.id=x.class_id "
        " WHERE x.exam_id=e.id) classes FROM exams e WHERE e.owner_id=? ORDER BY e.id DESC", (rq.uid,)))}


@route('POST', '/api/t/exams', T)
def t_exam_create(rq):
    eid = create_exam(rq, exam_fields(rq.body, True))
    set_exam_classes(rq, eid, rq.body.get('class_ids'))
    set_exam_items(rq, eid, rq.body.get('items') or [])
    return {'id': eid}


@route('GET', '/api/t/exams/<id>', T)
def t_exam_detail(rq):
    e = own_exam(rq, rq.pid())
    items = []
    for r in rq.con.execute(
            'SELECT x.id eq_id, x.question_id, x.points, x.snapshot, q.type, q.stem, q.level, q.chapter, q.status '
            'FROM exam_questions x LEFT JOIN questions q ON q.id=x.question_id WHERE x.exam_id=? '
            'ORDER BY x.order_index', (e['id'],)):
        d = dict(r)
        snap = json.loads(d.pop('snapshot')) if d['snapshot'] else None
        if snap:
            d.update(type=snap['type'], stem=snap['stem'], level=snap.get('level'), chapter=snap.get('chapter'),
                     status='approved')
        items.append(d)
    return {'exam': dict(e), 'items': items,
            'class_ids': [r[0] for r in rq.con.execute('SELECT class_id FROM exam_classes WHERE exam_id=?', (e['id'],))],
            'attempts': rq.con.execute('SELECT COUNT(*) FROM attempts WHERE exam_id=?', (e['id'],)).fetchone()[0]}


@route('PUT', '/api/t/exams/<id>', T)
def t_exam_update(rq):
    e = own_exam(rq, rq.pid())
    draft = e['status'] == 'draft'
    f = exam_fields(rq.body, draft)
    sets = ', '.join('%s=?' % k for k in f)
    rq.con.execute('UPDATE exams SET %s WHERE id=?' % sets, list(f.values()) + [e['id']])
    set_exam_classes(rq, e['id'], rq.body.get('class_ids'))
    if draft:
        set_exam_items(rq, e['id'], rq.body.get('items') or [])
    return {'ok': True}


@route('DELETE', '/api/t/exams/<id>', T)
def t_exam_delete(rq):
    e = own_exam(rq, rq.pid())
    n = rq.con.execute('SELECT COUNT(*) FROM attempts WHERE exam_id=?', (e['id'],)).fetchone()[0]
    rq.con.execute('DELETE FROM exams WHERE id=?', (e['id'],))
    audit(rq, 'exam.delete', e['title'], {'attempts_deleted': n})
    return {'ok': True}


@route('POST', '/api/t/exams/<id>/copy', T)
def t_exam_copy(rq):
    e = own_exam(rq, rq.pid())
    f = {k: e[k] for k in ('description', 'duration_min', 'max_attempts', 'shuffle_q', 'shuffle_opt',
                           'show_result', 'tf_policy')}
    f.update(title=(e['title'] + ' (bản sao)')[:200], start_at=None, end_at=None)
    eid = create_exam(rq, f)
    rq.con.execute(
        'INSERT INTO exam_questions(exam_id, question_id, order_index, points) '
        'SELECT ?, x.question_id, x.order_index, x.points FROM exam_questions x '
        'JOIN questions q ON q.id=x.question_id AND q.owner_id=? WHERE x.exam_id=?', (eid, rq.uid, e['id']))
    return {'id': eid}


@route('POST', '/api/t/exams/<id>/status', T)
def t_exam_status(rq):
    e = own_exam(rq, rq.pid())
    act, con = rq.body.get('action'), rq.con
    if act == 'publish' and e['status'] == 'draft':
        items = con.execute(
            'SELECT x.id, q.* FROM exam_questions x LEFT JOIN questions q ON q.id=x.question_id AND q.owner_id=? '
            'WHERE x.exam_id=? ORDER BY x.order_index', (rq.uid, e['id'])).fetchall()
        if not items:
            raise ApiError(409, 'Đề chưa có câu hỏi.')
        if not con.execute('SELECT 1 FROM exam_classes WHERE exam_id=?', (e['id'],)).fetchone():
            raise ApiError(409, 'Chưa chọn lớp được giao đề.')
        bad = sum(1 for r in items if r['stem'] is None or r['status'] != 'approved')
        if bad:
            raise ApiError(409, 'Còn %d câu chưa được duyệt (hoặc đã xoá). Hãy duyệt trước khi phát hành.' % bad)
        for r in items:                    # chụp lại câu hỏi; đáp án lưu riêng, không gửi cho học sinh
            snap = {'type': r['type'], 'stem': r['stem'], 'level': r['level'], 'chapter': r['chapter'],
                    'topic': r['topic'], 'grade': r['grade']}
            snap.update(json.loads(r['payload']))
            con.execute('UPDATE exam_questions SET snapshot=?, answer_key=?, explanation=? WHERE id=?',
                        (json.dumps(snap, ensure_ascii=False), r['answer_key'], r['explanation'], r[0]))
        con.execute("UPDATE exams SET status='open', published_at=? WHERE id=?", (now(), e['id']))
    elif act == 'unpublish' and e['status'] in ('open', 'closed'):
        if con.execute('SELECT 1 FROM attempts WHERE exam_id=?', (e['id'],)).fetchone():
            raise ApiError(409, 'Đề đã có học sinh làm bài nên không thể đưa về bản nháp.')
        con.execute('UPDATE exam_questions SET snapshot=NULL, answer_key=NULL, explanation=NULL WHERE exam_id=?', (e['id'],))
        con.execute("UPDATE exams SET status='draft', published_at=NULL WHERE id=?", (e['id'],))
    elif act == 'close' and e['status'] == 'open':
        con.execute("UPDATE exams SET status='closed' WHERE id=?", (e['id'],))
        for r in con.execute("SELECT id FROM attempts WHERE exam_id=? AND status='in_progress'", (e['id'],)).fetchall():
            finalize(con, r['id'], auto=True)
    elif act == 'reopen' and e['status'] == 'closed':
        con.execute("UPDATE exams SET status='open' WHERE id=?", (e['id'],))
    else:
        raise ApiError(409, 'Không thực hiện được thao tác này ở trạng thái hiện tại của đề.')
    audit(rq, 'exam.' + act, e['title'])
    return {'ok': True}


# ───────────────────────── tạo đề từ ma trận ─────────────────────────
def matrix_plan(rq, body, seed=None):
    grade = num(body.get('grade'), 10, 12, 'khối lớp')
    raw = body.get('rows')
    if not isinstance(raw, list) or not raw or len(raw) > 100:
        raise ApiError(400, 'Ma trận cần từ 1 đến 100 dòng.')
    merged = {}
    for r in raw:
        if not isinstance(r, dict) or r.get('type') not in TYPES or r.get('level') not in LEVELS + ('*',):
            raise ApiError(400, 'Có dòng ma trận không hợp lệ.')
        key = (txt(r.get('chapter'), 150) or '*', r['level'], r['type'])
        merged[key] = merged.get(key, 0) + num(r.get('count'), 1, 100, 'số câu')
    rng = random.Random(seed)
    chosen, out = set(), {}
    for key in sorted(merged, key=lambda k: (k[0] == '*') + (k[1] == '*')):   # dòng cụ thể chọn trước
        chapter, level, qtype = key
        where, args = ["owner_id=? AND status='approved' AND grade=? AND type=?"], [rq.uid, grade, qtype]
        if chapter != '*':
            where.append('chapter=?')
            args.append(chapter)
        if level != '*':
            where.append('level=?')
            args.append(level)
        pool = [r[0] for r in rq.con.execute('SELECT id FROM questions WHERE %s ORDER BY id' % ' AND '.join(where), args)
                if r[0] not in chosen]
        need = merged[key]
        picked = rng.sample(pool, need) if len(pool) >= need else []
        chosen.update(picked)
        out[key] = {'chapter': chapter, 'level': level, 'type': qtype, 'count': need, 'available': len(pool),
                    'short': max(0, need - len(pool)), 'picked': picked}
    return grade, [out[k] for k in merged]


@route('POST', '/api/t/matrix/check', T)
def t_matrix_check(rq):
    _, plan = matrix_plan(rq, rq.body)
    for p in plan:
        p.pop('picked')
    return {'rows': plan, 'ok': not any(p['short'] for p in plan)}


@route('POST', '/api/t/matrix/generate', T)
def t_matrix_generate(rq):
    seed = rq.body.get('seed')
    seed = seed if isinstance(seed, int) and not isinstance(seed, bool) else secrets.randbelow(10 ** 9)
    grade, plan = matrix_plan(rq, rq.body, seed)
    if any(p['short'] for p in plan):
        raise ApiError(409, 'Ngân hàng chưa đủ câu đã duyệt cho ma trận này. Bấm "Kiểm tra ma trận" để xem dòng thiếu.')
    pts = rq.body.get('points') if isinstance(rq.body.get('points'), dict) else {}
    default = {'single_choice': 0.25, 'true_false': 1, 'short_answer': 0.25}
    f = exam_fields({'title': rq.body.get('title'), 'duration_min': rq.body.get('duration_min') or 50,
                     'description': ''}, True)
    eid = create_exam(rq, f)
    items = [{'question_id': qid, 'points': pts.get(p['type']) or default[p['type']]} for p in plan for qid in p['picked']]
    set_exam_items(rq, eid, items)
    audit(rq, 'exam.matrix', f['title'], {'seed': seed, 'questions': len(items)})
    return {'id': eid, 'seed': seed, 'questions': len(items)}


# ───────────────────────── chấm điểm ─────────────────────────
def parse_num(v):
    if isinstance(v, bool) or v is None:
        return None
    s = str(v).strip().replace(' ', '').replace(',', '.').replace('−', '-')
    if not re.match(r'^-?\d+(\.\d+)?$', s) or len(s) > 30:
        return None
    return Decimal(s)


def norm_text(v):
    return ' '.join(unicodedata.normalize('NFC', str(v)).casefold().split())


TF_SCALE = {0: Decimal(0), 1: Decimal('0.1'), 2: Decimal('0.25'), 3: Decimal('0.5'), 4: Decimal(1)}


def grade_one(qtype, key, ans, points, tf_policy):
    p = Decimal(str(points))
    if ans is None or ans == '':
        return Decimal(0)
    if qtype == 'single_choice':
        return p if ans == key.get('correct') else Decimal(0)
    if qtype == 'true_false':
        if not isinstance(ans, dict):
            return Decimal(0)
        ok = sum(1 for k, v in key.items() if ans.get(k) is v)
        frac = Decimal(ok) / Decimal(len(key)) if tf_policy == 'per_item' else TF_SCALE.get(ok, Decimal(0))
        return (p * frac).quantize(Decimal('0.01'), ROUND_HALF_UP)
    if key.get('mode') == 'text':
        return p if norm_text(ans) in {norm_text(a) for a in key.get('accepts', [])} else Decimal(0)
    x = parse_num(ans)
    if x is None:
        return Decimal(0)
    return p if abs(x - Decimal(key['value'])) <= Decimal(key.get('tol', '0')) else Decimal(0)


def finalize(con, att_id, auto=False):
    """Chấm và khoá một lượt làm bài. Gọi nhiều lần vẫn chỉ chấm một lần."""
    own = not con.in_transaction
    if own:
        con.execute('BEGIN IMMEDIATE')
    try:
        a = con.execute('SELECT * FROM attempts WHERE id=?', (att_id,)).fetchone()
        if a and a['status'] == 'in_progress':
            ex = con.execute('SELECT tf_policy FROM exams WHERE id=?', (a['exam_id'],)).fetchone()
            saved = {r['eq_id']: json.loads(r['answer']) for r in
                     con.execute('SELECT eq_id, answer FROM attempt_answers WHERE attempt_id=?', (att_id,))}
            total = mx = Decimal(0)
            t = now()
            for q in con.execute('SELECT id, points, snapshot, answer_key FROM exam_questions WHERE exam_id=?',
                                 (a['exam_id'],)).fetchall():
                ans = saved.get(q['id'])
                aw = grade_one(json.loads(q['snapshot'])['type'], json.loads(q['answer_key']), ans, q['points'],
                               ex['tf_policy'])
                total += aw
                mx += Decimal(str(q['points']))
                con.execute('INSERT INTO attempt_answers(attempt_id, eq_id, answer, saved_at, awarded) VALUES(?,?,?,?,?) '
                            'ON CONFLICT(attempt_id, eq_id) DO UPDATE SET awarded=excluded.awarded',
                            (att_id, q['id'], json.dumps(ans), t, float(aw)))
            con.execute("UPDATE attempts SET status='submitted', submitted_at=?, score=?, max_score=?, auto=? "
                        "WHERE id=? AND status='in_progress'",
                        (min(t, a['deadline_at'] + GRACE), float(total), float(mx), 1 if auto else 0, att_id))
        if own:
            con.execute('COMMIT')
    except BaseException:
        if own:
            con.execute('ROLLBACK')
        raise


def sweep(con, extra='', args=()):
    """Tự nộp các lượt đã quá giờ."""
    for r in con.execute("SELECT id FROM attempts WHERE status='in_progress' AND deadline_at < ? " + extra,
                         (now() - GRACE,) + tuple(args)).fetchall():
        finalize(con, r['id'], auto=True)


def attempt_detail(con, a):
    """Bài làm kèm đáp án — chỉ gọi khi người xem được phép thấy đáp án."""
    layout = json.loads(a['layout'])
    eqs = {r['id']: r for r in con.execute('SELECT * FROM exam_questions WHERE exam_id=?', (a['exam_id'],))}
    ans = {r['eq_id']: r for r in con.execute('SELECT * FROM attempt_answers WHERE attempt_id=?', (a['id'],))}
    out = []
    for qid in layout['q']:
        r = eqs.get(qid)
        if not r:
            continue
        snap, key = json.loads(r['snapshot']), json.loads(r['answer_key'])
        got = ans.get(qid)
        item = {'type': snap['type'], 'stem': snap['stem'], 'points': r['points'], 'key': key,
                'explanation': r['explanation'] or '', 'answer': json.loads(got['answer']) if got else None,
                'awarded': got['awarded'] if got else 0}
        if snap['type'] == 'single_choice':
            cm = {c['id']: c['text'] for c in snap['choices']}
            order = layout['opt'].get(str(qid)) or [c['id'] for c in snap['choices']]
            item['choices'] = [{'id': c, 'text': cm[c]} for c in order]
        elif snap['type'] == 'true_false':
            item['statements'] = snap['statements']
        out.append(item)
    return out


# ───────────────────────── kết quả (giáo viên) ─────────────────────────
@route('GET', '/api/t/exams/<id>/results', T)
def t_results(rq):
    e = own_exam(rq, rq.pid())
    sweep(rq.con, 'AND exam_id=?', (e['id'],))
    return results_data(rq.con, e)


def results_data(con, e):
    atts = rows(con.execute(
        'SELECT a.id, a.student_id, a.attempt_no, a.started_at, a.submitted_at, a.status, a.score, a.max_score, a.auto, '
        'u.name, u.login_id, (SELECT c.name FROM enrollments n JOIN classes c ON c.id=n.class_id '
        ' JOIN exam_classes x ON x.class_id=c.id AND x.exam_id=a.exam_id WHERE n.student_id=a.student_id LIMIT 1) class_name '
        'FROM attempts a JOIN users u ON u.id=a.student_id WHERE a.exam_id=? '
        'ORDER BY class_name, u.login_id, a.attempt_no', (e['id'],)))
    missing = rows(con.execute(
        'SELECT DISTINCT u.id, u.login_id, u.name, c.name class_name FROM exam_classes x '
        'JOIN classes c ON c.id=x.class_id JOIN enrollments n ON n.class_id=c.id JOIN users u ON u.id=n.student_id '
        'WHERE x.exam_id=? AND NOT EXISTS(SELECT 1 FROM attempts a WHERE a.exam_id=x.exam_id AND a.student_id=u.id) '
        'ORDER BY c.name, u.login_id', (e['id'],)))
    best = {}
    for a in atts:
        if a['status'] == 'submitted' and a['max_score']:
            s10 = a['score'] / a['max_score'] * 10
            best[a['student_id']] = max(best.get(a['student_id'], 0), s10)
    vals = sorted(best.values())
    stats = None
    if vals:
        n = len(vals)
        hist = [0] * 10
        for v in vals:
            hist[min(9, int(v))] += 1
        stats = {'n': n, 'mean': round(sum(vals) / n, 2), 'max': round(vals[-1], 2), 'min': round(vals[0], 2),
                 'median': round((vals[(n - 1) // 2] + vals[n // 2]) / 2, 2), 'hist': hist,
                 'pass': sum(1 for v in vals if v >= 5)}
    agg = {}
    for r in con.execute("SELECT w.eq_id, w.awarded FROM attempt_answers w JOIN attempts a ON a.id=w.attempt_id "
                         "WHERE a.exam_id=? AND a.status='submitted'", (e['id'],)):
        agg.setdefault(r['eq_id'], []).append(r['awarded'] or 0)
    per_q = []
    for i, r in enumerate(con.execute('SELECT id, points, snapshot FROM exam_questions WHERE exam_id=? '
                                      'ORDER BY order_index', (e['id'],)).fetchall()):
        snap = json.loads(r['snapshot']) if r['snapshot'] else {}
        got = agg.get(r['id'], [])
        per_q.append({'no': i + 1, 'type': snap.get('type'), 'level': snap.get('level'), 'stem': snap.get('stem', ''),
                      'points': r['points'], 'n': len(got), 'full': sum(1 for g in got if g >= r['points'] - 1e-4),
                      'avg': round(sum(got) / len(got), 2) if got else 0})
    return {'exam': dict(e), 'attempts': atts, 'missing': missing, 'stats': stats, 'per_question': per_q}


def csv_cell(v):
    s = '' if v is None else str(v)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t') else s


@route('GET', '/api/t/exams/<id>/results.csv', T)
def t_results_csv(rq):
    e = own_exam(rq, rq.pid())
    sweep(rq.con, 'AND exam_id=?', (e['id'],))
    d = results_data(rq.con, e)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['STT', 'Mã đăng nhập', 'Họ tên', 'Lớp', 'Lượt', 'Bắt đầu', 'Nộp bài', 'Trạng thái', 'Điểm', 'Điểm tối đa'])
    fmt = lambda t: time.strftime('%d/%m/%Y %H:%M', time.localtime(t)) if t else ''
    num_vn = lambda x: ('%g' % round(x, 2)).replace('.', ',') if x is not None else ''
    for i, a in enumerate(d['attempts']):
        w.writerow([i + 1, csv_cell(a['login_id']), csv_cell(a['name']), csv_cell(a['class_name']), a['attempt_no'],
                    fmt(a['started_at']), fmt(a['submitted_at']),
                    'Đã nộp' if a['status'] == 'submitted' else 'Đang làm', num_vn(a['score']), num_vn(a['max_score'])])
    for m in d['missing']:
        w.writerow(['', csv_cell(m['login_id']), csv_cell(m['name']), csv_cell(m['class_name']), '', '', '', 'Chưa làm', '', ''])
    audit(rq, 'results.export', e['title'])
    return Raw('text/csv; charset=utf-8', ('\ufeff' + buf.getvalue()).encode('utf-8'),
               [('Content-Disposition', 'attachment; filename="ket-qua-de-%d.csv"' % e['id'])])


@route('GET', '/api/t/attempts/<id>', T)
def t_attempt(rq):
    a = rq.con.execute('SELECT a.*, u.name, u.login_id FROM attempts a JOIN exams e ON e.id=a.exam_id '
                       'JOIN users u ON u.id=a.student_id WHERE a.id=? AND e.owner_id=?', (rq.pid(), rq.uid)).fetchone()
    if not a:
        raise ApiError(404, 'Không tìm thấy bài làm.')
    d = {k: a[k] for k in ('id', 'attempt_no', 'started_at', 'submitted_at', 'status', 'score', 'max_score', 'name', 'login_id', 'auto')}
    d['detail'] = attempt_detail(rq.con, a)
    return d


@route('GET', '/api/t/dashboard', T)
def t_dashboard(rq):
    c, uid = rq.con, rq.uid
    sweep(c, 'AND exam_id IN (SELECT id FROM exams WHERE owner_id=?)', (uid,))
    one = lambda sql, *a: c.execute(sql, a).fetchone()[0]
    return {
        'classes': one('SELECT COUNT(*) FROM classes WHERE teacher_id=?', uid),
        'students': one('SELECT COUNT(DISTINCT e.student_id) FROM enrollments e JOIN classes c ON c.id=e.class_id '
                        'WHERE c.teacher_id=?', uid),
        'questions': one("SELECT COUNT(*) FROM questions WHERE owner_id=? AND status='approved'", uid),
        'drafts': one("SELECT COUNT(*) FROM questions WHERE owner_id=? AND status='draft'", uid),
        'exams_open': one("SELECT COUNT(*) FROM exams WHERE owner_id=? AND status='open'", uid),
        'submitted': one("SELECT COUNT(*) FROM attempts a JOIN exams e ON e.id=a.exam_id "
                         "WHERE e.owner_id=? AND a.status='submitted'", uid),
        'recent': rows(c.execute(
            "SELECT a.id, a.exam_id, a.submitted_at, a.score, a.max_score, u.name, e.title FROM attempts a "
            "JOIN exams e ON e.id=a.exam_id JOIN users u ON u.id=a.student_id "
            "WHERE e.owner_id=? AND a.status='submitted' ORDER BY a.submitted_at DESC LIMIT 8", (uid,))),
        'live': rows(c.execute(
            'SELECT l.id, l.title, l.starts_at, l.duration_min, c.name class_name FROM live_sessions l '
            'JOIN classes c ON c.id=l.class_id WHERE l.teacher_id=? AND l.starts_at + l.duration_min*60 > ? '
            'ORDER BY l.starts_at LIMIT 4', (uid, now()))),
    }


# ───────────────────────── bài giảng, lịch trực tuyến, thông báo ─────────────────────────
KINDS = ('video', 'pdf', 'slide', 'link', 'note')


def lesson_fields(rq):
    b = rq.body
    c = own_class(rq, num(b.get('class_id'), 1, 10 ** 12, 'lớp'))
    kind = b.get('kind') if b.get('kind') in KINDS else 'link'
    f = (c['id'], txt(b.get('title'), 200, True, 'tên bài giảng'), kind,
         url_ok(b.get('url'), required=(kind != 'note')), txt(b.get('body'), 8000, field='nội dung'), flag(b.get('published')))
    return f


@route('GET', '/api/t/lessons', T)
def t_lessons(rq):
    return {'lessons': rows(rq.con.execute(
        'SELECT l.*, c.name class_name, (SELECT COUNT(*) FROM lesson_done d WHERE d.lesson_id=l.id) done, '
        '(SELECT COUNT(*) FROM enrollments e WHERE e.class_id=l.class_id) students '
        'FROM lessons l JOIN classes c ON c.id=l.class_id WHERE l.teacher_id=? ORDER BY l.id DESC', (rq.uid,)))}


@route('POST', '/api/t/lessons', T)
def t_lesson_create(rq):
    f = lesson_fields(rq)
    cur = rq.con.execute('INSERT INTO lessons(class_id,title,kind,url,body,published,teacher_id,created_at) '
                         'VALUES(?,?,?,?,?,?,?,?)', f + (rq.uid, now()))
    return {'id': cur.lastrowid}


@route('PUT', '/api/t/lessons/<id>', T)
def t_lesson_update(rq):
    f = lesson_fields(rq)
    cur = rq.con.execute('UPDATE lessons SET class_id=?,title=?,kind=?,url=?,body=?,published=? '
                         'WHERE id=? AND teacher_id=?', f + (rq.pid(), rq.uid))
    if not cur.rowcount:
        raise ApiError(404, 'Không tìm thấy bài giảng.')
    return {'ok': True}


@route('DELETE', '/api/t/lessons/<id>', T)
def t_lesson_delete(rq):
    rq.con.execute('DELETE FROM lessons WHERE id=? AND teacher_id=?', (rq.pid(), rq.uid))
    return {'ok': True}


def live_fields(rq):
    b = rq.body
    c = own_class(rq, num(b.get('class_id'), 1, 10 ** 12, 'lớp'))
    st = ts(b.get('starts_at'), 'giờ bắt đầu')
    if not st:
        raise ApiError(400, 'Chưa chọn giờ bắt đầu.')
    return (c['id'], txt(b.get('title'), 200, True, 'tên buổi học'), st, num(b.get('duration_min'), 5, 600, 'thời lượng', 45),
            url_ok(b.get('join_url'), 'liên kết phòng học', True), txt(b.get('note'), 2000, field='ghi chú'))


@route('GET', '/api/t/live', T)
def t_live(rq):
    return {'sessions': rows(rq.con.execute(
        'SELECT l.*, c.name class_name FROM live_sessions l JOIN classes c ON c.id=l.class_id '
        'WHERE l.teacher_id=? ORDER BY l.starts_at DESC', (rq.uid,)))}


@route('POST', '/api/t/live', T)
def t_live_create(rq):
    cur = rq.con.execute('INSERT INTO live_sessions(class_id,title,starts_at,duration_min,join_url,note,teacher_id) '
                         'VALUES(?,?,?,?,?,?,?)', live_fields(rq) + (rq.uid,))
    return {'id': cur.lastrowid}


@route('PUT', '/api/t/live/<id>', T)
def t_live_update(rq):
    cur = rq.con.execute('UPDATE live_sessions SET class_id=?,title=?,starts_at=?,duration_min=?,join_url=?,note=? '
                         'WHERE id=? AND teacher_id=?', live_fields(rq) + (rq.pid(), rq.uid))
    if not cur.rowcount:
        raise ApiError(404, 'Không tìm thấy buổi học.')
    return {'ok': True}


@route('DELETE', '/api/t/live/<id>', T)
def t_live_delete(rq):
    rq.con.execute('DELETE FROM live_sessions WHERE id=? AND teacher_id=?', (rq.pid(), rq.uid))
    return {'ok': True}


def news_fields(rq):
    b = rq.body
    return (txt(b.get('title'), 200, True, 'tiêu đề'), txt(b.get('body'), 8000, field='nội dung'),
            flag(b.get('pinned')), flag(b.get('published')))


def news_scope(rq):
    return ('1=1', ()) if rq.user['role'] == 'admin' else ('author_id=?', (rq.uid,))


@route('GET', '/api/t/news', T)
def t_news(rq):
    w, a = news_scope(rq)
    return {'news': rows(rq.con.execute(
        'SELECT n.*, u.name author FROM news n JOIN users u ON u.id=n.author_id WHERE %s '
        'ORDER BY n.pinned DESC, n.created_at DESC' % w.replace('author_id', 'n.author_id'), a))}


@route('POST', '/api/t/news', T)
def t_news_create(rq):
    cur = rq.con.execute('INSERT INTO news(title,body,pinned,published,author_id,created_at) VALUES(?,?,?,?,?,?)',
                         news_fields(rq) + (rq.uid, now()))
    return {'id': cur.lastrowid}


@route('PUT', '/api/t/news/<id>', T)
def t_news_update(rq):
    w, a = news_scope(rq)
    cur = rq.con.execute('UPDATE news SET title=?,body=?,pinned=?,published=? WHERE id=? AND ' + w,
                         news_fields(rq) + (rq.pid(),) + a)
    if not cur.rowcount:
        raise ApiError(404, 'Không tìm thấy thông báo.')
    return {'ok': True}


@route('DELETE', '/api/t/news/<id>', T)
def t_news_delete(rq):
    w, a = news_scope(rq)
    rq.con.execute('DELETE FROM news WHERE id=? AND ' + w, (rq.pid(),) + a)
    return {'ok': True}


# ───────────────────────── học sinh ─────────────────────────
def student_exam(rq, eid):
    e = rq.con.execute(
        "SELECT e.* FROM exams e WHERE e.id=? AND e.status IN('open','closed') AND EXISTS("
        "SELECT 1 FROM exam_classes x JOIN enrollments n ON n.class_id=x.class_id "
        "WHERE x.exam_id=e.id AND n.student_id=?)", (eid, rq.uid)).fetchone()
    if not e:
        raise ApiError(404, 'Không tìm thấy bài kiểm tra.')
    return e


def my_attempt(rq, aid):
    a = rq.con.execute('SELECT * FROM attempts WHERE id=? AND student_id=?', (aid, rq.uid)).fetchone()
    if not a:
        raise ApiError(404, 'Không tìm thấy bài làm.')
    return a


def can_see_answers(e):
    return e['show_result'] == 'answers' or (
        e['show_result'] == 'after_close' and (e['status'] == 'closed' or (e['end_at'] and now() >= e['end_at'])))


@route('GET', '/api/s/dashboard', S)
def s_dashboard(rq):
    c, uid, t = rq.con, rq.uid, now()
    sweep(c, 'AND student_id=?', (uid,))
    exams = []
    for e in c.execute(
            "SELECT e.*, u.name teacher, (SELECT COUNT(*) FROM exam_questions q WHERE q.exam_id=e.id) nq "
            "FROM exams e JOIN users u ON u.id=e.owner_id WHERE e.status IN('open','closed') AND EXISTS("
            "SELECT 1 FROM exam_classes x JOIN enrollments n ON n.class_id=x.class_id "
            "WHERE x.exam_id=e.id AND n.student_id=?) ORDER BY e.id DESC", (uid,)).fetchall():
        atts = []
        for a in c.execute('SELECT id, attempt_no, status, submitted_at, score, max_score FROM attempts '
                           'WHERE exam_id=? AND student_id=? ORDER BY attempt_no', (e['id'], uid)):
            d = dict(a)
            if e['show_result'] == 'none':
                d['score'] = d['max_score'] = None
            atts.append(d)
        doing = next((a['id'] for a in atts if a['status'] == 'in_progress'), None)
        window = e['status'] == 'open' and (not e['start_at'] or t >= e['start_at']) and (not e['end_at'] or t < e['end_at'])
        exams.append({
            'id': e['id'], 'title': e['title'], 'description': e['description'], 'teacher': e['teacher'],
            'start_at': e['start_at'], 'end_at': e['end_at'], 'duration_min': e['duration_min'],
            'max_attempts': e['max_attempts'], 'status': e['status'], 'nq': e['nq'], 'attempts': atts,
            'in_progress': doing, 'can_start': bool(window and not doing and len(atts) < e['max_attempts']),
            'upcoming': bool(e['status'] == 'open' and e['start_at'] and t < e['start_at'])})
    return {
        'exams': exams, 'server_now': t,
        'classes': rows(c.execute('SELECT c.id, c.name, c.year, u.name teacher FROM enrollments n '
                                  'JOIN classes c ON c.id=n.class_id JOIN users u ON u.id=c.teacher_id '
                                  'WHERE n.student_id=? ORDER BY c.name', (uid,))),
        'live': s_live(rq)['sessions'][:4],
        'lessons': s_lessons(rq)['lessons'][:5],
        'news': public_news(rq)['news'][:4],
    }


@route('GET', '/api/s/lessons', S)
def s_lessons(rq):
    return {'lessons': rows(rq.con.execute(
        'SELECT l.id, l.title, l.kind, l.url, l.body, l.created_at, c.name class_name, '
        'EXISTS(SELECT 1 FROM lesson_done d WHERE d.lesson_id=l.id AND d.student_id=?) done '
        'FROM lessons l JOIN classes c ON c.id=l.class_id JOIN enrollments n ON n.class_id=c.id AND n.student_id=? '
        'WHERE l.published=1 ORDER BY l.id DESC', (rq.uid, rq.uid)))}


@route('POST', '/api/s/lessons/<id>/done', S)
def s_lesson_done(rq):
    ok = rq.con.execute('SELECT 1 FROM lessons l JOIN enrollments n ON n.class_id=l.class_id AND n.student_id=? '
                        'WHERE l.id=? AND l.published=1', (rq.uid, rq.pid())).fetchone()
    if not ok:
        raise ApiError(404, 'Không tìm thấy bài giảng.')
    if flag(rq.body.get('done')):
        rq.con.execute('INSERT OR IGNORE INTO lesson_done VALUES(?,?,?)', (rq.pid(), rq.uid, now()))
    else:
        rq.con.execute('DELETE FROM lesson_done WHERE lesson_id=? AND student_id=?', (rq.pid(), rq.uid))
    return {'ok': True}


@route('GET', '/api/s/live', S)
def s_live(rq):
    return {'sessions': rows(rq.con.execute(
        'SELECT l.id, l.title, l.starts_at, l.duration_min, l.join_url, l.note, c.name class_name, u.name teacher '
        'FROM live_sessions l JOIN classes c ON c.id=l.class_id JOIN users u ON u.id=l.teacher_id '
        'JOIN enrollments n ON n.class_id=c.id AND n.student_id=? '
        'WHERE l.starts_at + l.duration_min*60 > ? ORDER BY l.starts_at', (rq.uid, now() - 3600)))}


def make_layout(con, e):
    qs = con.execute('SELECT id, snapshot FROM exam_questions WHERE exam_id=? ORDER BY order_index', (e['id'],)).fetchall()
    rng = random.SystemRandom()
    order = [q['id'] for q in qs]
    snaps = {q['id']: json.loads(q['snapshot']) for q in qs}
    if e['shuffle_q']:
        order = []
        for tp in TYPES:
            grp = [q['id'] for q in qs if snaps[q['id']]['type'] == tp]
            rng.shuffle(grp)
            order += grp
    opt = {}
    if e['shuffle_opt']:
        for qid, s in snaps.items():
            if s['type'] == 'single_choice':
                ids = [c['id'] for c in s['choices']]
                rng.shuffle(ids)
                opt[str(qid)] = ids
    return json.dumps({'q': order, 'opt': opt})


@route('POST', '/api/s/exams/<id>/start', S)
def s_start(rq):
    e, con, t = student_exam(rq, rq.pid()), rq.con, now()
    for r in con.execute("SELECT id, deadline_at FROM attempts WHERE exam_id=? AND student_id=? AND status='in_progress'",
                         (e['id'], rq.uid)).fetchall():
        if t <= r['deadline_at'] + GRACE:
            return {'attempt_id': r['id'], 'resumed': True}
        finalize(con, r['id'], auto=True)
    if e['status'] != 'open':
        raise ApiError(409, 'Bài kiểm tra đã đóng.')
    if e['start_at'] and t < e['start_at']:
        raise ApiError(409, 'Chưa đến giờ làm bài.')
    if e['end_at'] and t >= e['end_at']:
        raise ApiError(409, 'Đã hết hạn làm bài.')
    n = con.execute('SELECT COUNT(*) FROM attempts WHERE exam_id=? AND student_id=?', (e['id'], rq.uid)).fetchone()[0]
    if n >= e['max_attempts']:
        raise ApiError(409, 'Em đã dùng hết số lượt làm bài.')
    deadline = t + e['duration_min'] * 60
    if e['end_at']:
        deadline = min(deadline, e['end_at'])
    cur = con.execute('INSERT INTO attempts(exam_id, student_id, attempt_no, started_at, deadline_at, layout) '
                      'VALUES(?,?,?,?,?,?)', (e['id'], rq.uid, n + 1, t, deadline, make_layout(con, e)))
    return {'attempt_id': cur.lastrowid, 'resumed': False}


@route('GET', '/api/s/attempts/<id>', S)
def s_attempt(rq):
    a, con = my_attempt(rq, rq.pid()), rq.con
    if a['status'] == 'in_progress' and now() > a['deadline_at'] + GRACE:
        finalize(con, a['id'], auto=True)
        a = my_attempt(rq, a['id'])
    if a['status'] != 'in_progress':
        return {'status': a['status']}
    e = con.execute('SELECT title, duration_min FROM exams WHERE id=?', (a['exam_id'],)).fetchone()
    layout = json.loads(a['layout'])
    eqs = {r['id']: r for r in con.execute('SELECT id, points, snapshot FROM exam_questions WHERE exam_id=?', (a['exam_id'],))}
    qs = []
    for qid in layout['q']:                # chỉ gửi phần công khai của câu hỏi, không kèm đáp án
        r = eqs[qid]
        s = json.loads(r['snapshot'])
        item = {'id': qid, 'type': s['type'], 'points': r['points'], 'stem': s['stem']}
        if s['type'] == 'single_choice':
            cm = {c['id']: c['text'] for c in s['choices']}
            item['choices'] = [{'id': c, 'text': cm[c]} for c in (layout['opt'].get(str(qid)) or list(cm))]
        elif s['type'] == 'true_false':
            item['statements'] = s['statements']
        qs.append(item)
    saved = {str(r['eq_id']): json.loads(r['answer']) for r in
             con.execute('SELECT eq_id, answer FROM attempt_answers WHERE attempt_id=?', (a['id'],))}
    return {'status': 'in_progress', 'exam': dict(e), 'attempt_no': a['attempt_no'], 'deadline_at': a['deadline_at'],
            'server_now': now(), 'questions': qs, 'answers': saved}


def save_answers(con, a, answers):
    if not isinstance(answers, dict) or len(answers) > 300:
        raise ApiError(400, 'Dữ liệu bài làm không hợp lệ.')
    snaps = {str(r['id']): json.loads(r['snapshot']) for r in
             con.execute('SELECT id, snapshot FROM exam_questions WHERE exam_id=?', (a['exam_id'],))}
    t = now()
    for k, v in answers.items():
        s = snaps.get(str(k))
        if not s:
            continue
        if s['type'] == 'single_choice':
            v = v if v in [c['id'] for c in s['choices']] else None
        elif s['type'] == 'true_false':
            v = {x['id']: v[x['id']] for x in s['statements'] if isinstance(v.get(x['id']), bool)} if isinstance(v, dict) else None
        else:
            v = str(v).strip()[:100] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else None
        con.execute('INSERT INTO attempt_answers(attempt_id, eq_id, answer, saved_at) VALUES(?,?,?,?) '
                    'ON CONFLICT(attempt_id, eq_id) DO UPDATE SET answer=excluded.answer, saved_at=excluded.saved_at',
                    (a['id'], int(k), json.dumps(v, ensure_ascii=False), t))
    return t


@route('PUT', '/api/s/attempts/<id>/answers', S)
def s_save(rq):
    a = my_attempt(rq, rq.pid())
    if a['status'] != 'in_progress':
        return {'ok': False, 'status': 'submitted'}
    if now() > a['deadline_at'] + GRACE:
        finalize(rq.con, a['id'], auto=True)
        return {'ok': False, 'status': 'submitted'}
    return {'ok': True, 'saved_at': save_answers(rq.con, a, rq.body.get('answers'))}


@route('POST', '/api/s/attempts/<id>/submit', S)
def s_submit(rq):
    a = my_attempt(rq, rq.pid())
    if a['status'] == 'in_progress':       # nộp lần hai trở đi không chấm lại
        late = now() > a['deadline_at'] + GRACE
        if not late and isinstance(rq.body.get('answers'), dict):
            save_answers(rq.con, a, rq.body['answers'])
        finalize(rq.con, a['id'], auto=late)
    return {'ok': True}


@route('GET', '/api/s/attempts/<id>/result', S)
def s_result(rq):
    a, con = my_attempt(rq, rq.pid()), rq.con
    if a['status'] == 'in_progress':
        if now() <= a['deadline_at'] + GRACE:
            raise ApiError(409, 'Bài làm chưa nộp.')
        finalize(con, a['id'], auto=True)
        a = my_attempt(rq, a['id'])
    e = con.execute('SELECT * FROM exams WHERE id=?', (a['exam_id'],)).fetchone()
    out = {'exam': {'id': e['id'], 'title': e['title'], 'show_result': e['show_result']},
           'attempt_no': a['attempt_no'], 'submitted_at': a['submitted_at'], 'auto': a['auto'],
           'score': None, 'max_score': None, 'detail': None}
    if e['show_result'] != 'none':
        out['score'], out['max_score'] = a['score'], a['max_score']
    if can_see_answers(e):
        out['detail'] = attempt_detail(con, a)
    return out


# ───────────────────────── sao lưu dữ liệu (quản trị) ─────────────────────────
@route('GET', '/api/a/backup', A)
def a_backup(rq):
    """Tải về một bản sao nhất quán của cơ sở dữ liệu (không kèm phiên đăng nhập)."""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        dst = sqlite3.connect(tmp)
        rq.con.backup(dst)
        dst.execute('DELETE FROM sessions')
        dst.execute('DELETE FROM login_failures')
        dst.commit()
        dst.execute('PRAGMA journal_mode=DELETE')
        dst.execute('VACUUM')
        dst.close()
        with open(tmp, 'rb') as f:
            data = f.read()
    finally:
        for p in (tmp, tmp + '-wal', tmp + '-shm'):
            if os.path.exists(p):
                os.unlink(p)
    audit(rq, 'backup.download', '', {'bytes': len(data)})
    name = 'tdh-chemistry-saoluu-%s.db' % time.strftime('%Y%m%d-%H%M')
    return Raw('application/octet-stream', data, [('Content-Disposition', 'attachment; filename="%s"' % name)])


# ───────────────────────── xử lí yêu cầu (dùng chung cho http.server và WSGI) ─────────────────────────
SEC_HEADERS = [
    ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'same-origin'),
    ('Content-Security-Policy',
     "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
     "frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"),
]
OPEN_WHEN_MUST_CHANGE = ('/api/me', '/api/password', '/api/logout')


def base_headers(path):
    h = [('Cache-Control', 'no-store' if path.startswith('/api/') else 'no-cache')] + SEC_HEADERS
    if SECURE_COOKIE:
        h.append(('Strict-Transport-Security', 'max-age=31536000'))
    return h


def json_resp(status, obj, extra=()):
    return status, 'application/json; charset=utf-8', json.dumps(obj, ensure_ascii=False).encode('utf-8'), list(extra)


def static_resp(path):
    rel = 'index.html' if path in ('', '/') else path.lstrip('/')
    full = os.path.realpath(os.path.join(STATIC, rel))
    if not full.startswith(STATIC + os.sep) or not os.path.isfile(full):
        full = os.path.join(STATIC, 'index.html')
    if not os.path.isfile(full):
        return json_resp(404, {'error': 'Không tìm thấy.'})
    ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
    if ctype.startswith('text/') or ctype.endswith(('javascript', 'json')):
        ctype += '; charset=utf-8'
    with open(full, 'rb') as f:
        return 200, ctype, f.read(), []


def process(method, path, query, header, read_body, peer_ip):
    """Xử lí một yêu cầu. `header(tên)` trả giá trị tiêu đề hoặc None; `read_body(n)` đọc n byte thân yêu cầu.
    Trả về (mã trạng thái, kiểu nội dung, dữ liệu bytes, các tiêu đề bổ sung)."""
    if path == '/healthz':
        return 200, 'text/plain; charset=utf-8', b'ok', []
    if not path.startswith('/api/'):
        if method in ('GET', 'HEAD'):
            return static_resp(path)
        return json_resp(405, {'error': 'Không hỗ trợ.'})
    ip = peer_ip
    if TRUST_PROXY and header('X-Forwarded-For'):
        ip = header('X-Forwarded-For').split(',')[0].strip()[:64]
    con = db()
    rq = Rq(con, ip)
    try:
        rq.query = parse_qs(query or '')
        if method != 'GET':
            origin = header('Origin')
            if header('X-TDH') != '1' or (origin and urlparse(origin).netloc != header('Host')):
                raise ApiError(403, 'Yêu cầu không hợp lệ.')
            n = int(header('Content-Length') or 0)
            if n > MAX_BODY:
                raise ApiError(413, 'Dữ liệu gửi lên quá lớn.')
            raw = read_body(n) if n > 0 else b''
            rq.body = json.loads(raw.decode('utf-8')) if raw else {}
            if not isinstance(rq.body, dict):
                raise ApiError(400, 'Dữ liệu không hợp lệ.')
        m = re.search(r'(?:^|;\s*)%s=([A-Za-z0-9_-]+)' % COOKIE, header('Cookie') or '')
        if m:
            rq.token_hash = sha(m.group(1))
            rq.user = con.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token=? AND s.expires_at>? AND u.status='active'", (rq.token_hash, now())).fetchone()
        for mth, rx, roles, use_tx, fn in ROUTES:
            mt = rx.match(path) if mth == method else None
            if not mt:
                continue
            rq.params = mt.groupdict()
            if roles is not None:
                if not rq.user:
                    raise ApiError(401, 'Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.')
                if rq.user['must_change'] and path not in OPEN_WHEN_MUST_CHANGE:
                    raise ApiError(403, 'Cần đổi mật khẩu trước khi tiếp tục.', 'must_change')
                if rq.user['role'] not in roles:
                    raise ApiError(403, 'Tài khoản không có quyền thực hiện thao tác này.')
            if use_tx and method != 'GET':
                with tx(con):
                    out = fn(rq)
            else:
                out = fn(rq)
            break
        else:
            raise ApiError(404, 'Không tìm thấy.')
        extra = []
        if rq.set_cookie is not None:
            extra.append(('Set-Cookie', '%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s' % (
                COOKIE, rq.set_cookie, SESSION_TTL if rq.set_cookie else 0, '; Secure' if SECURE_COOKIE else '')))
        if isinstance(out, Raw):
            return 200, out.ctype, out.data, list(out.headers)
        return json_resp(200, out, extra)
    except ApiError as e:
        return json_resp(e.status, {'error': e.msg, 'code': e.code})
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return json_resp(400, {'error': 'Dữ liệu gửi lên không hợp lệ.'})
    except Exception:
        traceback.print_exc()
        return json_resp(500, {'error': 'Máy chủ gặp lỗi. Vui lòng thử lại.'})
    finally:
        con.close()


class Handler(BaseHTTPRequestHandler):
    """Máy chủ có sẵn của Python — dùng khi chạy trên máy cá nhân (python3 server.py)."""
    server_version, sys_version = 'TDH-Chemistry', ''
    timeout = 30

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1])[:1] in '45':
            sys.stderr.write('%s %s\n' % (self.log_date_time_string(), fmt % args))

    def dispatch(self, method):
        url = urlparse(self.path)
        try:
            status, ctype, data, extra = process(method, url.path, url.query, self.headers.get, self.rfile.read,
                                                 self.client_address[0])
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            for k, v in base_headers(url.path) + extra:
                self.send_header(k, v)
            self.end_headers()
            if method != 'HEAD':
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self): self.dispatch('GET')
    def do_HEAD(self): self.dispatch('HEAD')
    def do_POST(self): self.dispatch('POST')
    def do_PUT(self): self.dispatch('PUT')
    def do_DELETE(self): self.dispatch('DELETE')


def wsgi_app(environ, start_response):
    """Điểm vào WSGI — dùng khi chạy trên máy chủ Internet (gunicorn wsgi:application)."""
    from http.client import responses

    def header(name):
        key = name.upper().replace('-', '_')
        if key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            return environ.get(key) or None
        return environ.get('HTTP_' + key)

    method, path = environ.get('REQUEST_METHOD', 'GET'), environ.get('PATH_INFO') or '/'
    status, ctype, data, extra = process(method, path, environ.get('QUERY_STRING', ''), header,
                                         environ['wsgi.input'].read, environ.get('REMOTE_ADDR', ''))
    headers = [('Content-Type', ctype), ('Content-Length', str(len(data)))] + base_headers(path) + extra
    start_response('%d %s' % (status, responses.get(status, 'OK')), headers)
    return [b'' if method == 'HEAD' else data]


# ───────────────────────── khởi tạo ─────────────────────────
def init_db(demo=True):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = db()
    con.execute('PRAGMA journal_mode=%s' % ('DELETE' if os.environ.get('TDH_JOURNAL', '').upper() == 'DELETE' else 'WAL'))
    con.executescript(SCHEMA)
    created = None
    with tx(con):                           # kiểm tra trong giao dịch để hai tiến trình không cùng khởi tạo
        if con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            given = os.environ.get('TDH_ADMIN_PASSWORD') or ''
            pw = given if len(given) >= 8 else gen_password(12)
            shown = '(giá trị của biến môi trường TDH_ADMIN_PASSWORD trên máy chủ)' if pw == given else pw
            created = ['TĐH Chemistry — tài khoản ban đầu (tạo lúc %s)' % time.strftime('%d/%m/%Y %H:%M'), '',
                       'Giáo viên (quản trị):  mã đăng nhập = giaovien    mật khẩu = %s' % shown,
                       '  → Hệ thống yêu cầu đổi mật khẩu ở lần đăng nhập đầu tiên.', '']
            cur = con.execute("INSERT INTO users(login_id,name,role,pw,must_change,created_at) "
                              "VALUES('giaovien','Giáo viên','admin',?,1,?)", (hash_pw(pw), now()))
            if demo:
                import seed_demo
                for lid, spw, name in seed_demo.seed(con, cur.lastrowid, hash_pw, gen_password, now()):
                    created.append('Học sinh demo:  mã đăng nhập = %-10s mật khẩu = %s   (%s)' % (lid, spw, name))
            created += ['', 'Xoá tệp này sau khi đã đăng nhập và đổi mật khẩu. Không gửi tệp này cho người khác.']
    if created:
        path = os.path.join(os.path.dirname(DB_PATH), 'TAI_KHOAN_BAN_DAU.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(created) + '\n')
        os.chmod(path, 0o600)
        print('Đã tạo cơ sở dữ liệu mới. Tài khoản ban đầu ghi trong tệp:\n  ' + path)
    con.close()


def configure(data_dir=None, demo=None):
    """Chọn thư mục dữ liệu rồi khởi tạo CSDL. Thứ tự ưu tiên: tham số → biến TDH_DATA → thư mục data/ cạnh mã nguồn."""
    global DB_PATH, SECURE_COOKIE, TRUST_PROXY
    SECURE_COOKIE = os.environ.get('TDH_SECURE_COOKIE') == '1'
    TRUST_PROXY = os.environ.get('TDH_TRUST_PROXY') == '1'
    DB_PATH = os.path.join(os.path.abspath(data_dir or os.environ.get('TDH_DATA') or DATA), 'tdh.db')
    init_db(demo=(os.environ.get('TDH_NO_DEMO') != '1') if demo is None else demo)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description='TĐH Chemistry — LMS và thi trực tuyến')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8700)))
    ap.add_argument('--lan', action='store_true', help='cho máy khác trong cùng mạng Wi-Fi truy cập')
    ap.add_argument('--data', default=None, help='thư mục chứa cơ sở dữ liệu (mặc định: data/ hoặc biến TDH_DATA)')
    ap.add_argument('--no-demo', action='store_true', help='không tạo dữ liệu minh hoạ khi khởi tạo')
    a = ap.parse_args()
    configure(a.data, demo=False if a.no_demo else None)
    host = '0.0.0.0' if a.lan else '127.0.0.1'
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer((host, a.port), Handler)
    print('TĐH Chemistry đang chạy:  http://localhost:%d' % a.port)
    if a.lan and lan_ip():
        print('Học sinh cùng mạng Wi-Fi truy cập:  http://%s:%d' % (lan_ip(), a.port))
    print('Nhấn Ctrl+C để dừng.')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nĐã dừng.')


if __name__ == '__main__':
    main()
