'use strict';
/* TĐH Chemistry — lõi giao diện: gọi API, định tuyến, khung trang, hiển thị công thức hoá học. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const App = { user: null, routes: [] };

const TYPE = { single_choice: 'Trắc nghiệm', true_false: 'Đúng/Sai', short_answer: 'Trả lời ngắn' };
const PART = { single_choice: 'Trắc nghiệm nhiều phương án lựa chọn', true_false: 'Trắc nghiệm đúng/sai', short_answer: 'Trắc nghiệm trả lời ngắn' };
const LEVEL = { NB: 'Biết', TH: 'Hiểu', VD: 'Vận dụng' };
const EXAM_STATUS = { draft: ['Bản nháp', ''], open: ['Đang mở', 'ok'], closed: ['Đã đóng', 'warn'] };
const SHOW = {
  score: 'Hiện điểm ngay sau khi nộp', after_close: 'Hiện điểm ngay, hiện đáp án sau khi đề đóng',
  answers: 'Hiện điểm và đáp án ngay sau khi nộp', none: 'Chỉ báo đã nộp, không hiện điểm',
};
const ROMAN = ['I', 'II', 'III', 'IV'];

const IC = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5c2 .8 3.5 2.7 3.5 5.5"/>',
  bank: '<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  exam: '<path d="M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M9 12l2 2 4-4"/>',
  grid: '<path d="M4 4h16v16H4zM4 10h16M4 15h16M10 4v16M15 4v16"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5M19 19v2H6"/>',
  video: '<path d="M3 7h12v10H3z"/><path d="M15 10l6-3v10l-6-3"/>',
  bell: '<path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  chart: '<path d="M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3"/>',
  flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/><path d="M7.5 15h9"/>',
};
const icon = n => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;

const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
const fmtNum = x => x == null ? '—' : Number(x).toLocaleString('vi-VN', { maximumFractionDigits: 2 });
const toLocalInput = ts => {
  if (!ts) return '';
  const d = new Date(ts * 1000), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
const fromLocalInput = v => v ? Math.floor(new Date(v).getTime() / 1000) : null;
const badge = (text, kind = '') => `<span class="badge ${kind}">${esc(text)}</span>`;

/* ── Công thức hoá học: H2SO4 → H₂SO₄ tự động; điện tích viết Fe^3+, SO4^2-; chỉ số tự do x_1 ── */
const ELEMENTS = new Set(('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo ' +
  'Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U').split(' '));
function fmtFormula(tok) {
  let i = 0, out = '', atoms = 0, subs = 0;
  const n = tok.length, digit = c => c >= '0' && c <= '9';
  if (tok[0] === 'n' && /[A-Z(]/.test(tok[1] || '')) out += tok[i++];  // hệ số n trong phương trình polymer: nCH2=CH2
  while (i < n && digit(tok[i])) out += tok[i++];                    // hệ số đứng trước giữ nguyên
  while (i < n) {
    const c = tok[i];
    if (c >= 'A' && c <= 'Z') {
      const two = tok.substr(i, 2);
      if (two.length === 2 && two[1] >= 'a' && two[1] <= 'z' && ELEMENTS.has(two)) { out += two; i += 2; }
      else if (ELEMENTS.has(c)) { out += c; i++; }
      else return null;
      atoms++;
    } else if (digit(c)) {
      let j = i;
      while (j < n && digit(tok[j])) j++;
      out += `<sub>${tok.slice(i, j)}</sub>`; subs++; i = j;
    } else if ('()[]'.includes(c)) { out += c; i++; }
    else if (c === 'n' && i > 0 && ')]'.includes(tok[i - 1])) { out += '<sub>n</sub>'; subs++; i++; }
    else return null;
  }
  return atoms && subs ? out : null;
}
function chem(s) {
  let h = esc(s).replace(/&lt;=&gt;/g, '⇌').replace(/-&gt;/g, '→');
  h = h.replace(/\^\{([^}]{1,12})\}|\^(\d*[+\-−]|\d+)/g, (m, a, b) => `<sup>${(a ?? b).replace(/-/g, '−')}</sup>`);
  h = h.replace(/_\{([^}]{1,12})\}|_(\d+)/g, (m, a, b) => `<sub>${a ?? b}</sub>`);
  h = h.split(/(<[^>]+>|&[#\w]+;)/).map((part, i) => i % 2 ? part
    : part.replace(/[A-Za-z0-9()[\]]*[A-Z][A-Za-z0-9()[\]]*/g, t => /\d|[)\]]n/.test(t) ? (fmtFormula(t) ?? t) : t)).join('');
  return h.replace(/\n/g, '<br>');
}

