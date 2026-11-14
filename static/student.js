'use strict';
/* TĐH Chemistry — màn hình học sinh: trang chính, làm bài, kết quả, bài giảng, lịch học. */
const SR = ['student'];
const ytId = url => { const m = String(url || '').match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/); return m ? m[1] : null; };
const KIND_S = { video: 'Video', pdf: 'Tài liệu', slide: 'Slide', link: 'Liên kết', note: 'Ghi chú' };

function examCard(e) {
  const done = e.attempts.filter(a => a.status === 'submitted');
  let state, btn = '';
  if (e.in_progress) { state = badge('Đang làm dở', 'warn'); btn = `<a class="btn primary" href="#/s/take/${e.in_progress}">Làm tiếp</a>`; }
  else if (e.can_start) { state = badge(done.length ? 'Còn lượt làm' : 'Chưa làm', 'blue'); btn = `<button class="btn primary" data-act="start" data-id="${e.id}">${done.length ? 'Làm lại' : 'Bắt đầu làm bài'}</button>`; }
  else if (e.upcoming) state = badge('Sắp mở');
  else state = done.length ? badge('Đã nộp', 'ok') : badge('Đã đóng');
  return `<div class="card"><div class="row between"><h2 class="grow">${esc(e.title)}</h2>${state}</div>
    <p class="muted small">GV ${esc(e.teacher)} · ${e.nq} câu · ${e.duration_min} phút · đã dùng ${e.attempts.length}/${e.max_attempts} lượt</p>
    ${e.start_at || e.end_at ? `<p class="small mt-s">Mở: ${fmtDate(e.start_at)} → Đóng: ${fmtDate(e.end_at)}</p>` : ''}
    ${e.description ? `<p class="pre mt-s">${chem(e.description)}</p>` : ''}
    ${done.length ? `<div class="mt-s">${done.map(a => `<a class="btn sm" href="#/s/result/${a.id}">Lượt ${a.attempt_no}${a.score != null ? `: ${fmtNum(a.score)}/${fmtNum(a.max_score)} điểm` : ': đã nộp'}</a>`).join(' ')}</div>` : ''}
    ${btn ? `<div class="mt">${btn}</div>` : ''}</div>`;
}
function examActions(page, exams) {
  actions(page, {
    start: async el => {
      const e = exams.find(x => x.id == el.dataset.id);
      if (!await confirmDlg(`Bắt đầu làm “${e.title}”?\n\nThời gian ${e.duration_min} phút được tính ngay từ lúc bấm, kể cả khi em thoát ra giữa chừng. Bài làm được tự lưu liên tục.`, 'Bắt đầu')) return;
      const r = await api('POST', `/api/s/exams/${e.id}/start`);
      go(`#/s/take/${r.attempt_id}`);
    },
  });
}
const liveItem = l => {
  const now = Date.now() / 1000, on = now >= l.starts_at && now < l.starts_at + l.duration_min * 60;
  return `<div class="news-item"><div class="row between"><b class="grow">${esc(l.title)}</b>${on ? badge('Đang diễn ra', 'ok') : ''}</div>
    <p class="muted small">${esc(l.class_name)} · GV ${esc(l.teacher)} · ${fmtDate(l.starts_at)} · ${l.duration_min} phút</p>
    ${l.note ? `<p class="pre small mt-s">${esc(l.note)}</p>` : ''}
    <p class="mt-s"><a class="btn sm ${on ? 'primary' : ''}" href="${esc(l.join_url)}" target="_blank" rel="noopener noreferrer">Vào phòng học</a></p></div>`;
};

