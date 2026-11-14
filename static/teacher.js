'use strict';
/* TĐH Chemistry — màn hình giáo viên và quản trị. */
const TR = ['admin', 'teacher'];
const TYPES = ['single_choice', 'true_false', 'short_answer'];
const DEFAULT_PTS = { single_choice: 0.25, true_false: 1, short_answer: 0.25 };
const opts = (obj, first) => (first ? [['', first]] : []).concat(Object.entries(obj));
const mem = (k, v) => { try { if (v === undefined) return localStorage.getItem('tdh_' + k); localStorage.setItem('tdh_' + k, v); } catch (e) { return null; } };
const cut = (s, n = 150) => s.length > n ? s.slice(0, n) + '…' : s;
const qShape = q => ({ type: q.type, stem: q.stem, choices: q.payload.choices, statements: q.payload.statements, key: q.answer_key, explanation: q.explanation });
const bodyShape = b => ({
  type: b.type, stem: b.stem || '', explanation: b.explanation,
  choices: (b.choices || []).map((t, i) => ({ id: 'ABCDEF'[i], text: t })),
  statements: (b.statements || []).map((s, i) => ({ id: 'abcd'[i], text: s.text })),
  key: b.type === 'single_choice' ? { correct: b.correct }
    : b.type === 'true_false' ? Object.fromEntries((b.statements || []).map((s, i) => ['abcd'[i], s.answer])) : (b.answer || {}),
});
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    ta.remove();
  }
  toast('Đã sao chép.', 'ok');
}
function showCreds(list, title) {
  const m = modal(title, `<p class="notice warn mb">Mật khẩu ban đầu chỉ hiển thị <b>một lần</b>. Hãy sao chép hoặc in ngay để phát riêng cho từng người.
      Hệ thống chỉ lưu mật khẩu dạng đã băm nên không xem lại được; nếu quên thì bấm "Cấp lại mật khẩu".</p>
    ${table([['Họ tên'], ['Mã đăng nhập'], ['Mật khẩu ban đầu']], list.map(s =>
    `<tr><td>${esc(s.name)}</td><td class="cred">${esc(s.login_id)}</td><td class="cred">${esc(s.password)}</td></tr>`))}
    <div class="form-actions mt no-print"><button class="btn" data-copy>Sao chép danh sách</button><button class="btn" data-print>In phiếu</button>
      <button class="btn primary" data-done>Đã lưu xong</button></div>`, { wide: true, sticky: true });
  $('[data-copy]', m.body).onclick = () => copyText(list.map(s => `${s.name}\t${s.login_id}\t${s.password}`).join('\n'));
  $('[data-print]', m.body).onclick = () => { document.body.classList.add('print-modal'); window.print(); document.body.classList.remove('print-modal'); };
  $('[data-done]', m.body).onclick = m.close;
}

/* ── Tổng quan ── */
route('/t', TR, async () => {
  const d = await api('GET', '/api/t/dashboard');
  const stats = [[d.classes, 'Lớp học'], [d.students, 'Học sinh'], [d.questions, 'Câu hỏi đã duyệt'], [d.drafts, 'Câu chờ duyệt'], [d.exams_open, 'Đề đang mở'], [d.submitted, 'Bài đã nộp']];
  shell('/t', 'Tổng quan', `
    <div class="grid g4">${stats.map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join('')}</div>
    <div class="row mt mb"><a class="btn primary" href="#/t/exams/new">+ Tạo đề mới</a><a class="btn" href="#/t/matrix">Tạo đề từ ma trận</a>
      <a class="btn" href="#/t/questions">Ngân hàng câu hỏi</a><a class="btn" href="#/t/classes">Lớp và tài khoản học sinh</a></div>
    <div class="grid g2"><div class="card"><h2>Bài nộp gần đây</h2>${table([['Học sinh'], ['Đề'], ['Điểm', 'num'], ['Nộp lúc']], d.recent.map(a =>
    `<tr><td>${esc(a.name)}</td><td><a href="#/t/exams/${a.exam_id}/results">${esc(cut(a.title, 50))}</a></td>
      <td class="num"><b>${fmtNum(a.score)}</b>/${fmtNum(a.max_score)}</td><td class="nowrap">${fmtDate(a.submitted_at)}</td></tr>`), 'Chưa có bài nộp nào.')}</div>
    <div class="card"><h2>Buổi học trực tuyến sắp tới</h2>${d.live.length ? d.live.map(l => `<div class="news-item"><b>${esc(l.title)}</b>
      <p class="muted small">${esc(l.class_name)} · ${fmtDate(l.starts_at)} · ${l.duration_min} phút</p></div>`).join('') : '<p class="muted">Chưa có lịch. Thêm ở mục Lịch trực tuyến.</p>'}</div></div>`);
});

/* ── Lớp học ── */
route('/t/classes', TR, async () => {
  const { classes } = await api('GET', '/api/t/classes');
  const page = shell('/t/classes', 'Lớp học', `<div class="page-head"><p class="muted">Tạo lớp, sau đó vào từng lớp để cấp tài khoản cho học sinh.</p>
      <button class="btn primary" data-act="add">+ Tạo lớp</button></div>
    ${table([['Lớp'], ['Năm học'], ['Học sinh', 'num'], ['']], classes.map(c => `<tr><td><a href="#/t/classes/${c.id}"><b>${esc(c.name)}</b></a></td>
      <td>${esc(c.year)}</td><td class="num">${c.students}</td><td class="acts"><a class="btn sm" href="#/t/classes/${c.id}">Danh sách</a>
      <button class="btn sm" data-act="edit" data-id="${c.id}">Sửa</button><button class="btn sm danger" data-act="del" data-id="${c.id}">Xoá</button></td></tr>`),
    'Chưa có lớp nào. Bấm "Tạo lớp" để bắt đầu.')}`);
  const fields = [{ name: 'name', label: 'Tên lớp', required: true, placeholder: 'Ví dụ: 12A1' }, { name: 'year', label: 'Năm học', placeholder: '2026–2027' }];
  actions(page, {
    add: () => formModal('Tạo lớp', fields, {}, async v => { await api('POST', '/api/t/classes', v); render(); }),
    edit: el => {
      const c = classes.find(x => x.id == el.dataset.id);
      formModal('Sửa lớp', fields, c, async v => { await api('PUT', `/api/t/classes/${c.id}`, v); render(); });
    },
    del: async el => {
      if (!await confirmDlg('Xoá lớp này? Bài giảng và lịch học của lớp cũng bị xoá.', 'Xoá lớp', true)) return;
      await api('DELETE', `/api/t/classes/${el.dataset.id}`);
      render();
    },
  });
});

route('/t/classes/:id', TR, async id => {
  const { class: c, students } = await api('GET', `/api/t/classes/${id}`);
  const page = shell('/t/classes', `Lớp ${c.name}`, `<div class="page-head"><p><a href="#/t/classes">← Tất cả lớp</a> <span class="muted">· ${students.length} học sinh · ${esc(c.year)}</span></p>
      <button class="btn primary" data-act="add">+ Thêm học sinh</button></div>
    ${table([['#', 'num'], ['Mã đăng nhập'], ['Họ tên'], ['Trạng thái'], ['']], students.map((s, i) => `<tr><td class="num">${i + 1}</td>
      <td class="cred">${esc(s.login_id)}</td><td>${esc(s.name)}</td>
      <td>${s.status === 'locked' ? badge('Đã khoá', 'err') : s.must_change ? badge('Chưa đổi mật khẩu', 'warn') : badge('Đang dùng', 'ok')}</td>
      <td class="acts"><button class="btn sm" data-act="rename" data-id="${s.id}">Sửa tên</button><button class="btn sm" data-act="reset" data-id="${s.id}">Cấp lại mật khẩu</button>
        <button class="btn sm" data-act="lock" data-id="${s.id}">${s.status === 'locked' ? 'Mở khoá' : 'Khoá'}</button>
        <button class="btn sm danger" data-act="remove" data-id="${s.id}">Gỡ khỏi lớp</button></td></tr>`),
    'Lớp chưa có học sinh. Bấm "Thêm học sinh" và dán danh sách họ tên.')}`);
  const find = el => students.find(s => s.id == el.dataset.id);
  actions(page, {
    add: () => formModal('Thêm học sinh', [{ name: 'names', label: 'Họ tên học sinh (mỗi dòng một em)', type: 'textarea', rows: 10, required: true,
      placeholder: 'Nguyễn Văn An\nTrần Thị Bình', hint: 'Mã đăng nhập và mật khẩu ban đầu được tạo tự động. Không nhập thông tin nhạy cảm (CCCD, địa chỉ…).' }], {},
    async v => {
      const names = v.names.split('\n').map(s => s.trim()).filter(Boolean);
      if (!names.length) throw new Error('Chưa nhập họ tên.');
      const { created } = await api('POST', `/api/t/classes/${id}/students`, { names });
      await render();
      showCreds(created, `Tài khoản mới – lớp ${c.name}`);
    }, { submit: 'Tạo tài khoản' }),
    rename: el => {
      const s = find(el);
      formModal('Sửa tên học sinh', [{ name: 'name', label: 'Họ tên', required: true }], s, async v => { await api('PUT', `/api/t/students/${s.id}`, v); render(); });
    },
    reset: async el => {
      const s = find(el);
      if (!await confirmDlg(`Cấp lại mật khẩu cho ${s.name}? Mật khẩu cũ sẽ hết hiệu lực và em phải đổi mật khẩu khi đăng nhập lại.`, 'Cấp lại')) return;
      const { password } = await api('POST', `/api/t/students/${s.id}/reset`);
      await render();
      showCreds([{ name: s.name, login_id: s.login_id, password }], 'Mật khẩu mới');
    },
    lock: async el => {
      const s = find(el);
      await api('POST', `/api/t/students/${s.id}/status`, { status: s.status === 'locked' ? 'active' : 'locked' });
      render();
    },
    remove: async el => {
      const s = find(el);
      if (!await confirmDlg(`Gỡ ${s.name} khỏi lớp ${c.name}? Tài khoản và kết quả bài làm của em vẫn được giữ.`, 'Gỡ khỏi lớp', true)) return;
      await api('DELETE', `/api/t/classes/${id}/students/${s.id}`);
      render();
    },
  });
});