/* ── API ── */
async function api(method, url, body) {
  const opt = { method, headers: {}, credentials: 'same-origin' };
  if (method !== 'GET') {
    opt.headers['X-TDH'] = '1';
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(body || {});
  }
  let res;
  try { res = await fetch(url, opt); } catch (e) {
    const err = new Error('Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.');
    err.network = true;
    throw err;
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* phản hồi không phải JSON */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Lỗi máy chủ (${res.status}).`);
    err.status = res.status;
    err.code = data && data.code;
    if (res.status === 401 && App.user) { App.user = null; location.hash = '#/login'; }
    if (err.code === 'must_change' && App.user) { App.user.must_change = true; location.hash = '#/account'; }
    throw err;
  }
  return data;
}

/* ── Thông báo nổi, cửa sổ, biểu mẫu ── */
function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.textContent = msg;
  $('#toast-root').appendChild(el);
  setTimeout(() => el.remove(), kind === 'err' ? 6000 : 3200);
}
const fail = e => toast(e.message || 'Có lỗi xảy ra.', 'err');
function closeModals() { $('#modal-root').innerHTML = ''; }
function modal(title, html, opts = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'modal-wrap';
  wrap.innerHTML = `<div class="modal ${opts.wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
    <header><h2>${esc(title)}</h2><button class="icon-btn" data-close aria-label="Đóng">✕</button></header>
    <div class="modal-body">${html}</div></div>`;
  $('#modal-root').appendChild(wrap);
  const close = () => { wrap.remove(); if (opts.onClose) opts.onClose(); };
  wrap.addEventListener('mousedown', e => { if (e.target === wrap && !opts.sticky) close(); });
  $('[data-close]', wrap).onclick = close;
  const first = $('input:not([type=hidden]), textarea, select', wrap);
  if (first && !opts.noFocus) setTimeout(() => first.focus(), 30);
  return { el: $('.modal', wrap), body: $('.modal-body', wrap), close };
}
function confirmDlg(message, okLabel = 'Đồng ý', danger = false) {
  return new Promise(resolve => {
    const m = modal('Xác nhận', `<p class="pre">${esc(message)}</p><div class="form-actions mt">
      <button class="btn" data-no>Huỷ</button><button class="btn ${danger ? 'accent' : 'primary'}" data-yes>${esc(okLabel)}</button></div>`,
      { onClose: () => resolve(false), noFocus: true });
    $('[data-no]', m.body).onclick = () => m.close();
    $('[data-yes]', m.body).onclick = () => { resolve(true); m.close(); };
  });
}
function fieldHtml(f, v) {
  const id = 'f_' + f.name, req = f.required ? 'required' : '', hint = f.hint ? `<small>${esc(f.hint)}</small>` : '';
  if (f.type === 'checkbox') return `<label class="chk"><input type="checkbox" name="${f.name}" ${v ? 'checked' : ''}><span>${esc(f.label)}${hint}</span></label>`;
  let ctl;
  if (f.type === 'select') {
    ctl = `<select id="${id}" name="${f.name}" ${req}>${f.options.map(([val, lab]) =>
      `<option value="${esc(val)}" ${String(v ?? '') === String(val) ? 'selected' : ''}>${esc(lab)}</option>`).join('')}</select>`;
  } else if (f.type === 'textarea') {
    ctl = `<textarea id="${id}" name="${f.name}" rows="${f.rows || 4}" ${req} placeholder="${esc(f.placeholder || '')}">${esc(v ?? '')}</textarea>`;
  } else if (f.type === 'multi') {
    ctl = f.options.length ? f.options.map(([val, lab]) => `<label class="chk"><input type="checkbox" name="${f.name}" value="${esc(val)}"
      ${(v || []).map(String).includes(String(val)) ? 'checked' : ''}><span>${esc(lab)}</span></label>`).join('') : '<p class="muted small">Chưa có lớp nào.</p>';
    return `<div class="f"><label class="f"><span>${esc(f.label)}</span></label>${ctl}${hint}</div>`;
  } else {
    const type = f.type === 'datetime' ? 'datetime-local' : (f.type || 'text');
    const val = f.type === 'datetime' ? toLocalInput(v) : (v ?? '');
    ctl = `<input id="${id}" type="${type}" name="${f.name}" value="${esc(val)}" ${req} placeholder="${esc(f.placeholder || '')}"
      ${f.step ? `step="${f.step}"` : ''} ${f.min != null ? `min="${f.min}"` : ''} ${f.max != null ? `max="${f.max}"` : ''} autocomplete="${f.autocomplete || 'off'}">`;
  }
  return `<label class="f"><span>${esc(f.label)}</span>${ctl}${hint}</label>`;
}
function readForm(form, fields) {
  const out = {};
  for (const f of fields) {
    if (f.type === 'checkbox') out[f.name] = form.elements[f.name].checked;
    else if (f.type === 'multi') out[f.name] = $$(`input[name="${f.name}"]:checked`, form).map(i => f.numeric ? Number(i.value) : i.value);
    else {
      const v = form.elements[f.name].value;
      out[f.name] = f.type === 'datetime' ? fromLocalInput(v) : f.type === 'number' ? (v === '' ? null : Number(v)) : f.numeric ? Number(v) : v.trim();
    }
  }
  return out;
}
function formModal(title, fields, values, onSubmit, opts = {}) {
  const m = modal(title, `<form class="form" novalidate>${opts.intro || ''}${fields.map(f => fieldHtml(f, (values || {})[f.name])).join('')}
    <p class="form-err" hidden></p><div class="form-actions"><button type="button" class="btn" data-cancel>Huỷ</button>
    <button class="btn primary" type="submit">${esc(opts.submit || 'Lưu')}</button></div></form>`, { wide: opts.wide, sticky: true });
  const form = $('form', m.body);
  $('[data-cancel]', form).onclick = m.close;
  form.onsubmit = async e => {
    e.preventDefault();
    const btn = $('[type=submit]', form), errBox = $('.form-err', form);
    btn.disabled = true;
    errBox.hidden = true;
    try { await onSubmit(readForm(form, fields)); m.close(); } catch (err) { errBox.textContent = err.message; errBox.hidden = false; } finally { btn.disabled = false; }
  };
  return m;
}
/* Gắn hành động cho các phần tử có data-act bên trong root */
function actions(root, map) {
  root.onclick = e => {
    const el = e.target.closest('[data-act]');
    if (!el || !root.contains(el) || el.disabled) return;
    const fn = map[el.dataset.act];
    if (fn) { e.preventDefault(); Promise.resolve(fn(el, e)).catch(fail); }
  };
}
function table(cols, rowsHtml, empty = 'Chưa có dữ liệu.') {
  if (!rowsHtml.length) return `<div class="empty">${esc(empty)}</div>`;
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr>${cols.map(c => `<th class="${c[1] || ''}">${esc(c[0])}</th>`).join('')}</tr></thead>
    <tbody>${rowsHtml.join('')}</tbody></table></div>`;
}

/* ── Hiển thị một câu hỏi kèm đáp án (xem trước, xem lại bài) ── */
function questionView(q, no, o = {}) {
  const key = q.key || {}, mine = o.mine, who = o.teacher ? 'HS' : 'Em';
  let body = '';
  if (q.type === 'single_choice') {
    body = (q.choices || []).map((c, i) => {
      const right = key.correct === c.id, picked = mine && q.answer === c.id;
      return `<div class="opt static ${right ? 'right-ans' : picked ? 'wrong-ans' : ''}"><span class="lb">${'ABCDEF'[i]}.</span>
        <span class="grow">${chem(c.text)}</span>${picked ? badge(who + ' chọn', right ? 'ok' : 'err') : ''}${right ? badge('Đáp án', 'ok') : ''}</div>`;
    }).join('');
  } else if (q.type === 'true_false') {
    const ans = q.answer || {};
    body = `<table class="tf"><tr><th></th><th>Đáp án</th>${mine ? `<th>${who} chọn</th>` : ''}</tr>${(q.statements || []).map(s => {
      const k = key[s.id], a = ans[s.id];
      return `<tr><td><b>${s.id})</b> ${chem(s.text)}</td><td class="c"><b>${k == null ? '—' : k ? 'Đúng' : 'Sai'}</b></td>
        ${mine ? `<td class="c ${a === k ? 'ok' : 'bad'}">${a == null ? '—' : a ? 'Đúng' : 'Sai'}</td>` : ''}</tr>`;
    }).join('')}</table>`;
  } else {
    const k = key.mode === 'text' ? (key.accepts || []).join('  |  ')
      : String(key.value ?? '').replace('.', ',') + (Number(String(key.tol ?? 0).replace(',', '.')) ? `  (± ${String(key.tol).replace('.', ',')})` : '');
    body = `${mine ? `<p>Trả lời của ${o.teacher ? 'học sinh' : 'em'}: <b>${q.answer == null || q.answer === '' ? '—' : esc(q.answer)}</b></p>` : ''}<p>Đáp án: <b>${esc(k)}</b></p>`;
  }
  const pts = mine ? `${fmtNum(q.awarded)} / ${fmtNum(q.points)} điểm` : (q.points != null ? `${fmtNum(q.points)} điểm` : '');
  const cls = mine ? (q.awarded >= q.points - 1e-4 ? 'ok' : q.awarded > 0 ? 'warn' : 'err') : 'blue';
  return `<div class="q"><div class="q-head"><b>Câu ${esc(no)}</b>${pts ? badge(pts, cls) : ''}</div>
    <div class="q-stem">${chem(q.stem)}</div>${body}
    ${q.explanation ? `<div class="q-expl"><b>Lời giải.</b> ${chem(q.explanation)}</div>` : ''}</div>`;
}
/* Chèn tiêu đề Phần I/II/III khi dạng câu thay đổi */
function withParts(list, render) {
  let last = null, part = 0;
  return list.map((q, i) => {
    let head = '';
    if (q.type !== last) { head = `<div class="part-title">Phần ${ROMAN[part++] || part}. ${PART[q.type]}</div>`; last = q.type; }
    return head + render(q, i);
  }).join('');
}

