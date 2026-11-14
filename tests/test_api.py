#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm thử tự động cho máy chủ TĐH Chemistry.

Chạy:  python3 tests/test_api.py
Tự khởi động một máy chủ riêng trên cơ sở dữ liệu tạm (không đụng tới dữ liệu thật),
rồi kiểm tra: đăng nhập, phân quyền, chống lộ đáp án, chấm điểm, nộp trùng, hết giờ, ma trận.
"""
import http.cookiejar, json, os, re, shutil, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSED = FAILED = 0


def check(name, cond, info=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print('  ✓', name)
    else:
        FAILED += 1
        print('  ✗', name, '—', info)


class Client:
    def __init__(self, base):
        self.base = base
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, headers=None, raw=False, binary=False):
        h = {'X-TDH': '1', 'Content-Type': 'application/json'} if method != 'GET' else {}
        h.update(headers or {})
        data = json.dumps(body or {}).encode() if method != 'GET' else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with self.op.open(req, timeout=20) as r:
                self.headers = r.headers
                if binary:
                    return r.status, r.read()
                txt = r.read().decode('utf-8')
                return r.status, (txt if raw else json.loads(txt))
        except urllib.error.HTTPError as e:
            self.headers = e.headers
            txt = e.read().decode('utf-8')
            try:
                return e.code, json.loads(txt)
            except ValueError:
                return e.code, txt

    def login(self, lid, pw):
        return self.call('POST', '/api/login', {'login_id': lid, 'password': pw})


def with_server(mode, fn, env=None):
    """Khởi động máy chủ trên CSDL tạm rồi chạy fn(base, tmp). mode: 'http' (server.py) hoặc 'wsgi' (wsgi.py)."""
    tmp = tempfile.mkdtemp(prefix='tdh_test_')
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    cmd = ([sys.executable, os.path.join(ROOT, 'server.py'), '--port', str(port), '--data', tmp] if mode == 'http'
           else [sys.executable, os.path.join(ROOT, 'wsgi.py'), str(port)])
    full_env = dict(os.environ, TDH_DATA=tmp, **(env or {}))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=full_env, cwd=ROOT)
    base = 'http://127.0.0.1:%d' % port
    before = FAILED
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen(base + '/healthz', timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        fn(base, tmp)
    finally:
        proc.terminate()
        out = proc.communicate(timeout=5)[0]
        if FAILED > before:
            print('\n--- nhật kí máy chủ ---\n' + out[-3000:])
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print('══ Chế độ máy cá nhân (python3 server.py) ══')
    with_server('http', run)
    print('\n══ Chế độ máy chủ Internet (WSGI, wsgi.py) ══')
    with_server('wsgi', run)
    print('\n══ Cấu hình khi đưa lên Internet ══')
    with_server('wsgi', run_production, env={'TDH_SECURE_COOKIE': '1', 'TDH_TRUST_PROXY': '1', 'TDH_NO_DEMO': '1',
                                             'TDH_ADMIN_PASSWORD': PROD_PW, 'TZ': 'Asia/Ho_Chi_Minh'})
    print('\nKết quả: %d đạt, %d lỗi' % (PASSED, FAILED))
    sys.exit(1 if FAILED else 0)


PROD_PW = 'Khoi-tao-' + os.urandom(6).hex()


def run_production(base, tmp):
    c = Client(base)
    st, u = c.login('giaovien', PROD_PW)
    cookie = c.headers.get('Set-Cookie') or ''
    check('đăng nhập bằng mật khẩu ban đầu lấy từ biến môi trường', st == 200 and u['must_change'])
    check('cookie phiên có cờ Secure, HttpOnly, SameSite', all(x in cookie for x in ('Secure', 'HttpOnly', 'SameSite=Lax')), cookie)
    check('có tiêu đề HSTS', 'max-age' in (c.headers.get('Strict-Transport-Security') or ''))
    creds = open(os.path.join(tmp, 'TAI_KHOAN_BAN_DAU.txt'), encoding='utf-8').read()
    check('tệp tài khoản ban đầu không ghi mật khẩu đã đặt qua biến môi trường', PROD_PW not in creds and 'demo-hs' not in creds)
    db = sqlite3.connect(os.path.join(tmp, 'tdh.db'))
    check('không tạo dữ liệu demo trên máy chủ thật', db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
          and db.execute('SELECT COUNT(*) FROM questions').fetchone()[0] == 0)
    Client(base).call('POST', '/api/login', {'login_id': 'ai-do', 'password': 'x'}, headers={'X-Forwarded-For': '203.0.113.9, 10.0.0.1'})
    check('ghi nhận IP thật của người dùng qua proxy', db.execute("SELECT ip FROM login_failures WHERE login_id='ai-do'").fetchone() == ('203.0.113.9',))
    db.close()
    st, raw = Client(base).call('GET', '/', raw=True)
    check('trang chủ tải được qua WSGI', st == 200 and 'TĐH Chemistry' in raw)


def run(base, tmp):
    creds = open(os.path.join(tmp, 'TAI_KHOAN_BAN_DAU.txt'), encoding='utf-8').read()
    tpw = re.search(r'giaovien\s+mật khẩu = (\S+)', creds).group(1)
    demo = dict(re.findall(r'(demo-hs\d+)\s+mật khẩu = (\S+)', creds))

    print('1. Đăng nhập và đổi mật khẩu')
    anon = Client(base)
    check('chưa đăng nhập gọi API giáo viên → 401', anon.call('GET', '/api/t/classes')[0] == 401)
    check('sai mật khẩu → 401', anon.login('giaovien', 'sai-mat-khau')[0] == 401)
    check('tài khoản không tồn tại → cùng thông báo', anon.login('khong-co', 'x')[1]['error'] == anon.login('giaovien', 'x')[1]['error'])
    t1 = Client(base)
    st, u = t1.login('GiaoVien ', tpw)
    check('giáo viên đăng nhập (không phân biệt hoa/thường)', st == 200 and u['role'] == 'admin' and u['must_change'])
    st, d = t1.call('GET', '/api/t/classes')
    check('chưa đổi mật khẩu thì bị chặn', st == 403 and d.get('code') == 'must_change')
    check('mật khẩu mới quá ngắn bị từ chối', t1.call('POST', '/api/password', {'old': tpw, 'new': '123'})[0] == 400)
    check('đổi mật khẩu', t1.call('POST', '/api/password', {'old': tpw, 'new': 'Giaovien-Test-2026'})[0] == 200)
    check('mật khẩu cũ hết hiệu lực', Client(base).login('giaovien', tpw)[0] == 401)
    check('thiếu tiêu đề X-TDH (CSRF) → 403', t1.call('POST', '/api/t/classes', {'name': 'x'}, headers={'X-TDH': '0'})[0] == 403)
    check('Origin lạ → 403', t1.call('POST', '/api/t/classes', {'name': 'x'}, headers={'Origin': 'http://evil.example'})[0] == 403)

    print('2. Lớp học và tài khoản học sinh')
    st, d = t1.call('POST', '/api/t/classes', {'name': '12A1', 'year': '2026–2027'})
    cid = d['id']
    st, d = t1.call('POST', '/api/t/classes/%d/students' % cid, {'names': ['Nguyễn Văn An', 'Trần Thị Bình']})
    sA, sB = d['created']
    check('tạo 2 học sinh, mã theo lớp', st == 200 and sA['login_id'] == '12a1-001' and sB['login_id'] == '12a1-002')
    db = sqlite3.connect(os.path.join(tmp, 'tdh.db'))
    stored = db.execute('SELECT pw FROM users WHERE login_id=?', (sA['login_id'],)).fetchone()[0]
    check('mật khẩu lưu dạng băm, không lưu chữ thường', stored.startswith('pbkdf2$') and sA['password'] not in stored)

    print('3. Ngân hàng câu hỏi và đề')
    base_q = {'grade': 12, 'chapter': 'Kiểm thử', 'level': 'NB', 'status': 'approved'}
    q1 = t1.call('POST', '/api/t/questions', dict(base_q, type='single_choice', stem='Công thức của nước là',
                 choices=['H2O', 'CO2', 'O2', 'H2'], correct='A'))[1]['id']
    q2 = t1.call('POST', '/api/t/questions', dict(base_q, type='true_false', stem='Xét các phát biểu:', statements=[
        {'text': 'a', 'answer': True}, {'text': 'b', 'answer': False}, {'text': 'c', 'answer': True}, {'text': 'd', 'answer': False}]))[1]['id']
    q3 = t1.call('POST', '/api/t/questions', dict(base_q, type='short_answer', stem='Giá trị của m là?',
                 answer={'mode': 'number', 'value': '21,6', 'tol': '0,05'}))[1]['id']
    q4 = t1.call('POST', '/api/t/questions', dict(base_q, type='single_choice', stem='Câu nháp', status='draft',
                 choices=['1', '2'], correct='B'))[1]['id']
    check('câu thiếu đáp án bị từ chối', t1.call('POST', '/api/t/questions', dict(base_q, type='single_choice', stem='x', choices=['1', '2']))[0] == 400)
    exam = {'title': 'Đề kiểm thử', 'duration_min': 30, 'max_attempts': 2, 'show_result': 'after_close', 'shuffle_opt': True,
            'class_ids': [cid], 'items': [{'question_id': q1, 'points': 4}, {'question_id': q2, 'points': 4},
                                          {'question_id': q3, 'points': 2}, {'question_id': q4, 'points': 1}]}
    eid = t1.call('POST', '/api/t/exams', exam)[1]['id']
    st, d = t1.call('POST', '/api/t/exams/%d/status' % eid, {'action': 'publish'})
    check('không phát hành được đề còn câu nháp', st == 409)
    exam['items'].pop()
    t1.call('PUT', '/api/t/exams/%d' % eid, exam)
    check('phát hành đề', t1.call('POST', '/api/t/exams/%d/status' % eid, {'action': 'publish'})[0] == 200)

    print('4. Học sinh làm bài')
    a = Client(base)
    a.login(sA['login_id'], sA['password'])
    check('học sinh phải đổi mật khẩu lần đầu', a.call('GET', '/api/s/dashboard')[1].get('code') == 'must_change')
    a.call('POST', '/api/password', {'old': sA['password'], 'new': 'hocsinh-a-2026'})
    b = Client(base)
    b.login(sB['login_id'], sB['password'])
    b.call('POST', '/api/password', {'old': sB['password'], 'new': 'hocsinh-b-2026'})
    check('học sinh không gọi được API giáo viên', a.call('GET', '/api/t/questions')[0] == 403)
    check('học sinh không gọi được API quản trị', a.call('GET', '/api/a/teachers')[0] == 403)
    st, d = a.call('GET', '/api/s/dashboard')
    check('học sinh thấy đề được giao', st == 200 and any(e['id'] == eid and e['can_start'] for e in d['exams']))
    aid = a.call('POST', '/api/s/exams/%d/start' % eid)[1]['attempt_id']
    check('bấm bắt đầu lần hai → tiếp tục lượt cũ', a.call('POST', '/api/s/exams/%d/start' % eid)[1]['attempt_id'] == aid)
    st, raw = a.call('GET', '/api/s/attempts/%d' % aid, raw=True)
    att = json.loads(raw)
    check('đề gửi cho học sinh không chứa đáp án', not re.search(r'answer_key|"correct"|"key"|explanation|21[.,]6', raw), raw[:300])
    qs = {q['type']: q for q in att['questions']}
    check('đề có đủ 3 dạng câu', set(qs) == {'single_choice', 'true_false', 'short_answer'})
    answers = {str(qs['single_choice']['id']): 'A',
               str(qs['true_false']['id']): {'a': True, 'b': False, 'c': True, 'd': True},   # đúng 3/4 ý
               str(qs['short_answer']['id']): '21,62'}
    check('lưu bài (autosave)', a.call('PUT', '/api/s/attempts/%d/answers' % aid, {'answers': answers})[1].get('ok') is True)
    check('học sinh B không xem được bài của A', b.call('GET', '/api/s/attempts/%d' % aid)[0] == 404)
    check('học sinh B không lưu được vào bài của A', b.call('PUT', '/api/s/attempts/%d/answers' % aid, {'answers': {}})[0] == 404)
    check('nộp bài', a.call('POST', '/api/s/attempts/%d/submit' % aid)[0] == 200)
    check('nộp lần hai không lỗi', a.call('POST', '/api/s/attempts/%d/submit' % aid)[0] == 200)
    check('sau khi nộp không sửa được bài', a.call('PUT', '/api/s/attempts/%d/answers' % aid, {'answers': {str(qs['single_choice']['id']): 'B'}})[1].get('ok') is False)
    st, r = a.call('GET', '/api/s/attempts/%d/result' % aid)
    check('điểm = 4 + 4×0,5 + 2 = 8', st == 200 and r['score'] == 8.0 and r['max_score'] == 10.0, str(r))
    check('đề chưa đóng thì chưa hiện đáp án', r['detail'] is None)
    check('học sinh B không xem được kết quả của A', b.call('GET', '/api/s/attempts/%d/result' % aid)[0] == 404)

    print('5. Hết giờ, số lượt, đóng đề')
    bid = b.call('POST', '/api/s/exams/%d/start' % eid)[1]['attempt_id']
    b.call('PUT', '/api/s/attempts/%d/answers' % bid, {'answers': {str(qs['single_choice']['id']): 'A'}})
    db.execute('UPDATE attempts SET deadline_at=? WHERE id=?', (int(time.time()) - 600, bid))
    db.commit()
    st, d = b.call('PUT', '/api/s/attempts/%d/answers' % bid, {'answers': {str(qs['short_answer']['id']): '21,6'}})
    check('quá giờ thì không lưu thêm, tự nộp', d.get('ok') is False and d.get('status') == 'submitted')
    st, r = b.call('GET', '/api/s/attempts/%d/result' % bid)
    check('bài tự nộp chỉ chấm phần đã lưu trong giờ (4 điểm)', r['score'] == 4.0 and r['auto'] == 1, str(r))
    a.call('POST', '/api/s/exams/%d/start' % eid)
    st, d = a.call('POST', '/api/s/exams/%d/start' % eid)
    a2 = d['attempt_id']
    a.call('POST', '/api/s/attempts/%d/submit' % a2)
    check('hết 2 lượt thì không làm tiếp được', a.call('POST', '/api/s/exams/%d/start' % eid)[0] == 409)
    check('đề đã có bài làm không đưa về nháp được', t1.call('POST', '/api/t/exams/%d/status' % eid, {'action': 'unpublish'})[0] == 409)
    t1.call('POST', '/api/t/exams/%d/status' % eid, {'action': 'close'})
    st, r = a.call('GET', '/api/s/attempts/%d/result' % aid)
    check('đóng đề rồi mới hiện đáp án', r['detail'] is not None and len(r['detail']) == 3)

    print('6. Giáo viên khác không xem được dữ liệu')
    st, d = t1.call('POST', '/api/a/teachers', {'login_id': 'gv2', 'name': 'Giáo viên Hai'})
    t2 = Client(base)
    t2.login('gv2', d['password'])
    t2.call('POST', '/api/password', {'old': d['password'], 'new': 'giaovien-hai-2026'})
    check('GV2 không xem được kết quả đề của GV1', t2.call('GET', '/api/t/exams/%d/results' % eid)[0] == 404)
    check('GV2 không xem được lớp của GV1', t2.call('GET', '/api/t/classes/%d' % cid)[0] == 404)
    check('GV2 không xem được bài làm của HS lớp GV1', t2.call('GET', '/api/t/attempts/%d' % aid)[0] == 404)
    check('GV2 không sửa được câu hỏi của GV1', t2.call('PUT', '/api/t/questions/%d' % q1, dict(base_q, type='short_answer', stem='x', answer={'value': 1}))[0] == 404)
    check('GV2 không phải quản trị', t2.call('GET', '/api/a/teachers')[0] == 403)
    check('GV2 không thấy câu hỏi của GV1', t2.call('GET', '/api/t/questions')[1]['total'] == 0)
    st, d = t1.call('GET', '/api/t/exams/%d/results' % eid)
    check('GV1 xem thống kê', st == 200 and d['stats']['n'] == 2 and len(d['per_question']) == 3, str(d.get('stats')))
    st, raw = t1.call('GET', '/api/t/exams/%d/results.csv' % eid, raw=True)
    check('xuất CSV', st == 200 and '12a1-001' in raw and 'Điểm' in raw)

    print('7. Tạo đề từ ma trận')
    rows = [{'chapter': 'Ester – Lipid', 'level': 'NB', 'type': 'single_choice', 'count': 2},
            {'chapter': '*', 'level': '*', 'type': 'true_false', 'count': 3}]
    st, d = t1.call('POST', '/api/t/matrix/check', {'grade': 12, 'rows': rows})
    check('ma trận đủ câu', st == 200 and d['ok'], str(d))
    st, d = t1.call('POST', '/api/t/matrix/check', {'grade': 12, 'rows': [{'chapter': 'Polymer', 'level': 'VD', 'type': 'short_answer', 'count': 5}]})
    check('ma trận thiếu câu được báo rõ số thiếu', st == 200 and not d['ok'] and d['rows'][0]['short'] == 5)
    check('thiếu câu thì không tạo đề', t1.call('POST', '/api/t/matrix/generate', {'grade': 12, 'title': 'x', 'rows': [{'chapter': 'Polymer', 'level': 'VD', 'type': 'short_answer', 'count': 5}]})[0] == 409)
    st, d = t1.call('POST', '/api/t/matrix/generate', {'grade': 12, 'title': 'Đề từ ma trận', 'rows': rows, 'seed': 7})
    st2, d2 = t1.call('GET', '/api/t/exams/%d' % d['id'])
    check('tạo đề nháp 5 câu từ ma trận', st == 200 and d['questions'] == 5 and d2['exam']['status'] == 'draft' and len(d2['items']) == 5)

    print('8. Học liệu, lịch, thông báo, khoá tài khoản')
    check('liên kết không hợp lệ bị từ chối', t1.call('POST', '/api/t/lessons', {'class_id': cid, 'title': 'x', 'kind': 'link', 'url': 'javascript:alert(1)', 'published': True})[0] == 400)
    lid = t1.call('POST', '/api/t/lessons', {'class_id': cid, 'title': 'Bài 1', 'kind': 'note', 'body': 'Nội dung', 'published': True})[1]['id']
    check('học sinh thấy bài giảng của lớp mình', any(x['id'] == lid for x in a.call('GET', '/api/s/lessons')[1]['lessons']))
    check('đánh dấu đã học', a.call('POST', '/api/s/lessons/%d/done' % lid, {'done': True})[0] == 200)
    demo_c = Client(base)
    lid0, pw0 = next(iter(demo.items()))
    demo_c.login(lid0, pw0)
    check('học sinh lớp khác không thấy bài giảng lớp 12A1', not any(x['id'] == lid for x in demo_c.call('GET', '/api/s/lessons')[1]['lessons']))
    check('học sinh lớp khác không bắt đầu được đề của 12A1', demo_c.call('POST', '/api/s/exams/%d/start' % eid)[0] == 404)
    check('trang chủ công khai đọc được thông báo', len(anon.call('GET', '/api/public/news')[1]['news']) >= 1)
    sid = db.execute('SELECT id FROM users WHERE login_id=?', (sB['login_id'],)).fetchone()[0]
    t1.call('POST', '/api/t/students/%d/status' % sid, {'status': 'locked'})
    check('tài khoản bị khoá mất phiên ngay', b.call('GET', '/api/s/dashboard')[0] == 401)
    check('tài khoản bị khoá không đăng nhập được', Client(base).login(sB['login_id'], 'hocsinh-b-2026')[0] == 401)
    for _ in range(9):
        anon.login('giaovien', 'sai')
    check('sai mật khẩu nhiều lần bị chặn tạm (429)', anon.login('giaovien', 'Giaovien-Test-2026')[0] == 429)
    st, raw = anon.call('GET', '/../server.py', raw=True)
    check('không đọc được tệp ngoài thư mục static', 'PBKDF_ITERS' not in raw)

    print('9. Kiểm tra sức khoẻ và sao lưu')
    check('/healthz trả lời ok', anon.call('GET', '/healthz', raw=True) == (200, 'ok'))
    check('học sinh không tải được bản sao lưu', a.call('GET', '/api/a/backup')[0] == 403)
    check('chưa đăng nhập không tải được bản sao lưu', anon.call('GET', '/api/a/backup')[0] == 401)
    st, blob = t1.call('GET', '/api/a/backup', binary=True)
    check('quản trị tải được bản sao lưu SQLite', st == 200 and blob[:15] == b'SQLite format 3', str(blob[:20]))
    bk = os.path.join(tmp, 'bk.db')
    with open(bk, 'wb') as f:
        f.write(blob)
    b2 = sqlite3.connect(bk)
    check('bản sao lưu đủ dữ liệu và không kèm phiên đăng nhập',
          b2.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] >= 3 and b2.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0)
    b2.close()
    db.close()


if __name__ == '__main__':
    main()