/* ── Ngân hàng câu hỏi ── */
function questionEditor(q, chapters, done) {
  const isNew = !q;
  q = q || { grade: Number(mem('grade')) || 12, chapter: mem('chapter') || '', topic: '', outcome: '', level: 'NB', type: 'single_choice',
    status: 'approved', stem: '', payload: {}, answer_key: {}, explanation: '', source: '' };
  const sel = (name, options, v) => `<select name="${name}">${options.map(([val, lab]) => `<option value="${val}" ${String(v) === String(val) ? 'selected' : ''}>${esc(lab)}</option>`).join('')}</select>`;
  const m = modal(isNew ? 'Thêm câu hỏi' : 'Sửa câu hỏi', `<form id="qf" novalidate>
    <div class="fgrid">
      <label class="f"><span>Khối lớp</span>${sel('grade', [[10, 'Hoá 10'], [11, 'Hoá 11'], [12, 'Hoá 12']], q.grade)}</label>
      <label class="f"><span>Chương</span><input type="text" name="chapter" list="chap-dl" value="${esc(q.chapter)}" placeholder="Ví dụ: Ester – Lipid"></label>
      <label class="f"><span>Chủ đề / bài</span><input type="text" name="topic" value="${esc(q.topic)}"></label>
      <label class="f"><span>Mức độ</span>${sel('level', Object.entries(LEVEL), q.level)}</label>
      <label class="f"><span>Dạng câu</span>${sel('type', Object.entries(TYPE), q.type)}</label>
      <label class="f"><span>Trạng thái</span>${sel('status', [['approved', 'Đã duyệt'], ['draft', 'Nháp (chờ duyệt)']], q.status)}</label>
    </div>
    <datalist id="chap-dl">${chapters.map(c => `<option value="${esc(c)}">`).join('')}</datalist>
    <label class="f"><span>Yêu cầu cần đạt (không bắt buộc)</span><input type="text" name="outcome" value="${esc(q.outcome)}"></label>
    <label class="f"><span>Nội dung câu hỏi</span><textarea name="stem" rows="4">${esc(q.stem)}</textarea>
      <small>Gõ công thức bình thường: H2SO4, CH3COOH sẽ tự hạ chỉ số. Điện tích gõ Fe^3+, SO4^2-. Mũi tên gõ -&gt; hoặc &lt;=&gt;.</small></label>
    <div id="q-dyn"></div>
    <label class="f"><span>Lời giải (hiện cho học sinh khi được xem đáp án)</span><textarea name="explanation" rows="2">${esc(q.explanation)}</textarea></label>
    <label class="f"><span>Nguồn</span><input type="text" name="source" value="${esc(q.source)}" placeholder="Ví dụ: tự soạn, đề HK1 2025…"></label>
    <div class="notice" style="background:#f8fafd;color:inherit"><b class="small muted">XEM TRƯỚC</b><div id="q-prev" class="mt-s"></div></div>
    <p class="form-err mt" hidden></p>
    <div class="form-actions mt"><button type="button" class="btn" data-cancel>Huỷ</button><button class="btn primary" type="submit">Lưu câu hỏi</button></div></form>`,
  { wide: true, sticky: true });
  const f = $('#qf', m.body), dyn = $('#q-dyn', f);
  function drawDyn(type, src) {
    const key = src.answer_key || {}, pl = src.payload || {};
    if (type === 'single_choice') {
      dyn.innerHTML = '<label class="f"><span>Phương án (chọn nút tròn ở đáp án đúng)</span></label>' + 'ABCD'.split('').map((L, i) =>
        `<div class="row mt-s"><input type="radio" name="correct" value="${L}" ${key.correct === L ? 'checked' : ''} aria-label="Đáp án đúng ${L}" style="width:18px;height:18px">
        <b>${L}.</b><input class="grow" style="width:auto" type="text" name="choice_${L}" value="${esc((pl.choices || [])[i]?.text || '')}"></div>`).join('') + '<div class="mb"></div>';
    } else if (type === 'true_false') {
      dyn.innerHTML = '<label class="f"><span>Bốn mệnh đề và đáp án Đúng/Sai</span></label>' + 'abcd'.split('').map((L, i) =>
        `<div class="row mt-s"><b>${L})</b><input class="grow" style="width:auto" type="text" name="st_${L}" value="${esc((pl.statements || [])[i]?.text || '')}">
        <select name="ans_${L}" style="width:92px"><option value="">—</option><option value="1" ${key[L] === true ? 'selected' : ''}>Đúng</option>
        <option value="0" ${key[L] === false ? 'selected' : ''}>Sai</option></select></div>`).join('') + '<div class="mb"></div>';
    } else {
      const text = key.mode === 'text';
      dyn.innerHTML = `<div class="fgrid"><label class="f"><span>Kiểu đáp án</span><select name="mode"><option value="number">Số</option>
          <option value="text" ${text ? 'selected' : ''}>Văn bản</option></select></label>
        <label class="f" data-num><span>Đáp án đúng</span><input type="text" name="value" inputmode="decimal" value="${esc(text ? '' : String(key.value ?? '').replace('.', ','))}" placeholder="Ví dụ: 21,6"></label>
        <label class="f" data-num><span>Sai số cho phép (±)</span><input type="text" name="tol" inputmode="decimal" value="${esc(text ? '0' : String(key.tol ?? '0').replace('.', ','))}"></label>
        <label class="f" data-txt><span>Các đáp án chấp nhận (ngăn bằng dấu |)</span><input type="text" name="accepts" value="${esc(text ? (key.accepts || []).join(' | ') : '')}"></label></div>`;
      const sync = () => { const t = f.elements.mode.value === 'text'; $$('[data-num]', dyn).forEach(e => e.hidden = t); $$('[data-txt]', dyn).forEach(e => e.hidden = !t); };
      f.elements.mode.onchange = sync;
      sync();
    }
  }
  function collect() {
    const v = n => (f.elements[n]?.value || '').trim(), type = v('type');
    const b = { grade: Number(v('grade')), chapter: v('chapter'), topic: v('topic'), outcome: v('outcome'), level: v('level'), type, status: v('status'),
      stem: v('stem'), explanation: v('explanation'), source: v('source') };
    if (type === 'single_choice') {
      b.choices = 'ABCD'.split('').map(L => v('choice_' + L));
      b.correct = f.elements.correct?.value || '';
    } else if (type === 'true_false') {
      b.statements = 'abcd'.split('').map(L => ({ text: v('st_' + L), answer: v('ans_' + L) === '' ? null : v('ans_' + L) === '1' }));
    } else if (v('mode') === 'text') b.answer = { mode: 'text', accepts: v('accepts').split('|').map(s => s.trim()).filter(Boolean) };
    else b.answer = { mode: 'number', value: v('value'), tol: v('tol') || '0' };
    return b;
  }
  const preview = () => { $('#q-prev', f).innerHTML = questionView(bodyShape(collect()), '…'); };
  drawDyn(q.type, q);
  preview();
  f.elements.type.onchange = () => { drawDyn(f.elements.type.value, f.elements.type.value === q.type ? q : {}); preview(); };
  f.oninput = preview;
  $('[data-cancel]', f).onclick = m.close;
  f.onsubmit = async e => {
    e.preventDefault();
    const errBox = $('.form-err', f), b = collect();
    errBox.hidden = true;
    try {
      if (isNew) await api('POST', '/api/t/questions', b); else await api('PUT', `/api/t/questions/${q.id}`, b);
      mem('grade', b.grade);
      mem('chapter', b.chapter);
      m.close();
      toast('Đã lưu câu hỏi.', 'ok');
      done();
    } catch (err) { errBox.textContent = err.message; errBox.hidden = false; }
  };
}