/* ── Định tuyến ── */
function route(pattern, roles, fn) {
  App.routes.push({ rx: new RegExp('^' + pattern.replace(/:(\w+)/g, '([^/]+)') + '$'), roles, fn });
}
const home = () => !App.user ? '#/' : App.user.role === 'student' ? '#/s' : '#/t';
function go(hash) { if (location.hash === hash) render(); else location.hash = hash; }
async function render() {
  const path = (location.hash.slice(1) || '/').split('?')[0];
  closeModals();
  if (App.leave) { App.leave(); App.leave = null; }
  for (const r of App.routes) {
    const m = path.match(r.rx);
    if (!m) continue;
    if (r.roles) {
      if (!App.user) return go('#/login');
      if (!r.roles.includes(App.user.role)) return go(home());
      if (App.user.must_change && path !== '/account') return go('#/account');
    }
    try { await r.fn(...m.slice(1).map(decodeURIComponent)); } catch (e) {
      if (e.status === 401 || e.code === 'must_change') return;
      if (App.user) shell('', 'Có lỗi', `<div class="notice err">${esc(e.message)}</div><p class="mt"><a class="btn" href="${home()}">Về trang chính</a></p>`);
      else fail(e);
    }
    window.scrollTo(0, 0);
    return;
  }
  go(home());
}