route('/s', SR, async () => {
  const d = await api('GET', '/api/s/dashboard');
  const todo = d.exams.filter(e => e.in_progress || e.can_start);
  const page = shell('/s', 'Trang của em', `<p class="mb">Chào <b>${esc(App.user.name)}</b>${d.classes.length ? ` · lớp ${d.classes.map(c => esc(c.name)).join(', ')}` : ''}.</p>
    ${d.classes.length ? '' : '<p class="notice warn mb">Em chưa được xếp vào lớp nào. Hãy báo giáo viên.</p>'}
    <h2 class="mb">Bài kiểm tra cần làm</h2>
    ${todo.length ? `<div class="grid g2" style="align-items:start">${todo.map(examCard).join('')}</div>` : '<div class="empty">Hiện không có bài kiểm tra nào đang chờ. <a href="#/s/exams">Xem tất cả bài kiểm tra</a></div>'}
    <div class="grid g2 mt" style="align-items:start">
      <div class="card"><h2>Buổi học trực tuyến sắp tới</h2>${d.live.length ? d.live.map(liveItem).join('') : '<p class="muted">Chưa có lịch học.</p>'}</div>
      <div class="card"><h2>Bài giảng mới</h2>${d.lessons.length ? d.lessons.map(l => `<div class="news-item"><a href="#/s/lessons"><b>${esc(l.title)}</b></a>
        <p class="muted small">${esc(l.class_name)} · ${KIND_S[l.kind] || ''} · ${l.done ? 'đã học' : 'chưa học'}</p></div>`).join('') : '<p class="muted">Chưa có bài giảng.</p>'}</div></div>
    <div class="card mt"><h2>Thông báo</h2>${d.news.length ? d.news.map(n => `<article class="news-item"><b>${esc(n.title)}</b>
      <p class="muted small">${fmtDate(n.created_at)} · ${esc(n.author)}</p><p class="pre mt-s">${chem(n.body)}</p></article>`).join('') : '<p class="muted">Chưa có thông báo.</p>'}</div>`);
  examActions(page, d.exams);
});

route('/s/exams', SR, async () => {
  const { exams } = await api('GET', '/api/s/dashboard');
  const page = shell('/s/exams', 'Bài kiểm tra', exams.length ? `<div class="grid g2" style="align-items:start">${exams.map(examCard).join('')}</div>`
    : '<div class="empty">Chưa có bài kiểm tra nào được giao cho lớp em.</div>');
  examActions(page, exams);
});