/* Nhận dạng câu hỏi từ văn bản dán vào (hoặc JSON) */
function parseQuestions(text) {
  const t = text.trim();
  if (t[0] === '{' || t[0] === '[') {
    const obj = JSON.parse(t), arr = Array.isArray(obj) ? obj : (obj.questions || []);
    return arr.map(x => {
      const k = x.answer_key || {}, type = { true_false_group: 'true_false', short_number: 'short_answer', short_text: 'short_answer' }[x.type] || x.type;
      const it = { type, grade: x.grade, chapter: x.chapter, topic: x.topic, outcome: x.learning_outcome || x.outcome, level: x.difficulty || x.level || 'NB',
        stem: x.stem || '', explanation: x.explanation || '', source: x.source || '' };
      if (type === 'single_choice') { it.choices = (x.choices || []).map(c => c.text ?? c); it.correct = k.correct_choice || k.correct || ''; }
      else if (type === 'true_false') it.statements = (x.statements || []).map(s => ({ text: s.text, answer: k[s.id] }));
      else it.answer = k.mode === 'text' || k.accepts ? { mode: 'text', accepts: k.accepts || [] } : { mode: 'number', value: k.value, tol: k.absolute_tolerance ?? k.tol ?? 0 };
      return it;
    });
  }
  const out = [];
  for (const blk of ('\n' + text.replace(/\r/g, '')).split(/\n(?=\s*Câu\s+\d+\s*[.:)])/i)) {
    const lines = blk.split('\n').map(l => l.trim()).filter(Boolean);
    const m0 = lines.length && lines[0].match(/^Câu\s+\d+\s*[.:)]\s*(.*)$/i);
    if (!m0) continue;
    let rest = m0[1], level = 'NB';
    const lv = rest.match(/^[[(](NB|TH|VD)[\])]\s*/i);
    if (lv) { level = lv[1].toUpperCase(); rest = rest.slice(lv[0].length); }
    const stem = [rest], choices = [], statements = [], expl = [];
    let correct = '', ansLine = '', mode = 'stem', warn = '';
    for (const line of lines.slice(1)) {
      let mm;
      if ((mm = line.match(/^(?:Lời giải|Giải thích|Hướng dẫn giải|HD)\s*[:.]\s*(.*)$/i))) { mode = 'expl'; if (mm[1]) expl.push(mm[1]); }
      else if (mode === 'expl') expl.push(line);
      else if ((mm = line.match(/^Đáp án\s*[:.]\s*(.+)$/i))) { ansLine = mm[1].trim(); mode = 'ans'; }
      else if ((mm = line.match(/^(\*?)\s*([A-F])[.)]\s*(.+)$/))) { choices.push(mm[3]); if (mm[1]) correct = 'ABCDEF'[choices.length - 1]; mode = 'opt'; }
      else if ((mm = line.match(/^([a-d])[.)]\s*(.+?)\s*[[(]\s*(Đ|S|Đúng|Sai|đ|s|đúng|sai)\s*[\])]\s*\.?$/))) { statements.push({ text: mm[2], answer: /^đ/i.test(mm[3]) }); mode = 'opt'; }
      else if (mode === 'stem') stem.push(line);
      else warn = 'Có dòng không nhận dạng được: “' + cut(line, 40) + '”';
    }
    const it = { level, stem: stem.join('\n').trim(), explanation: expl.join('\n') };
    if (choices.length) {
      it.type = 'single_choice'; it.choices = choices;
      it.correct = correct || (/^[A-F]$/i.test(ansLine) ? ansLine.toUpperCase() : '');
      if (!it.correct) it.error = 'Chưa đánh dấu đáp án đúng (thêm dấu * trước phương án đúng, hoặc dòng “Đáp án: B”).';
      else if (choices.length < 2) it.error = 'Cần ít nhất 2 phương án.';
    } else if (statements.length) {
      it.type = 'true_false'; it.statements = statements;
      if (statements.length !== 4) it.error = 'Câu đúng/sai cần đúng 4 ý a–d, mỗi ý kết thúc bằng (Đ) hoặc (S).';
    } else if (ansLine) {
      it.type = 'short_answer';
      it.answer = /^-?\d+([.,]\d+)?$/.test(ansLine.replace(/\s/g, '')) ? { mode: 'number', value: ansLine, tol: 0 }
        : { mode: 'text', accepts: ansLine.split('|').map(s => s.trim()).filter(Boolean) };
    } else it.error = 'Không thấy phương án A–D, mệnh đề a–d hay dòng “Đáp án:”.';
    if (!it.stem) it.error = 'Thiếu nội dung câu hỏi.';
    if (warn && !it.error) it.error = warn;
    out.push(it);
  }
  return out;
}
function importDialog(chapters, done) {
  const sample = 'Câu 1. [NB] Công thức của ethyl acetate là\nA. HCOOC2H5\n*B. CH3COOC2H5\nC. CH3COOCH3\nD. C2H5COOCH3\nLời giải: Ethyl acetate là ester của acetic acid và ethanol.\n\n' +
    'Câu 2. [TH] Xét các phát biểu về glucose:\na) Glucose là monosaccharide. (Đ)\nb) Glucose thuộc loại polymer. (S)\nc) Glucose có phản ứng với thuốc thử Tollens. (Đ)\nd) Glucose không tan trong nước. (S)\n\n' +
    'Câu 3. [VD] Cho 18 gam glucose tác dụng với lượng dư thuốc thử Tollens thu được m gam Ag. Giá trị của m là bao nhiêu?\nĐáp án: 21,6';
  const m = modal('Nhập nhanh nhiều câu hỏi', `<div class="fgrid">
      <label class="f"><span>Khối lớp</span><select id="im-grade">${[10, 11, 12].map(g => `<option ${g == (mem('grade') || 12) ? 'selected' : ''}>${g}</option>`).join('')}</select></label>
      <label class="f"><span>Chương (áp dụng cho cả lô)</span><input type="text" id="im-chapter" list="im-dl" value="${esc(mem('chapter') || '')}"></label>
      <label class="f"><span>Chủ đề / bài</span><input type="text" id="im-topic"></label></div>
    <datalist id="im-dl">${chapters.map(c => `<option value="${esc(c)}">`).join('')}</datalist>
    <label class="f"><span>Dán nội dung câu hỏi</span><textarea id="im-text" rows="12" spellcheck="false" placeholder="${esc(sample)}"></textarea>
      <small>Mỗi câu bắt đầu bằng “Câu 1.”; mức độ ghi [NB], [TH] hoặc [VD]. Trắc nghiệm: thêm dấu * trước phương án đúng. Đúng/sai: mỗi ý kết thúc bằng (Đ) hoặc (S).
      Trả lời ngắn: thêm dòng “Đáp án: …”. Có thể thêm dòng “Lời giải: …”.</small></label>
    <div class="row"><button class="btn" data-sample>Chèn ví dụ mẫu</button><button class="btn primary" data-parse>Phân tích</button></div>
    <div id="im-out" class="mt"></div>`, { wide: true, sticky: true });
  const out = $('#im-out', m.body);
  let good = [];
  $('[data-sample]', m.body).onclick = () => { $('#im-text', m.body).value = sample; };
  $('[data-parse]', m.body).onclick = () => {
    let list;
    try { list = parseQuestions($('#im-text', m.body).value); } catch (e) { out.innerHTML = `<p class="notice err">Không đọc được nội dung: ${esc(e.message)}</p>`; return; }
    list.forEach(x => { if (!TYPE[x.type]) x.error = 'Dạng câu hỏi này chưa được hỗ trợ.'; if (!LEVEL[x.level]) x.level = 'NB'; });
    good = list.filter(x => !x.error);
    out.innerHTML = `<p class="notice ${good.length === list.length && list.length ? 'ok' : 'warn'}">Nhận dạng được ${list.length} câu: ${good.length} câu hợp lệ, ${list.length - good.length} câu cần sửa.
      Câu nhập vào ở trạng thái <b>nháp</b>; thầy/cô duyệt lại rồi mới dùng được trong đề.</p>
      ${list.map((x, i) => x.error ? `<div class="q"><div class="q-head"><b>Câu ${i + 1}</b>${badge('Cần sửa', 'err')}</div><div class="q-stem">${chem(cut(x.stem || '', 200))}</div>
        <p class="notice err">${esc(x.error)}</p></div>` : questionView(Object.assign(bodyShape(x), { points: null }), `${i + 1} · ${TYPE[x.type]} · ${LEVEL[x.level] || x.level}`)).join('')}
      ${good.length ? `<div class="form-actions"><button class="btn primary" data-import>Nhập ${good.length} câu hợp lệ vào ngân hàng</button></div>` : ''}`;
    const btn = $('[data-import]', out);
    if (btn) btn.onclick = async () => {
      const grade = Number($('#im-grade', m.body).value), chapter = $('#im-chapter', m.body).value.trim(), topic = $('#im-topic', m.body).value.trim();
      btn.disabled = true;
      try {
        const r = await api('POST', '/api/t/questions/import', { questions: good.map(x => Object.assign({ grade, chapter, topic }, x, { grade: x.grade || grade, chapter: x.chapter || chapter, topic: x.topic || topic })) });
        mem('grade', grade);
        mem('chapter', chapter);
        m.close();
        toast(`Đã nhập ${r.imported} câu (trạng thái nháp).`, 'ok');
        done();
      } catch (e) { btn.disabled = false; fail(e); }
    };
  };
}