/* ── Khung trang sau đăng nhập ── */
const NAV_T = [['/t', 'Tổng quan', 'home'], ['/t/classes', 'Lớp học', 'users'], ['/t/questions', 'Ngân hàng câu hỏi', 'bank'], ['/t/exams', 'Đề thi', 'exam'],
  ['/t/matrix', 'Tạo đề từ ma trận', 'grid'], ['/t/lessons', 'Bài giảng', 'book'], ['/t/live', 'Lịch trực tuyến', 'video'], ['/t/news', 'Thông báo', 'bell']];
const NAV_A = [['/a/teachers', 'Giáo viên', 'shield'], ['/a/audit', 'Nhật kí và sao lưu', 'list']];
const NAV_S = [['/s', 'Trang của em', 'home'], ['/s/exams', 'Bài kiểm tra', 'exam'], ['/s/lessons', 'Bài giảng', 'book'], ['/s/live', 'Lịch học trực tuyến', 'video']];
const ROLE = { admin: 'Giáo viên · Quản trị', teacher: 'Giáo viên', student: 'Học sinh' };
function shell(active, title, html) {
  const u = App.user, link = ([p, label, ic]) => `<a href="#${p}" class="${p === active ? 'on' : ''}">${icon(ic)}<span>${label}</span></a>`;
  const nav = u.role === 'student' ? NAV_S.map(link).join('')
    : NAV_T.map(link).join('') + (u.role === 'admin' ? `<div class="sep">Quản trị</div>${NAV_A.map(link).join('')}` : '');
  $('#app').innerHTML = `<div class="shell" id="shell">
    <aside class="side"><a class="brand" href="${home()}"><img src="/img/logo_tdh.png" alt=""><div><b>TĐH Chemistry</b><span>Lớp học Hoá học số</span></div></a>
      <nav class="nav" aria-label="Điều hướng">${nav}<div class="sep">Cá nhân</div>${link(['/account', 'Tài khoản', 'key'])}</nav>
      <div class="who"><b>${esc(u.name)}</b>${esc(u.login_id)} · ${ROLE[u.role]}<button class="btn sm" id="logout-btn">Đăng xuất</button></div></aside>
    <div class="backdrop" id="backdrop"></div>
    <div class="main"><header class="top"><button class="icon-btn" id="menu-btn" aria-label="Mở menu">☰</button><h1>${esc(title)}</h1></header>
      <div class="page" id="page">${html}</div></div></div>`;
  $('#menu-btn').onclick = () => $('#shell').classList.toggle('open');
  $('#backdrop').onclick = () => $('#shell').classList.remove('open');
  $('#logout-btn').onclick = logout;
  return $('#page');
}
async function logout() {
  try { await api('POST', '/api/logout'); } catch (e) { /* vẫn thoát ở phía trình duyệt */ }
  App.user = null;
  go('#/');
}