/* ── Làm bài: tự lưu, đếm giờ theo máy chủ, khôi phục khi mất mạng ── */
route('/s/take/:aid', SR, async aid => {
  const d = await api('GET', `/api/s/attempts/${aid}`);
  if (d.status !== 'in_progress') return go(`#/s/result/${aid}`);
  const LS = 'tdh_pending_' + aid, answers = d.answers || {};
  let pending = {}, saving = false, submitting = false, saveTimer = null;
  try { pending = JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) { pending = {}; }
  Object.assign(answers, pending);                       // phần chưa kịp gửi ở lần trước
  const skew = d.server_now * 1000 - Date.now();         // lệch giờ giữa máy học sinh và máy chủ
  const answered = q => {
    const a = answers[q.id];
    if (q.type === 'true_false') return !!a && q.statements.every(s => typeof a[s.id] === 'boolean');
    return a != null && a !== '';
  };
  const qHtml = (q, i) => {
    const a = answers[q.id];
    let body;
    if (q.type === 'single_choice') {
      body = q.choices.map((c, k) => `<label class="opt ${a === c.id ? 'sel' : ''}"><input type="radio" name="q${q.id}" data-q="${q.id}" value="${esc(c.id)}" ${a === c.id ? 'checked' : ''}>
        <span class="lb">${'ABCDEF'[k]}.</span><span class="grow">${chem(c.text)}</span></label>`).join('');
    } else if (q.type === 'true_false') {
      body = `<table class="tf"><tr><th></th><th>Đúng</th><th>Sai</th></tr>${q.statements.map(s => `<tr><td><b>${s.id})</b> ${chem(s.text)}</td>
        ${[1, 0].map(v => `<td class="c"><label><input type="radio" name="q${q.id}_${s.id}" data-q="${q.id}" data-s="${s.id}" value="${v}"
          ${a && a[s.id] === !!v ? 'checked' : ''} aria-label="Ý ${s.id}: ${v ? 'Đúng' : 'Sai'}"></label></td>`).join('')}</tr>`).join('')}</table>`;
    } else {
      body = `<input type="text" class="short" data-q="${q.id}" data-short="1" inputmode="decimal" maxlength="100" value="${esc(a ?? '')}" placeholder="Nhập câu trả lời" aria-label="Trả lời câu ${i + 1}">
        <p class="hint">Với đáp án là số: dùng dấu phẩy hoặc dấu chấm cho phần thập phân, ví dụ 21,6.</p>`;
    }
    return `<div class="q" id="q-${q.id}"><div class="q-head"><b>Câu ${i + 1}</b>${badge(fmtNum(q.points) + ' điểm', 'blue')}</div><div class="q-stem">${chem(q.stem)}</div>${body}</div>`;
  };
  $('#app').innerHTML = `<div class="take"><header class="take-top"><h1>${esc(d.exam.title)}</h1><span class="save-state" id="save-state">Bài làm được tự lưu</span>
      <span class="timer" id="timer" aria-label="Thời gian còn lại">--:--</span><button class="btn primary" id="submit-btn">Nộp bài</button></header>
    <div class="take-body"><div id="qs">${withParts(d.questions, qHtml)}
        <div class="center mt"><button class="btn primary lg" id="submit-btn2">Nộp bài</button></div></div>
      <aside class="navq card"><b>Danh sách câu</b><p class="small muted" id="nav-count"></p>
        <div class="cells">${d.questions.map((q, i) => `<a href="#" data-goto="${q.id}" id="nav-${q.id}">${i + 1}</a>`).join('')}</div></aside></div></div>`;
  const stateEl = $('#save-state'), timerEl = $('#timer');
  const setState = (t, err) => { stateEl.textContent = t; stateEl.classList.toggle('err', !!err); };
  const persist = () => { try { localStorage.setItem(LS, JSON.stringify(pending)); } catch (e) { /* bộ nhớ trình duyệt bị chặn */ } };
  function mark() {
    let n = 0;
    for (const q of d.questions) { const ok = answered(q); n += ok; $('#nav-' + q.id).classList.toggle('done', ok); }
    $('#nav-count').textContent = `Đã trả lời ${n}/${d.questions.length} câu`;
    return d.questions.length - n;
  }
  const schedule = ms => { clearTimeout(saveTimer); saveTimer = setTimeout(flush, ms); };
  async function flush() {
    if (saving || submitting || !Object.keys(pending).length) return;
    saving = true;
    const batch = pending;
    pending = {};
    setState('Đang lưu…');
    try {
      const r = await api('PUT', `/api/s/attempts/${aid}/answers`, { answers: batch });
      if (r.ok === false) { cleanup(); toast('Bài đã được nộp.', 'ok'); return go(`#/s/result/${aid}`); }
      persist();
      setState('Đã lưu lúc ' + new Date().toLocaleTimeString('vi-VN'));
    } catch (e) {
      pending = Object.assign(batch, pending);            // giữ lại để gửi lại, ưu tiên thay đổi mới hơn
      persist();
      setState('Chưa lưu được – đang thử lại', true);
    } finally {
      saving = false;
      if (Object.keys(pending).length && !submitting) schedule(4000);
    }
  }
  function changed(id) { pending[id] = answers[id]; persist(); mark(); setState('Đang lưu…'); schedule(1200); }
  const qs = $('#qs');
  qs.addEventListener('change', e => {
    const t = e.target, id = t.dataset.q;
    if (!id || t.dataset.short) return;
    if (t.dataset.s) answers[id] = Object.assign({}, answers[id], { [t.dataset.s]: t.value === '1' });
    else {
      answers[id] = t.value;
      $$(`#q-${id} .opt`).forEach(o => o.classList.toggle('sel', $('input', o).checked));
    }
    changed(id);
  });
  qs.addEventListener('input', e => { const t = e.target; if (t.dataset.short) { answers[t.dataset.q] = t.value.trim(); changed(t.dataset.q); } });
  $('.navq').addEventListener('click', e => {
    const a = e.target.closest('[data-goto]');
    if (a) { e.preventDefault(); $('#q-' + a.dataset.goto).scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
  async function submit(auto) {
    if (submitting) return;
    submitting = true;
    clearTimeout(saveTimer);
    $('#submit-btn').disabled = $('#submit-btn2').disabled = true;
    setState('Đang nộp bài…');
    try {
      await api('POST', `/api/s/attempts/${aid}/submit`, { answers: pending });
      try { localStorage.removeItem(LS); } catch (e) { /* bỏ qua */ }
      cleanup();
      toast(auto ? 'Hết giờ – bài đã được nộp.' : 'Đã nộp bài.', 'ok');
      go(`#/s/result/${aid}`);
    } catch (e) {
      submitting = false;
      $('#submit-btn').disabled = $('#submit-btn2').disabled = false;
      setState('Chưa nộp được – kiểm tra mạng', true);
      if (auto) setTimeout(() => submit(true), 5000); else fail(e);
    }
  }
  const ask = async () => {
    const left = mark();
    if (await confirmDlg(left ? `Em còn ${left} câu chưa trả lời xong.\nNộp bài rồi sẽ không sửa được nữa. Em vẫn muốn nộp?` : 'Nộp bài? Sau khi nộp em không sửa được nữa.', 'Nộp bài')) submit(false);
  };
  $('#submit-btn').onclick = $('#submit-btn2').onclick = ask;
  let fired = false;
  const tick = setInterval(() => {
    const left = Math.max(0, Math.round((d.deadline_at * 1000 - (Date.now() + skew)) / 1000));
    const h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60), s = left % 60, p = n => String(n).padStart(2, '0');
    timerEl.textContent = (h ? h + ':' : '') + p(m) + ':' + p(s);
    timerEl.classList.toggle('low', left <= 300);
    if (left <= 0 && !fired) { fired = true; closeModals(); submit(true); }
  }, 500);
  const onHide = () => { if (document.visibilityState === 'hidden') flush(); };
  const onUnload = e => { if (Object.keys(pending).length) { e.preventDefault(); e.returnValue = ''; } };
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('beforeunload', onUnload);
  function cleanup() {
    clearInterval(tick);
    clearTimeout(saveTimer);
    document.removeEventListener('visibilitychange', onHide);
    window.removeEventListener('beforeunload', onUnload);
  }
  App.leave = cleanup;
  mark();
  if (Object.keys(pending).length) schedule(300);
});

route('/s/result/:aid', SR, async aid => {
  const r = await api('GET', `/api/s/attempts/${aid}/result`);
  const hasScore = r.score != null;
  shell('/s/exams', 'Kết quả bài làm', `<div class="card center"><p class="muted">${esc(r.exam.title)} · lượt ${r.attempt_no}</p>
      ${hasScore ? `<div class="score-big mt-s">${fmtNum(r.score)}<span class="muted" style="font-size:22px;font-weight:600"> / ${fmtNum(r.max_score)}</span></div><p>điểm</p>`
    : '<h2 class="mt-s">Đã nộp bài</h2><p class="muted">Giáo viên chưa công bố điểm cho bài này.</p>'}
      <p class="muted small mt-s">Nộp lúc ${fmtDate(r.submitted_at)}${r.auto ? ' · hệ thống tự nộp khi hết giờ' : ''}</p>
      <p class="mt"><a class="btn" href="#/s/exams">Về danh sách bài kiểm tra</a></p></div>
    ${r.detail ? `<h2 class="mt mb">Xem lại bài làm</h2>${withParts(r.detail, (q, i) => questionView(q, i + 1, { mine: true }))}`
    : (r.exam.show_result === 'after_close' ? '<p class="notice mt">Đáp án và lời giải sẽ hiện sau khi bài kiểm tra đóng.</p>' : '')}`);
});

route('/s/lessons', SR, async () => {
  const { lessons } = await api('GET', '/api/s/lessons');
  const page = shell('/s/lessons', 'Bài giảng', lessons.length ? lessons.map(l => {
    const yt = ytId(l.url);
    return `<div class="card"><div class="row between"><h2 class="grow">${esc(l.title)}</h2>${l.done ? badge('Đã học', 'ok') : badge('Chưa học', 'blue')}</div>
      <p class="muted small">${esc(l.class_name)} · ${KIND_S[l.kind] || ''} · ${fmtDate(l.created_at)}</p>
      ${l.body ? `<p class="pre mt-s">${chem(l.body)}</p>` : ''}<div id="vid-${l.id}"></div>
      <div class="row mt">${yt ? `<button class="btn primary" data-act="play" data-id="${l.id}" data-yt="${yt}">Xem video</button>` : ''}
        ${l.url ? `<a class="btn ${yt ? '' : 'primary'}" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">Mở học liệu</a>` : ''}
        <button class="btn" data-act="done" data-id="${l.id}" data-done="${l.done ? 0 : 1}">${l.done ? 'Bỏ đánh dấu đã học' : 'Đánh dấu đã học'}</button></div></div>`;
  }).join('') : '<div class="empty">Chưa có bài giảng nào cho lớp em.</div>');
  actions(page, {
    play: el => {
      $('#vid-' + el.dataset.id).innerHTML = `<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/${el.dataset.yt}" title="Video bài giảng"
        allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`;
      el.remove();
    },
    done: async el => { await api('POST', `/api/s/lessons/${el.dataset.id}/done`, { done: el.dataset.done === '1' }); render(); },
  });
});

route('/s/live', SR, async () => {
  const { sessions } = await api('GET', '/api/s/live');
  shell('/s/live', 'Lịch học trực tuyến', sessions.length ? `<div class="card">${sessions.map(liveItem).join('')}</div>` : '<div class="empty">Chưa có buổi học trực tuyến nào sắp tới.</div>');
});