route('/t/questions', TR, async () => {
  const st = { grade: '', chapter: '', level: '', type: '', status: '', q: '', offset: 0 }, LIMIT = 50;
  const page = shell('/t/questions', 'Ngân hàng câu hỏi', `<div class="page-head"><p class="muted" id="q-total"></p>
      <div class="row"><button class="btn" data-act="import">Nhập nhanh nhiều câu</button><button class="btn primary" data-act="add">+ Thêm câu hỏi</button></div></div>
    <div class="filters" id="q-filters"></div><div class="row mb" id="q-bulk" hidden><b id="q-nsel"></b>
      <button class="btn sm" data-act="bulk" data-do="approve">Duyệt</button><button class="btn sm" data-act="bulk" data-do="draft">Chuyển về nháp</button>
      <button class="btn sm danger" data-act="bulk" data-do="delete">Xoá</button></div><div id="q-list"></div>`);
  let items = [], total = 0, chapters = [];
  const selected = () => $$('input[data-qid]:checked', page).map(i => Number(i.dataset.qid));
  const syncBulk = () => { const n = selected().length; $('#q-bulk').hidden = !n; $('#q-nsel').textContent = `Đã chọn ${n} câu:`; };
  async function load() {
    const [{ facets }, data] = await Promise.all([api('GET', '/api/t/questions/facets'), api('GET', '/api/t/questions?' + new URLSearchParams({ ...st, limit: LIMIT }))]);
    items = data.items;
    total = data.total;
    chapters = [...new Set(facets.filter(f => !st.grade || f.grade == st.grade).map(f => f.chapter).filter(Boolean))].sort();
    const sel = (name, options) => `<select data-f="${name}" aria-label="${name}">${options.map(([v, l]) => `<option value="${esc(v)}" ${String(st[name]) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    $('#q-filters').innerHTML = sel('grade', [['', 'Mọi khối'], [10, 'Hoá 10'], [11, 'Hoá 11'], [12, 'Hoá 12']]) + sel('chapter', [['', 'Mọi chương']].concat(chapters.map(c => [c, c]))) +
      sel('level', opts(LEVEL, 'Mọi mức độ')) + sel('type', opts(TYPE, 'Mọi dạng')) + sel('status', [['', 'Mọi trạng thái'], ['approved', 'Đã duyệt'], ['draft', 'Nháp']]) +
      `<input type="search" data-f="q" placeholder="Tìm trong nội dung…" value="${esc(st.q)}">`;
    $('#q-total').textContent = `${total} câu hỏi${Object.entries(st).some(([k, v]) => k !== 'offset' && v) ? ' khớp bộ lọc' : ''}`;
    $('#q-list').innerHTML = table([['', ''], ['Nội dung'], ['Khối', 'num'], ['Mức độ'], ['Dạng'], ['Trạng thái'], ['']], items.map(q => `<tr>
      <td><input type="checkbox" data-qid="${q.id}" aria-label="Chọn câu ${q.id}"></td>
      <td><div>${chem(cut(q.stem, 170))}</div><div class="muted small">${esc([q.chapter, q.topic].filter(Boolean).join(' · ') || 'Chưa phân chương')}</div></td>
      <td class="num">${q.grade}</td><td>${badge(LEVEL[q.level], 'blue')}</td><td class="nowrap">${TYPE[q.type]}</td>
      <td>${q.status === 'approved' ? badge('Đã duyệt', 'ok') : badge('Nháp', 'warn')}</td>
      <td class="acts"><button class="btn sm" data-act="view" data-id="${q.id}">Xem</button><button class="btn sm" data-act="edit" data-id="${q.id}">Sửa</button></td></tr>`),
    'Chưa có câu hỏi phù hợp. Bấm "Thêm câu hỏi" hoặc "Nhập nhanh nhiều câu".') +
      (total > LIMIT ? `<div class="row between mt"><span class="muted small">Câu ${st.offset + 1}–${Math.min(total, st.offset + LIMIT)} / ${total}</span><span class="row">
        <button class="btn sm" data-act="prev" ${st.offset ? '' : 'disabled'}>← Trước</button><button class="btn sm" data-act="next" ${st.offset + LIMIT < total ? '' : 'disabled'}>Sau →</button></span></div>` : '');
    syncBulk();
  }
  page.onchange = e => {
    const f = e.target.dataset.f;
    if (f) { st[f] = e.target.value; st.offset = 0; if (f === 'grade') st.chapter = ''; load().catch(fail); } else if (e.target.dataset.qid) syncBulk();
  };
  actions(page, {
    add: () => questionEditor(null, chapters, load),
    import: () => importDialog(chapters, load),
    edit: el => questionEditor(items.find(q => q.id == el.dataset.id), chapters, load),
    view: el => {
      const q = items.find(x => x.id == el.dataset.id);
      modal('Xem câu hỏi', `<p class="muted small mb">Hoá ${q.grade} · ${esc(q.chapter || 'Chưa phân chương')}${q.topic ? ' · ' + esc(q.topic) : ''} · ${LEVEL[q.level]} · ${TYPE[q.type]}
        ${q.source ? ' · Nguồn: ' + esc(q.source) : ''}</p>${q.outcome ? `<p class="small mb"><b>YCCĐ:</b> ${esc(q.outcome)}</p>` : ''}${questionView(qShape(q), q.id)}`, { wide: true, noFocus: true });
    },
    prev: () => { st.offset = Math.max(0, st.offset - LIMIT); return load(); },
    next: () => { st.offset += LIMIT; return load(); },
    bulk: async el => {
      const ids = selected(), act = el.dataset.do;
      if (act === 'delete' && !await confirmDlg(`Xoá ${ids.length} câu hỏi đã chọn? Các đề đã phát hành vẫn giữ bản chụp của câu.`, 'Xoá', true)) return;
      await api('POST', '/api/t/questions/bulk', { ids, action: act });
      toast('Đã cập nhật.', 'ok');
      await load();
    },
  });
  await load();
});

/* ── Đề thi ── */
route('/t/exams', TR, async () => {
  const { exams } = await api('GET', '/api/t/exams');
  const page = shell('/t/exams', 'Đề thi', `<div class="page-head"><p class="muted">Soạn đề, giao cho lớp, theo dõi kết quả.</p>
      <div class="row"><a class="btn" href="#/t/matrix">Tạo từ ma trận</a><a class="btn primary" href="#/t/exams/new">+ Tạo đề mới</a></div></div>
    ${table([['Đề'], ['Lớp'], ['Trạng thái'], ['Thời gian mở'], ['Câu', 'num'], ['Đã nộp', 'num'], ['']], exams.map(e => `<tr>
      <td><a href="#/t/exams/${e.id}"><b>${esc(e.title)}</b></a><div class="muted small">${e.duration_min} phút · ${fmtNum(e.total)} điểm · ${e.max_attempts} lượt</div></td>
      <td>${esc(e.classes || '—')}</td><td>${badge(...EXAM_STATUS[e.status])}${e.ndoing ? ' ' + badge(e.ndoing + ' đang làm', 'blue') : ''}</td>
      <td class="small">${e.start_at || e.end_at ? `${fmtDate(e.start_at)}<br>→ ${fmtDate(e.end_at)}` : 'Không giới hạn'}</td>
      <td class="num">${e.nq}</td><td class="num">${e.nsub}</td>
      <td class="acts">${e.status !== 'draft' ? `<a class="btn sm primary" href="#/t/exams/${e.id}/results">Kết quả</a>` : ''}<a class="btn sm" href="#/t/exams/${e.id}">${e.status === 'draft' ? 'Soạn' : 'Thiết lập'}</a>
        <button class="btn sm" data-act="copy" data-id="${e.id}">Sao chép</button><button class="btn sm danger" data-act="del" data-id="${e.id}">Xoá</button></td></tr>`),
    'Chưa có đề nào. Bấm "Tạo đề mới" để chọn câu từ ngân hàng.')}`);
  actions(page, {
    copy: async el => { const r = await api('POST', `/api/t/exams/${el.dataset.id}/copy`); toast('Đã tạo bản sao (bản nháp).', 'ok'); go(`#/t/exams/${r.id}`); },
    del: async el => {
      const e = exams.find(x => x.id == el.dataset.id), n = e.nsub + e.ndoing;
      const msg = n ? `Xoá đề “${e.title}”?\n\nĐề này đã có ${n} bài làm của học sinh. Toàn bộ bài làm và điểm sẽ bị xoá vĩnh viễn, không khôi phục được.` : `Xoá đề “${e.title}”?`;
      if (!await confirmDlg(msg, n ? 'Xoá đề và toàn bộ bài làm' : 'Xoá đề', true)) return;
      await api('DELETE', `/api/t/exams/${e.id}`);
      render();
    },
  });
});

function pickQuestions(have, onAdd) {
  const st = { grade: mem('grade') || '', chapter: '', level: '', type: '', q: '' };
  const m = modal('Thêm câu từ ngân hàng', `<div class="filters" id="pk-f"></div><div id="pk-list" style="max-height:52vh;overflow:auto"></div>
    <div class="form-actions mt"><span class="grow muted small" id="pk-n"></span><button class="btn" data-all>Chọn tất cả đang hiện</button>
    <button class="btn primary" data-add>Thêm vào đề</button></div>`, { wide: true, noFocus: true });
  let items = [];
  const count = () => { $('#pk-n', m.body).textContent = `Đã chọn thêm ${$$('input[data-qid]:checked:not(:disabled)', m.body).length} câu`; };
  async function load() {
    const [{ facets }, data] = await Promise.all([api('GET', '/api/t/questions/facets'),
      api('GET', '/api/t/questions?' + new URLSearchParams({ ...st, status: 'approved', limit: 300 }))]);
    items = data.items;
    const chapters = [...new Set(facets.filter(f => !st.grade || f.grade == st.grade).map(f => f.chapter).filter(Boolean))].sort();
    const sel = (name, options) => `<select data-f="${name}">${options.map(([v, l]) => `<option value="${esc(v)}" ${String(st[name]) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    $('#pk-f', m.body).innerHTML = sel('grade', [['', 'Mọi khối'], [10, 'Hoá 10'], [11, 'Hoá 11'], [12, 'Hoá 12']]) + sel('chapter', [['', 'Mọi chương']].concat(chapters.map(c => [c, c]))) +
      sel('level', opts(LEVEL, 'Mọi mức độ')) + sel('type', opts(TYPE, 'Mọi dạng')) + `<input type="search" data-f="q" placeholder="Tìm…" value="${esc(st.q)}">`;
    $('#pk-list', m.body).innerHTML = table([[''], ['Nội dung'], ['Mức độ'], ['Dạng']], items.map(q => `<tr>
      <td><input type="checkbox" data-qid="${q.id}" ${have.has(q.id) ? 'disabled checked' : ''} aria-label="Chọn"></td>
      <td>${chem(cut(q.stem, 160))}<div class="muted small">${esc(q.chapter)}${have.has(q.id) ? ' · đã có trong đề' : ''}</div></td>
      <td>${badge(LEVEL[q.level], 'blue')}</td><td class="nowrap">${TYPE[q.type]}</td></tr>`), 'Không có câu đã duyệt nào khớp bộ lọc. Chỉ câu “Đã duyệt” mới đưa được vào đề.');
    count();
  }
  m.body.onchange = e => { const f = e.target.dataset.f; if (f) { st[f] = e.target.value; if (f === 'grade') st.chapter = ''; load().catch(fail); } else count(); };
  $('[data-all]', m.body).onclick = () => { $$('input[data-qid]:not(:disabled)', m.body).forEach(i => i.checked = true); count(); };
  $('[data-add]', m.body).onclick = () => {
    const ids = $$('input[data-qid]:checked:not(:disabled)', m.body).map(i => Number(i.dataset.qid));
    onAdd(items.filter(q => ids.includes(q.id)));
    m.close();
  };
  load().catch(fail);
}

route('/t/exams/:id', TR, async id => {
  const isNew = id === 'new';
  const [{ classes }, d] = await Promise.all([api('GET', '/api/t/classes'), isNew ? null : api('GET', `/api/t/exams/${id}`)]);
  const ex = d ? d.exam : { title: '', description: '', duration_min: 45, max_attempts: 1, shuffle_q: 0, shuffle_opt: 1, show_result: 'score', tf_policy: 'scale', status: 'draft' };
  const draft = ex.status === 'draft';
  let items = d ? d.items : [];
  const fields = [
    { name: 'title', label: 'Tên đề', required: true, placeholder: 'Ví dụ: Kiểm tra 15 phút – Ester' },
    { name: 'description', label: 'Ghi chú cho học sinh', type: 'textarea', rows: 2 },
    { name: 'class_ids', label: 'Giao cho lớp', type: 'multi', numeric: true, options: classes.map(c => [c.id, `${c.name} (${c.students} HS)`]) },
    { name: 'start_at', label: 'Mở lúc (để trống = mở ngay khi phát hành)', type: 'datetime' },
    { name: 'end_at', label: 'Đóng lúc (để trống = không giới hạn)', type: 'datetime' },
    { name: 'duration_min', label: 'Thời gian làm bài (phút)', type: 'number', min: 1, max: 600, required: true },
    { name: 'max_attempts', label: 'Số lượt được làm', type: 'number', min: 1, max: 20 },
    { name: 'show_result', label: 'Sau khi nộp bài', type: 'select', options: Object.entries(SHOW) },
  ].concat(draft ? [
    { name: 'tf_policy', label: 'Cách tính điểm câu Đúng/Sai', type: 'select', options: [['scale', 'Theo số ý đúng: 1 ý 10 % · 2 ý 25 % · 3 ý 50 % · 4 ý 100 %'], ['per_item', 'Chia đều: mỗi ý đúng 25 % điểm của câu']] },
    { name: 'shuffle_opt', label: 'Đảo thứ tự phương án A–D cho từng học sinh', type: 'checkbox' },
    { name: 'shuffle_q', label: 'Đảo thứ tự câu hỏi trong từng phần', type: 'checkbox' },
  ] : []);
  const values = Object.assign({}, ex, { class_ids: d ? d.class_ids : [] });
  const head = draft ? `<button class="btn" data-act="save">Lưu nháp</button><button class="btn primary" data-act="publish">Lưu và phát hành</button>`
    : `<a class="btn" href="#/t/exams/${id}/results">Kết quả</a><button class="btn" data-act="save">Lưu thiết lập</button>
       ${ex.status === 'open' ? '<button class="btn accent" data-act="close">Đóng đề</button>' : '<button class="btn primary" data-act="reopen">Mở lại đề</button>'}
       ${d.attempts ? '' : '<button class="btn" data-act="unpublish">Đưa về bản nháp</button>'}`;
  const page = shell('/t/exams', isNew ? 'Tạo đề mới' : ex.title, `<div class="page-head"><p><a href="#/t/exams">← Tất cả đề</a> ${badge(...EXAM_STATUS[ex.status])}</p><div class="row">${head}</div></div>
    ${draft ? '' : '<p class="notice mb">Đề đã phát hành nên danh sách câu hỏi, cách tính điểm và chế độ đảo đề được giữ cố định. Thầy/cô vẫn đổi được lớp, thời gian và cách hiện kết quả.</p>'}
    <div class="grid g2" style="align-items:start"><div class="card"><h2>Thiết lập</h2><form id="ex-form" novalidate>${fields.map(f => fieldHtml(f, values[f.name])).join('')}</form></div>
    <div class="card"><div class="row between"><h2>Câu hỏi trong đề</h2>${draft ? '<button class="btn sm primary" data-act="pick">+ Thêm từ ngân hàng</button>' : ''}</div>
      <p class="muted small mt-s" id="ex-sum"></p>
      ${draft ? `<div class="row mt-s small"><span class="muted">Đặt điểm theo dạng:</span>${TYPES.map(t => `<label>${TYPE[t]} <input type="number" data-pt="${t}" step="0.05" min="0.05" value="${DEFAULT_PTS[t]}" style="width:74px;min-height:30px;padding:2px 6px"></label>`).join('')}
        <button class="btn sm" data-act="setpts">Áp dụng</button></div>` : ''}
      <div id="ex-items" class="mt"></div></div></div>`);
  const form = $('#ex-form');
  function draw() {
    items.sort((a, b) => TYPES.indexOf(a.type) - TYPES.indexOf(b.type));
    const total = items.reduce((s, it) => s + Number(it.points || 0), 0);
    $('#ex-sum').textContent = items.length ? `${items.length} câu · tổng ${fmtNum(total)} điểm · ` + TYPES.map(t => `${items.filter(i => i.type === t).length} ${TYPE[t].toLowerCase()}`).join(', ') : 'Chưa có câu nào.';
    $('#ex-items').innerHTML = items.length ? withParts(items, (it, i) => `<div class="item-row">
      <b class="muted">${i + 1}</b><div><div>${chem(cut(it.stem || '(câu đã bị xoá khỏi ngân hàng)', 120))}</div>
        <div class="small muted">${LEVEL[it.level] || ''}${it.chapter ? ' · ' + esc(it.chapter) : ''}${it.status === 'draft' ? ' · ' + badge('Chưa duyệt', 'warn') : ''}</div></div>
      ${draft ? `<input type="number" step="0.05" min="0.05" value="${it.points}" data-idx="${i}" aria-label="Điểm câu ${i + 1}">
        <span class="nowrap"><button class="btn sm" data-act="up" data-idx="${i}" aria-label="Lên">↑</button><button class="btn sm" data-act="down" data-idx="${i}" aria-label="Xuống">↓</button>
        <button class="btn sm danger" data-act="rm" data-idx="${i}" aria-label="Bỏ">✕</button></span>` : `<span class="right">${fmtNum(it.points)} đ</span><span></span>`}</div>`)
      : '<div class="empty">Bấm “Thêm từ ngân hàng” để chọn câu đã duyệt.</div>';
  }
  const body = () => Object.assign(readForm(form, fields), { items: items.map(it => ({ question_id: it.question_id, points: Number(it.points) })) });
  async function save() {
    if (isNew) return (await api('POST', '/api/t/exams', body())).id;
    await api('PUT', `/api/t/exams/${id}`, body());
    return id;
  }
  const setStatus = async (action, msg) => { await api('POST', `/api/t/exams/${id}/status`, { action }); toast(msg, 'ok'); render(); };
  page.addEventListener('change', e => { if (e.target.dataset.idx != null && e.target.type === 'number') { items[e.target.dataset.idx].points = Number(e.target.value); draw(); } });
  actions(page, {
    pick: () => pickQuestions(new Set(items.map(i => i.question_id)), list => {
      for (const q of list) items.push({ question_id: q.id, points: Number($(`[data-pt="${q.type}"]`).value) || DEFAULT_PTS[q.type], type: q.type, stem: q.stem, level: q.level, chapter: q.chapter, status: q.status });
      draw();
    }),
    setpts: () => { for (const it of items) it.points = Number($(`[data-pt="${it.type}"]`).value) || it.points; draw(); },
    rm: el => { items.splice(el.dataset.idx, 1); draw(); },
    up: el => { const i = Number(el.dataset.idx); if (i > 0 && items[i - 1].type === items[i].type) { [items[i - 1], items[i]] = [items[i], items[i - 1]]; draw(); } },
    down: el => { const i = Number(el.dataset.idx); if (i < items.length - 1 && items[i + 1].type === items[i].type) { [items[i + 1], items[i]] = [items[i], items[i + 1]]; draw(); } },
    save: async () => { const nid = await save(); toast('Đã lưu.', 'ok'); go(`#/t/exams/${nid}`); },
    publish: async () => {
      const b = body();
      if (!b.class_ids.length) throw new Error('Hãy chọn ít nhất một lớp được giao đề.');
      if (!items.length) throw new Error('Đề chưa có câu hỏi.');
      if (!await confirmDlg(`Phát hành đề cho ${b.class_ids.length} lớp? Sau khi phát hành, danh sách câu hỏi được giữ cố định.`, 'Phát hành')) return;
      const nid = await save();
      try { await api('POST', `/api/t/exams/${nid}/status`, { action: 'publish' }); toast('Đã phát hành đề.', 'ok'); } finally { go(`#/t/exams/${nid}`); }
    },
    close: async () => { if (await confirmDlg('Đóng đề? Các bài đang làm dở sẽ được nộp và chấm ngay.', 'Đóng đề', true)) await setStatus('close', 'Đã đóng đề.'); },
    reopen: () => setStatus('reopen', 'Đã mở lại đề.'),
    unpublish: () => setStatus('unpublish', 'Đã đưa đề về bản nháp.'),
  });
  draw();
});

/* ── Kết quả ── */
route('/t/exams/:id/results', TR, async id => {
  const d = await api('GET', `/api/t/exams/${id}/results`), s = d.stats, e = d.exam;
  const maxBar = s ? Math.max(...s.hist, 1) : 1;
  const hard = [...d.per_question].filter(q => q.n).sort((a, b) => a.full / a.n - b.full / b.n);
  const page = shell('/t/exams', `Kết quả: ${e.title}`, `<div class="page-head"><p><a href="#/t/exams">← Tất cả đề</a> ${badge(...EXAM_STATUS[e.status])}</p>
      <div class="row"><a class="btn" href="#/t/exams/${id}">Thiết lập đề</a><a class="btn primary" href="/api/t/exams/${id}/results.csv" download>Tải bảng điểm (CSV)</a></div></div>
    ${s ? `<div class="grid g4"><div class="stat"><b>${s.n}</b><span>Học sinh đã nộp</span></div><div class="stat"><b>${fmtNum(s.mean)}</b><span>Điểm trung bình (thang 10)</span></div>
      <div class="stat"><b>${fmtNum(s.median)}</b><span>Trung vị</span></div><div class="stat"><b>${fmtNum(s.max)}</b><span>Cao nhất</span></div>
      <div class="stat"><b>${fmtNum(s.min)}</b><span>Thấp nhất</span></div><div class="stat"><b>${Math.round(s.pass / s.n * 100)}%</b><span>Đạt từ 5 điểm</span></div></div>
    <div class="grid g2 mt" style="align-items:start"><div class="card"><h2>Phổ điểm (thang 10, lấy lượt cao nhất)</h2>
      <div class="hist" role="img" aria-label="Phổ điểm">${s.hist.map((n, i) => `<div class="bar ${i < 5 ? 'low' : ''}" style="height:${Math.max(2, n / maxBar * 100)}%" title="${n} học sinh"><i>${n || ''}</i></div>`).join('')}</div>
      <div class="hist-x">${s.hist.map((_, i) => `<span>${i}–${i + 1}</span>`).join('')}</div></div>
    <div class="card"><h2>Câu sai nhiều nhất</h2>${table([['Câu', 'num'], ['Nội dung'], ['Đúng trọn', 'num']], hard.slice(0, 6).map(q => {
    const r = q.full / q.n * 100;
    return `<tr><td class="num">${q.no}</td><td>${chem(cut(q.stem, 80))}<div class="small muted">${TYPE[q.type]} · ${LEVEL[q.level] || ''}</div></td>
        <td class="num">${Math.round(r)}%<div class="meter"><i class="${r < 40 ? 'low' : r < 70 ? 'mid' : ''}" style="width:${r}%"></i></div></td></tr>`;
  }))}</div></div>` : '<div class="empty">Chưa có bài nào được nộp.</div>'}
    <div class="card mt"><h2>Bài làm (${d.attempts.length})</h2>${table([['Học sinh'], ['Lớp'], ['Lượt', 'num'], ['Trạng thái'], ['Nộp lúc'], ['Điểm', 'num'], ['']], d.attempts.map(a => `<tr>
      <td><b>${esc(a.name)}</b><div class="small muted cred">${esc(a.login_id)}</div></td><td>${esc(a.class_name || '—')}</td><td class="num">${a.attempt_no}</td>
      <td>${a.status === 'submitted' ? badge(a.auto ? 'Tự nộp khi hết giờ' : 'Đã nộp', a.auto ? 'warn' : 'ok') : badge('Đang làm', 'blue')}</td>
      <td class="nowrap">${fmtDate(a.submitted_at)}</td><td class="num">${a.status === 'submitted' ? `<b>${fmtNum(a.score)}</b> / ${fmtNum(a.max_score)}` : '—'}</td>
      <td class="acts">${a.status === 'submitted' ? `<button class="btn sm" data-act="view" data-id="${a.id}">Xem bài</button>` : ''}</td></tr>`), 'Chưa có học sinh nào làm bài.')}</div>
    ${d.missing.length ? `<div class="card"><h2>Chưa làm bài (${d.missing.length})</h2><p>${d.missing.map(m => `${esc(m.name)} <span class="muted small">(${esc(m.class_name)})</span>`).join(' · ')}</p></div>` : ''}`);
  actions(page, {
    view: async el => {
      const a = await api('GET', `/api/t/attempts/${el.dataset.id}`);
      modal(`${a.name} – lượt ${a.attempt_no}`, `<p class="mb">Điểm: <b>${fmtNum(a.score)} / ${fmtNum(a.max_score)}</b> · Nộp lúc ${fmtDate(a.submitted_at)}${a.auto ? ' · ' + badge('Tự nộp khi hết giờ', 'warn') : ''}</p>
        ${withParts(a.detail, (q, i) => questionView(q, i + 1, { mine: true, teacher: true }))}`, { wide: true, noFocus: true });
    },
  });
});

/* ── Tạo đề từ ma trận ── */
route('/t/matrix', TR, async () => {
  const { facets } = await api('GET', '/api/t/questions/facets');
  const ok = facets.filter(f => f.status === 'approved');
  const st = { grade: Number(mem('grade')) || 12, rows: [], checked: null };
  const page = shell('/t/matrix', 'Tạo đề từ ma trận', `<p class="muted mb">Nhập số câu cần lấy theo chương, mức độ và dạng câu. Hệ thống chỉ chọn câu <b>đã duyệt</b> trong ngân hàng của thầy/cô,
      không tự bù bằng câu khác khi thiếu. Đề tạo ra là bản nháp để thầy/cô xem lại trước khi phát hành.</p>
    <div class="card"><h2>Thông tin đề</h2><div class="fgrid">
      <label class="f"><span>Tên đề</span><input type="text" id="mx-title" placeholder="Ví dụ: Kiểm tra giữa kì I – Hoá 12"></label>
      <label class="f"><span>Khối lớp</span><select id="mx-grade">${[10, 11, 12].map(g => `<option value="${g}" ${g === st.grade ? 'selected' : ''}>Hoá ${g}</option>`).join('')}</select></label>
      <label class="f"><span>Thời gian làm bài (phút)</span><input type="number" id="mx-dur" value="50" min="1" max="600"></label>
      ${TYPES.map(t => `<label class="f"><span>Điểm mỗi câu ${TYPE[t].toLowerCase()}</span><input type="number" data-pt="${t}" step="0.05" min="0.05" value="${DEFAULT_PTS[t]}"></label>`).join('')}</div></div>
    <div class="card"><div class="row between"><h2>Ma trận</h2><div class="row"><button class="btn sm" data-act="tpl">Điền mẫu 18 – 4 – 6</button><button class="btn sm primary" data-act="add">+ Thêm dòng</button></div></div>
      <div id="mx-rows" class="mt"></div><p class="mt" id="mx-sum"></p><div id="mx-msg"></div>
      <div class="form-actions mt"><button class="btn" data-act="check">Kiểm tra ma trận</button><button class="btn primary" data-act="gen">Tạo đề nháp</button></div></div>`);
  const chapters = () => [...new Set(ok.filter(f => f.grade == st.grade).map(f => f.chapter))].sort();
  const avail = r => ok.filter(f => f.grade == st.grade && f.type === r.type && (r.chapter === '*' || f.chapter === r.chapter) && (r.level === '*' || f.level === r.level)).reduce((s, f) => s + f.n, 0);
  function draw() {
    const chs = chapters(), sel = (i, k, options, v) => `<select data-row="${i}" data-k="${k}" aria-label="${k}">${options.map(([val, lab]) => `<option value="${esc(val)}" ${v === val ? 'selected' : ''}>${esc(lab)}</option>`).join('')}</select>`;
    $('#mx-rows').innerHTML = table([['Chương'], ['Mức độ'], ['Dạng câu'], ['Số câu', 'num'], ['Sẵn có', 'num'], ['']], st.rows.map((r, i) => {
      const a = avail(r), chk = st.checked && st.checked[i];
      return `<tr><td>${sel(i, 'chapter', [['*', 'Bất kì chương nào']].concat(chs.map(c => [c, c || '(chưa phân chương)'])), r.chapter)}</td>
        <td>${sel(i, 'level', [['*', 'Bất kì']].concat(Object.entries(LEVEL)), r.level)}</td><td>${sel(i, 'type', Object.entries(TYPE), r.type)}</td>
        <td class="num"><input type="number" min="1" max="100" value="${r.count}" data-row="${i}" data-k="count" style="width:76px" aria-label="Số câu"></td>
        <td class="num">${chk ? (chk.short ? badge(`thiếu ${chk.short}`, 'err') : badge('đủ', 'ok')) : (a >= r.count ? a : badge(`${a} câu`, 'warn'))}</td>
        <td class="acts"><button class="btn sm danger" data-act="rm" data-idx="${i}" aria-label="Xoá dòng">✕</button></td></tr>`;
    }), 'Chưa có dòng nào. Bấm “Thêm dòng” hoặc “Điền mẫu 18 – 4 – 6”.');
    const n = t => st.rows.filter(r => r.type === t).reduce((s, r) => s + Number(r.count || 0), 0);
    const total = TYPES.reduce((s, t) => s + n(t) * (Number($(`[data-pt="${t}"]`).value) || 0), 0), all = TYPES.reduce((s, t) => s + n(t), 0);
    const lv = k => st.rows.filter(r => r.level === k).reduce((s, r) => s + Number(r.count || 0), 0);
    $('#mx-sum').innerHTML = st.rows.length ? `<b>${all} câu</b> (${TYPES.map(t => `${n(t)} ${TYPE[t].toLowerCase()}`).join(', ')}) · tổng <b>${fmtNum(total)} điểm</b>` +
      (all ? ` · Biết ${Math.round(lv('NB') / all * 100)}% · Hiểu ${Math.round(lv('TH') / all * 100)}% · Vận dụng ${Math.round(lv('VD') / all * 100)}%` + (lv('*') ? ` · ${lv('*')} câu mức bất kì` : '') : '') : '';
  }
  const payload = () => ({ grade: st.grade, rows: st.rows.map(r => ({ ...r, count: Number(r.count) })) });
  page.addEventListener('change', e => {
    const t = e.target;
    if (t.id === 'mx-grade') { st.grade = Number(t.value); mem('grade', st.grade); st.rows.forEach(r => r.chapter = '*'); }
    else if (t.dataset.row != null) st.rows[t.dataset.row][t.dataset.k] = t.dataset.k === 'count' ? Number(t.value) : t.value;
    else if (!t.dataset.pt) return;
    st.checked = null;
    $('#mx-msg').innerHTML = '';
    draw();
  });
  actions(page, {
    add: () => { st.rows.push({ chapter: chapters()[0] ?? '*', level: 'NB', type: 'single_choice', count: 1 }); st.checked = null; draw(); },
    tpl: () => { st.rows = [{ chapter: '*', level: '*', type: 'single_choice', count: 18 }, { chapter: '*', level: '*', type: 'true_false', count: 4 }, { chapter: '*', level: '*', type: 'short_answer', count: 6 }]; st.checked = null; draw(); },
    rm: el => { st.rows.splice(el.dataset.idx, 1); st.checked = null; draw(); },
    check: async () => {
      if (!st.rows.length) throw new Error('Ma trận chưa có dòng nào.');
      const r = await api('POST', '/api/t/matrix/check', payload());
      const key = x => `${x.chapter}|${x.level}|${x.type}`, byKey = Object.fromEntries(r.rows.map(x => [key(x), x]));
      st.checked = st.rows.map(x => byKey[key(x)]);
      $('#mx-msg').innerHTML = r.ok ? '<p class="notice ok mt">Ngân hàng đủ câu đã duyệt cho ma trận này.</p>'
        : `<p class="notice err mt">Chưa đủ câu: ${r.rows.filter(x => x.short).map(x => `${esc(x.chapter === '*' ? 'bất kì chương' : x.chapter)} – ${x.level === '*' ? 'bất kì mức' : LEVEL[x.level]} – ${TYPE[x.type]} thiếu ${x.short}`).join('; ')}.
           Hãy soạn và duyệt thêm câu, hoặc giảm số câu ở các dòng này.</p>`;
      draw();
    },
    gen: async () => {
      if (!st.rows.length) throw new Error('Ma trận chưa có dòng nào.');
      const title = $('#mx-title').value.trim();
      if (!title) throw new Error('Chưa nhập tên đề.');
      const r = await api('POST', '/api/t/matrix/generate', Object.assign(payload(), { title, duration_min: Number($('#mx-dur').value) || 50,
        points: Object.fromEntries(TYPES.map(t => [t, Number($(`[data-pt="${t}"]`).value) || DEFAULT_PTS[t]])) }));
      toast(`Đã tạo đề nháp gồm ${r.questions} câu.`, 'ok');
      go(`#/t/exams/${r.id}`);
    },
  });
  draw();
});

/* ── Trang danh sách dùng chung: bài giảng, lịch, thông báo ── */
async function crudPage(o) {
  const [data, { classes }] = await Promise.all([api('GET', o.url), api('GET', '/api/t/classes')]);
  const list = data[o.key], fields = o.fields(classes), needClass = o.needClass && !classes.length;
  const page = shell(o.nav, o.title, `<div class="page-head"><p class="muted">${o.intro}</p><button class="btn primary" data-act="add" ${needClass ? 'disabled' : ''}>+ ${o.noun}</button></div>
    ${needClass ? '<p class="notice warn mb">Hãy tạo lớp học trước ở mục Lớp học.</p>' : ''}
    ${table(o.cols.concat([['']]), list.map(it => `<tr>${o.row(it)}<td class="acts"><button class="btn sm" data-act="edit" data-id="${it.id}">Sửa</button>
      <button class="btn sm danger" data-act="del" data-id="${it.id}">Xoá</button></td></tr>`), o.empty)}`);
  actions(page, {
    add: () => formModal(o.noun, fields, o.defaults(classes), async v => { await api('POST', o.url, v); render(); }, { wide: true }),
    edit: el => { const it = list.find(x => x.id == el.dataset.id); formModal('Sửa ' + o.noun.toLowerCase(), fields, it, async v => { await api('PUT', `${o.url}/${it.id}`, v); render(); }, { wide: true }); },
    del: async el => { if (await confirmDlg(`Xoá ${o.noun.toLowerCase()} này?`, 'Xoá', true)) { await api('DELETE', `${o.url}/${el.dataset.id}`); render(); } },
  });
}
const classField = classes => ({ name: 'class_id', label: 'Lớp', type: 'select', numeric: true, options: classes.map(c => [c.id, c.name]) });
const KIND = { video: 'Video', pdf: 'Tài liệu PDF', slide: 'Slide', link: 'Liên kết', note: 'Ghi chú (chỉ có nội dung)' };

route('/t/lessons', TR, () => crudPage({
  nav: '/t/lessons', title: 'Bài giảng', url: '/api/t/lessons', key: 'lessons', noun: 'Bài giảng', needClass: true,
  intro: 'Đăng video, slide, tài liệu theo lớp. Tệp lớn nên để trên Google Drive, OneDrive hoặc YouTube rồi dán liên kết.',
  empty: 'Chưa có bài giảng nào.',
  cols: [['Bài giảng'], ['Lớp'], ['Loại'], ['Đã học', 'num'], ['Hiển thị']],
  row: l => `<td><b>${esc(l.title)}</b>${l.url ? `<div class="small"><a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(cut(l.url, 60))}</a></div>` : ''}</td>
    <td>${esc(l.class_name)}</td><td>${esc(KIND[l.kind] || l.kind)}</td><td class="num">${l.done}/${l.students}</td><td>${l.published ? badge('Đang hiện', 'ok') : badge('Ẩn')}</td>`,
  fields: classes => [classField(classes), { name: 'title', label: 'Tên bài giảng', required: true }, { name: 'kind', label: 'Loại học liệu', type: 'select', options: Object.entries(KIND) },
    { name: 'url', label: 'Liên kết (https://…)', type: 'url', placeholder: 'https://', hint: 'Liên kết YouTube sẽ được phát ngay trong trang của học sinh.' },
    { name: 'body', label: 'Nội dung / hướng dẫn tự học', type: 'textarea', rows: 6 }, { name: 'published', label: 'Hiển thị cho học sinh', type: 'checkbox' }],
  defaults: classes => ({ class_id: classes[0]?.id, kind: 'video', published: true }),
}));

route('/t/live', TR, () => crudPage({
  nav: '/t/live', title: 'Lịch học trực tuyến', url: '/api/t/live', key: 'sessions', noun: 'Buổi học', needClass: true,
  intro: 'Lên lịch buổi học qua Google Meet, Microsoft Teams hoặc Zoom. Chỉ học sinh của lớp mới thấy liên kết.',
  empty: 'Chưa có buổi học nào.',
  cols: [['Buổi học'], ['Lớp'], ['Bắt đầu'], ['Thời lượng', 'num'], ['Phòng học']],
  row: l => `<td><b>${esc(l.title)}</b>${l.note ? `<div class="small muted">${esc(cut(l.note, 80))}</div>` : ''}</td><td>${esc(l.class_name)}</td>
    <td class="nowrap">${fmtDate(l.starts_at)} ${l.starts_at + l.duration_min * 60 < Date.now() / 1000 ? badge('Đã qua') : ''}</td><td class="num">${l.duration_min} phút</td>
    <td><a href="${esc(l.join_url)}" target="_blank" rel="noopener noreferrer">Mở phòng</a></td>`,
  fields: classes => [classField(classes), { name: 'title', label: 'Tên buổi học', required: true }, { name: 'starts_at', label: 'Bắt đầu lúc', type: 'datetime', required: true },
    { name: 'duration_min', label: 'Thời lượng (phút)', type: 'number', min: 5, max: 600 }, { name: 'join_url', label: 'Liên kết phòng học', type: 'url', required: true, placeholder: 'https://meet.google.com/…' },
    { name: 'note', label: 'Nội dung, dặn dò', type: 'textarea', rows: 3 }],
  defaults: classes => ({ class_id: classes[0]?.id, duration_min: 45, starts_at: Math.floor(Date.now() / 1000 / 1800) * 1800 + 86400 }),
}));

route('/t/news', TR, () => crudPage({
  nav: '/t/news', title: 'Thông báo', url: '/api/t/news', key: 'news', noun: 'Thông báo',
  intro: 'Thông báo đang hiện sẽ xuất hiện trên trang chủ (ai cũng đọc được) và trang của học sinh. Không đưa thông tin riêng tư của học sinh vào đây.',
  empty: 'Chưa có thông báo nào.',
  cols: [['Tiêu đề'], ['Người đăng'], ['Ngày đăng'], ['Hiển thị']],
  row: n => `<td><b>${esc(n.title)}</b><div class="small muted">${esc(cut(n.body, 90))}</div></td><td>${esc(n.author)}</td><td class="nowrap">${fmtDate(n.created_at)}</td>
    <td>${n.published ? badge('Đang hiện', 'ok') : badge('Ẩn')} ${n.pinned ? badge('Ghim', 'blue') : ''}</td>`,
  fields: () => [{ name: 'title', label: 'Tiêu đề', required: true }, { name: 'body', label: 'Nội dung', type: 'textarea', rows: 7 },
    { name: 'pinned', label: 'Ghim lên đầu', type: 'checkbox' }, { name: 'published', label: 'Hiển thị công khai', type: 'checkbox' }],
  defaults: () => ({ published: true }),
}));

/* ── Quản trị ── */
route('/a/teachers', ['admin'], async () => {
  const { teachers } = await api('GET', '/api/a/teachers');
  const page = shell('/a/teachers', 'Tài khoản giáo viên', `<div class="page-head"><p class="muted">Mỗi giáo viên có lớp, ngân hàng câu hỏi và đề riêng; không xem được dữ liệu của nhau.</p>
      <button class="btn primary" data-act="add">+ Thêm giáo viên</button></div>
    ${table([['Mã đăng nhập'], ['Họ tên'], ['Vai trò'], ['Trạng thái'], ['']], teachers.map(t => `<tr><td class="cred">${esc(t.login_id)}</td><td>${esc(t.name)}</td>
      <td>${ROLE[t.role]}</td><td>${t.status === 'locked' ? badge('Đã khoá', 'err') : t.must_change ? badge('Chưa đổi mật khẩu', 'warn') : badge('Đang dùng', 'ok')}</td>
      <td class="acts">${t.role === 'teacher' ? `<button class="btn sm" data-act="reset" data-id="${t.id}">Cấp lại mật khẩu</button>
        <button class="btn sm" data-act="lock" data-id="${t.id}">${t.status === 'locked' ? 'Mở khoá' : 'Khoá'}</button>` : '<span class="muted small">Tài khoản của thầy/cô</span>'}</td></tr>`))}`);
  const find = el => teachers.find(t => t.id == el.dataset.id);
  actions(page, {
    add: () => formModal('Thêm giáo viên', [{ name: 'login_id', label: 'Mã đăng nhập', required: true, placeholder: 'vd: gv.lan', hint: 'Chữ không dấu, số, dấu chấm hoặc gạch nối; 3–32 kí tự.' },
      { name: 'name', label: 'Họ tên', required: true }], {}, async v => {
      const r = await api('POST', '/api/a/teachers', v);
      await render();
      showCreds([r], 'Tài khoản giáo viên mới');
    }, { submit: 'Tạo tài khoản' }),
    reset: async el => {
      const t = find(el);
      if (!await confirmDlg(`Cấp lại mật khẩu cho ${t.name}?`, 'Cấp lại')) return;
      const { password } = await api('POST', `/api/a/teachers/${t.id}/reset`);
      await render();
      showCreds([{ name: t.name, login_id: t.login_id, password }], 'Mật khẩu mới');
    },
    lock: async el => { const t = find(el); await api('POST', `/api/a/teachers/${t.id}/status`, { status: t.status === 'locked' ? 'active' : 'locked' }); render(); },
  });
});

const AUDIT = { 'password.change': 'Đổi mật khẩu', 'teacher.create': 'Tạo giáo viên', 'teacher.reset': 'Cấp lại mật khẩu giáo viên', 'teacher.status': 'Khoá/mở giáo viên',
  'student.create': 'Tạo tài khoản học sinh', 'student.reset': 'Cấp lại mật khẩu học sinh', 'student.status': 'Khoá/mở học sinh', 'student.unenroll': 'Gỡ học sinh khỏi lớp',
  'class.delete': 'Xoá lớp', 'question.import': 'Nhập câu hỏi', 'question.delete': 'Xoá câu hỏi', 'exam.publish': 'Phát hành đề', 'exam.unpublish': 'Đưa đề về nháp',
  'exam.close': 'Đóng đề', 'exam.reopen': 'Mở lại đề', 'exam.delete': 'Xoá đề', 'exam.matrix': 'Tạo đề từ ma trận', 'results.export': 'Xuất bảng điểm', 'backup.download': 'Tải bản sao lưu' };
route('/a/audit', ['admin'], async () => {
  const { events } = await api('GET', '/api/a/audit');
  shell('/a/audit', 'Nhật kí và sao lưu', `<div class="card mb"><div class="row between"><div class="grow"><h2>Sao lưu dữ liệu</h2>
      <p class="muted small">Tải về toàn bộ cơ sở dữ liệu: lớp, tài khoản, câu hỏi, đề, bài làm. Nên tải mỗi tuần và trước mỗi lần cập nhật website.
      Tệp chứa dữ liệu học sinh — cất ở nơi an toàn, không gửi qua nhóm chat.</p></div>
      <a class="btn primary" href="/api/a/backup" download>Tải bản sao lưu (.db)</a></div></div>
    <p class="muted mb">200 thao tác quan trọng gần nhất. Nhật kí không ghi mật khẩu hay đáp án.</p>
    ${table([['Thời gian'], ['Người thực hiện'], ['Thao tác'], ['Đối tượng'], ['Chi tiết']], events.map(e => `<tr><td class="nowrap">${fmtDate(e.at)}</td>
      <td>${esc(e.actor || '—')} <span class="muted small cred">${esc(e.login_id || '')}</span></td><td>${esc(AUDIT[e.action] || e.action)}</td><td>${esc(e.target)}</td>
      <td class="small muted">${esc(e.meta === '{}' ? '' : e.meta)}</td></tr>`), 'Chưa có thao tác nào.')}`);
});