/* ── Trang chủ công khai ── */
route('/', null, async () => {
  let news = [];
  try { news = (await api('GET', '/api/public/news')).news; } catch (e) { /* trang chủ vẫn hiển thị khi chưa tải được tin */ }
  const feats = [
    ['exam', 'Kiểm tra trực tuyến', 'Đề gồm trắc nghiệm, đúng/sai và trả lời ngắn. Tự lưu bài khi đang làm, đếm giờ theo máy chủ, chấm điểm ngay khi nộp.'],
    ['bank', 'Ngân hàng câu hỏi', 'Phân loại theo khối lớp, chương, mức độ Biết – Hiểu – Vận dụng. Câu mới nhập ở trạng thái nháp, giáo viên duyệt rồi mới dùng.'],
    ['grid', 'Tạo đề từ ma trận', 'Nhập số câu theo chương × mức độ × dạng câu; hệ thống chọn câu đã duyệt và báo rõ dòng nào còn thiếu.'],
    ['users', 'Lớp học và tài khoản', 'Giáo viên tạo lớp, cấp mã đăng nhập và mật khẩu ban đầu cho từng học sinh; học sinh phải đổi mật khẩu ở lần đầu.'],
    ['book', 'Bài giảng và lịch học', 'Đăng bài giảng, video, tài liệu theo lớp; lên lịch buổi học trực tuyến kèm liên kết phòng học.'],
    ['chart', 'Thống kê kết quả', 'Phổ điểm, điểm trung bình, trung vị, câu sai nhiều, danh sách chưa làm bài; xuất bảng điểm ra Excel (CSV).'],
  ];
  $('#app').innerHTML = `
    <header class="lp-top"><a class="brand" href="#/"><img src="/img/logo_tdh.png" alt="Logo TĐH"><div><b>TĐH Chemistry</b><span>Lớp học Hoá học số</span></div></a>
      <nav><a class="plain" href="#/" data-scroll="feat">Tính năng</a><a class="plain" href="#/" data-scroll="how">Cách dùng</a><a class="plain" href="#/" data-scroll="news">Thông báo</a>
        <a class="btn primary" href="${App.user ? home() : '#/login'}">${App.user ? 'Vào lớp học' : 'Đăng nhập'}</a></nav></header>
    <section class="hero"><div class="hero-in"><div>
        <span class="kicker">Hoá học THPT · Chương trình GDPT 2018</span>
        <h1>Dạy học, giao bài và kiểm tra Hoá học trong cùng một nơi</h1>
        <p class="lead">TĐH Chemistry giúp giáo viên quản lí lớp, xây dựng ngân hàng câu hỏi và tổ chức kiểm tra trực tuyến chấm tự động.
          Học sinh xem bài giảng, làm bài và nhận kết quả ngay trên điện thoại hoặc máy tính.</p>
        <div class="row"><a class="btn lg white" href="${App.user ? home() : '#/login'}">${App.user ? 'Vào lớp học' : 'Đăng nhập'}</a>
          <a class="btn lg line" href="#/" data-scroll="feat">Xem tính năng</a></div></div>
      <div class="hero-card"><img src="/img/logo_tdh.png" alt="">
        <h3 class="center">Một đề – ba dạng câu hỏi</h3>
        <ul><li><b>Trắc nghiệm</b><span>4 phương án, chọn 1 đáp án đúng</span></li>
          <li><b>Đúng/Sai</b><span>4 ý a–d, tính điểm theo số ý đúng</span></li>
          <li><b>Trả lời ngắn</b><span>Đáp án số, có sai số cho phép</span></li>
          <li><b>Công thức</b><span>${chem('H2SO4, Fe^3+, CH3COOC2H5')} hiển thị đúng chỉ số</span></li></ul></div></div></section>
    <section class="lp-sec" id="feat"><div><h2>Tính năng chính</h2><p class="sub">Những việc giáo viên Hoá học làm hằng tuần, gom về một trang web chạy được cả trên điện thoại.</p>
      <div class="grid g3">${feats.map(([ic, t, d]) => `<div class="feat"><div class="ic">${icon(ic)}</div><h3>${t}</h3><p>${d}</p></div>`).join('')}</div></div></section>
    <section class="lp-sec alt" id="how"><div><h2>Cách dùng trong ba bước</h2><p class="sub">Tài khoản do giáo viên cấp, không cần học sinh tự đăng kí.</p>
      <div class="grid g3">
        <div class="feat"><div class="ic"><b>1</b></div><h3>Giáo viên tạo lớp</h3><p>Nhập danh sách họ tên, hệ thống sinh mã đăng nhập và mật khẩu ban đầu để phát cho từng em.</p></div>
        <div class="feat"><div class="ic"><b>2</b></div><h3>Giao đề và bài giảng</h3><p>Chọn câu từ ngân hàng hoặc tạo đề theo ma trận, đặt giờ mở – đóng, thời gian làm bài và lớp được giao.</p></div>
        <div class="feat"><div class="ic"><b>3</b></div><h3>Học sinh làm bài</h3><p>Bài được tự lưu liên tục. Hết giờ hệ thống tự nộp, chấm điểm ở máy chủ và thống kê cho giáo viên.</p></div>
      </div></div></section>
    <section class="lp-sec" id="news"><div><h2>Thông báo</h2><p class="sub">Tin mới từ giáo viên.</p>
      <div class="card">${news.length ? news.map(n => `<article class="news-item"><h3>${n.pinned ? badge('Ghim', 'blue') + ' ' : ''}${esc(n.title)}</h3>
        <p class="muted small">${fmtDate(n.created_at)} · ${esc(n.author)}</p><p class="pre mt-s">${chem(n.body)}</p></article>`).join('')
        : '<p class="muted">Chưa có thông báo.</p>'}</div></div></section>
    <footer class="lp-foot">TĐH Chemistry · Lớp học Hoá học số · Dữ liệu lưu trên máy chủ của giáo viên</footer>`;
  $$('[data-scroll]').forEach(a => a.onclick = e => { e.preventDefault(); $('#' + a.dataset.scroll).scrollIntoView({ behavior: 'smooth' }); });
});

/* ── Đăng nhập ── */
route('/login', null, async () => {
  if (App.user) return go(home());
  $('#app').innerHTML = `<div class="auth"><div class="card">
    <img class="logo" src="/img/logo_tdh.png" alt="Logo TĐH"><h1>TĐH Chemistry</h1><p class="sub">Đăng nhập bằng tài khoản giáo viên cấp</p>
    <form id="login-form" novalidate>
      <label class="f"><span>Mã đăng nhập</span><input type="text" name="login_id" autocomplete="username" autocapitalize="none" spellcheck="false" required></label>
      <label class="f"><span>Mật khẩu</span><input type="password" name="password" autocomplete="current-password" required></label>
      <p class="form-err" hidden></p>
      <button class="btn primary lg" style="width:100%" type="submit">Đăng nhập</button></form>
    <p class="muted small center mt">Quên mật khẩu? Hãy liên hệ giáo viên để được cấp lại.</p>
    <p class="center mt-s"><a href="#/">← Về trang chủ</a></p></div></div>`;
  const form = $('#login-form');
  form.elements.login_id.focus();
  form.onsubmit = async e => {
    e.preventDefault();
    const btn = $('button', form), errBox = $('.form-err', form);
    btn.disabled = true;
    errBox.hidden = true;
    try {
      App.user = await api('POST', '/api/login', { login_id: form.elements.login_id.value, password: form.elements.password.value });
      go(App.user.must_change ? '#/account' : home());
    } catch (err) { errBox.textContent = err.message; errBox.hidden = false; } finally { btn.disabled = false; }
  };
});

/* ── Tài khoản: đổi mật khẩu ── */
route('/account', ['admin', 'teacher', 'student'], async () => {
  const u = App.user, forced = u.must_change;
  const form = `<form id="pw-form" novalidate style="max-width:420px">
      ${forced ? '<p class="notice warn mb">Đây là lần đăng nhập đầu tiên (hoặc mật khẩu vừa được cấp lại). Hãy đặt mật khẩu mới của riêng mình để tiếp tục.</p>' : ''}
      <label class="f"><span>Mật khẩu hiện tại</span><input type="password" name="old" autocomplete="current-password" required></label>
      <label class="f"><span>Mật khẩu mới</span><input type="password" name="new" autocomplete="new-password" required minlength="8"><small>Ít nhất 8 kí tự, khác mã đăng nhập.</small></label>
      <label class="f"><span>Nhập lại mật khẩu mới</span><input type="password" name="again" autocomplete="new-password" required></label>
      <p class="form-err" hidden></p><button class="btn primary" type="submit">Đổi mật khẩu</button>
      ${forced ? '<button class="btn ghost" type="button" id="pw-logout">Đăng xuất</button>' : ''}</form>`;
  if (forced) {
    $('#app').innerHTML = `<div class="auth"><div class="card"><img class="logo" src="/img/logo_tdh.png" alt=""><h1>Đặt mật khẩu mới</h1>
      <p class="sub">${esc(u.name)} · ${esc(u.login_id)}</p>${form}</div></div>`;
    $('#pw-logout').onclick = logout;
  } else {
    shell('/account', 'Tài khoản', `<div class="card"><h2>Thông tin</h2><p><b>${esc(u.name)}</b></p>
      <p class="muted">Mã đăng nhập: <span class="cred">${esc(u.login_id)}</span> · ${ROLE[u.role]}</p></div><div class="card"><h2>Đổi mật khẩu</h2>${form}</div>`);
  }
  const f = $('#pw-form');
  f.onsubmit = async e => {
    e.preventDefault();
    const errBox = $('.form-err', f), show = m => { errBox.textContent = m; errBox.hidden = false; };
    errBox.hidden = true;
    if (f.elements.new.value !== f.elements.again.value) return show('Hai lần nhập mật khẩu mới chưa giống nhau.');
    try {
      await api('POST', '/api/password', { old: f.elements.old.value, new: f.elements.new.value });
      App.user.must_change = false;
      toast('Đã đổi mật khẩu.', 'ok');
      go(forced ? home() : '#/account');
    } catch (err) { show(err.message); }
  };
});

window.addEventListener('hashchange', render);
window.addEventListener('DOMContentLoaded', async () => {
  try { App.user = (await api('GET', '/api/me')).user; } catch (e) { fail(e); }
  render();
});
