(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const FIELDS = ['name', 'title', 'company', 'mobile', 'phone', 'fax', 'email', 'website', 'address', 'note'];
  const FIELD_LABELS = {
    name: 'Họ tên', title: 'Chức vụ', company: 'Công ty', mobile: 'Di động', phone: 'Điện thoại',
    fax: 'Fax', email: 'Email', website: 'Website', address: 'Địa chỉ', note: 'Ghi chú',
  };
  const TESSERACT_URL = 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js';
  const OCR_MAX_SIDE = 1600;
  const PHOTO_MAX_SIDE = 1000;

  // ---------- Cài đặt (lưu trong localStorage) ----------
  const settings = { engine: 'auto', server: '', token: '' };
  try {
    Object.assign(settings, JSON.parse(localStorage.getItem('settings') || '{}'));
  } catch (e) { /* bỏ qua */ }
  function saveSettings() {
    try { localStorage.setItem('settings', JSON.stringify(settings)); } catch (e) { /* bỏ qua */ }
  }

  // ---------- Tiện ích ----------
  function show(view) {
    document.querySelectorAll('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-' + view));
    window.scrollTo(0, 0);
  }

  let toastTimer;
  function toast(msg, ms = 2500) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), ms);
  }

  function setStatus(msg, kind) {
    const el = $('#ocr-status');
    if (!msg) { el.classList.add('hidden'); return; }
    el.className = 'status' + (kind ? ' ' + kind : '');
    el.textContent = msg;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  }

  function serverBase() {
    return (settings.server || location.origin).replace(/\/+$/, '');
  }

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Không mở được ảnh'));
      img.src = src;
    });
  }

  // Vẽ ảnh lên canvas (có thể xoay 90°) và thu nhỏ về cạnh dài tối đa maxSide.
  function drawScaled(img, maxSide, quarterTurns = 0) {
    const w0 = img.naturalWidth || img.width;
    const h0 = img.naturalHeight || img.height;
    const scale = Math.min(1, maxSide / Math.max(w0, h0));
    const w = Math.round(w0 * scale);
    const h = Math.round(h0 * scale);
    const turned = quarterTurns % 2 === 1;
    const canvas = document.createElement('canvas');
    canvas.width = turned ? h : w;
    canvas.height = turned ? w : h;
    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((quarterTurns * Math.PI) / 2);
    ctx.drawImage(img, -w / 2, -h / 2, w, h);
    return canvas;
  }

  function canvasToBlob(canvas, quality = 0.88) {
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
  }

  async function shareFile(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const file = new File([blob], filename, { type: mime });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: filename });
        return;
      } catch (e) {
        if (e.name === 'AbortError') return;
      }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  // ---------- Nhận dạng chữ ----------
  async function ocrServer(blob) {
    const fd = new FormData();
    fd.append('file', blob, 'card.jpg');
    const ctrl = new AbortController();
    // Server miễn phí có thể đang "ngủ", lần đầu cần ~1–2 phút để thức dậy.
    const timer = setTimeout(() => ctrl.abort(), 150000);
    try {
      const res = await fetch(serverBase() + '/api/ocr', {
        method: 'POST',
        body: fd,
        headers: settings.token ? { 'X-App-Token': settings.token } : {},
        signal: ctrl.signal,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail || detail; } catch (e) { /* bỏ qua */ }
        throw new Error(`Server lỗi ${res.status}: ${detail}`);
      }
      const data = await res.json();
      return data.lines.map((l) => ({ text: l.text, height: l.height }));
    } finally {
      clearTimeout(timer);
    }
  }

  let tesseractWorker = null;
  async function ocrTesseract(canvas) {
    if (!window.Tesseract) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = TESSERACT_URL;
        s.onload = resolve;
        s.onerror = () => reject(new Error('Không tải được Tesseract (cần Internet lần đầu)'));
        document.head.appendChild(s);
      });
    }
    if (!tesseractWorker) tesseractWorker = await window.Tesseract.createWorker('vie+eng');
    const { data } = await tesseractWorker.recognize(canvas);
    return data.text.split('\n').map((t) => t.trim()).filter(Boolean).map((text) => ({ text, height: 0 }));
  }

  async function runOCR(canvas) {
    const blob = await canvasToBlob(canvas);
    if (settings.engine !== 'tesseract') {
      try {
        setStatus('Đang nhận dạng bằng VietOCR… (lần đầu có thể mất 1–2 phút nếu server đang ngủ)');
        return { lines: await ocrServer(blob), engine: 'VietOCR' };
      } catch (e) {
        if (settings.engine === 'server') throw e;
        console.warn('VietOCR lỗi, chuyển sang Tesseract', e);
      }
    }
    setStatus('Đang nhận dạng bằng Tesseract trên iPhone…');
    return { lines: await ocrTesseract(canvas), engine: 'Tesseract' };
  }

  // ---------- Màn hình chỉnh sửa ----------
  const editor = { card: null, isNew: false, img: null, turns: 0, lastField: null };

  function fillForm(card) {
    const form = $('#edit-form');
    FIELDS.forEach((f) => { form.elements[f].value = card[f] || ''; });
  }

  function readForm() {
    const form = $('#edit-form');
    const out = {};
    FIELDS.forEach((f) => { out[f] = form.elements[f].value.trim(); });
    return out;
  }

  function renderRawLines(lines) {
    const wrap = $('#raw-lines');
    wrap.innerHTML = lines.map((l, i) => `<button type="button" class="chip" data-i="${i}">${esc(l)}</button>`).join('');
    $('#raw-wrap').classList.toggle('hidden', lines.length === 0);
  }

  async function startNewCard(file) {
    let img;
    const url = URL.createObjectURL(file);
    try {
      img = await loadImage(url);
    } catch (e) {
      toast('Không mở được ảnh này');
      return;
    } finally {
      URL.revokeObjectURL(url);
    }
    editor.card = { id: uid(), createdAt: Date.now() };
    editor.isNew = true;
    editor.img = img;
    editor.turns = 0;
    fillForm({});
    renderRawLines([]);
    $('#edit-heading').textContent = 'Danh thiếp mới';
    show('edit');
    await recognizeCurrent(true);
  }

  async function recognizeCurrent(overwrite) {
    const photo = drawScaled(editor.img, PHOTO_MAX_SIDE, editor.turns);
    editor.card.photo = photo.toDataURL('image/jpeg', 0.8);
    $('#edit-photo').src = editor.card.photo;
    const ocrCanvas = drawScaled(editor.img, OCR_MAX_SIDE, editor.turns);
    $('#edit-save').disabled = true;
    try {
      const { lines, engine } = await runOCR(ocrCanvas);
      const parsed = CardParser.parseCard(lines);
      const current = readForm();
      const merged = {};
      FIELDS.forEach((f) => { merged[f] = overwrite || !current[f] ? parsed[f] || current[f] : current[f]; });
      fillForm(merged);
      editor.card.rawText = lines.map((l) => l.text).join('\n');
      renderRawLines(lines.map((l) => l.text));
      setStatus(lines.length ? `Đã nhận dạng ${lines.length} dòng bằng ${engine}. Hãy kiểm tra lại các ô.` : 'Không tìm thấy chữ. Thử chụp lại rõ hơn hoặc xoay ảnh.', lines.length ? 'ok' : 'warn');
    } catch (e) {
      setStatus('Không nhận dạng được: ' + e.message.replace(/\.+$/, '') + '. Bạn vẫn có thể tự nhập.', 'warn');
    } finally {
      $('#edit-save').disabled = false;
    }
  }

  async function openEditor(card) {
    editor.card = { ...card };
    editor.isNew = false;
    editor.turns = 0;
    editor.img = card.photo ? await loadImage(card.photo) : null;
    fillForm(card);
    renderRawLines((card.rawText || '').split('\n').filter(Boolean));
    $('#edit-photo').src = card.photo || '';
    $('#edit-heading').textContent = 'Sửa danh thiếp';
    setStatus('');
    show('edit');
  }

  async function saveEditor() {
    const data = readForm();
    if (!FIELDS.some((f) => data[f])) {
      toast('Chưa có thông tin nào để lưu');
      return;
    }
    const card = { ...editor.card, ...data, updatedAt: Date.now() };
    await CardDB.put(card);
    toast('Đã lưu');
    await renderList();
    if (editor.isNew) show('list');
    else openDetail(card.id);
  }

  // ---------- Danh sách ----------
  let allCards = [];

  async function renderList() {
    allCards = await CardDB.all();
    const q = CardParser.normalize($('#search').value).toLowerCase();
    const strip = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd');
    const qs = strip(q);
    const cards = q
      ? allCards.filter((c) => strip([c.name, c.company, c.title, c.mobile, c.phone, c.email, c.note].join(' ').toLowerCase()).includes(qs)
        || [c.mobile, c.phone].join(' ').replace(/\s/g, '').includes(q.replace(/\s/g, '')))
      : allCards;
    $('#list').innerHTML = cards.map((c) => `
      <li data-id="${esc(c.id)}">
        ${c.photo ? `<img src="${c.photo}" alt="">` : '<div class="noimg">🪪</div>'}
        <div class="info">
          <div class="name">${esc(c.name || c.company || '(Chưa có tên)')}</div>
          <div class="sub">${esc([c.title, c.name ? c.company : ''].filter(Boolean).join(' · '))}</div>
          <div class="sub">${esc(c.mobile || c.phone || c.email || '')}</div>
        </div>
      </li>`).join('');
    $('#empty').classList.toggle('hidden', allCards.length > 0);
    $('#count').textContent = allCards.length ? `${cards.length}/${allCards.length} danh thiếp` : '';
  }

  // ---------- Chi tiết ----------
  let detailId = null;

  async function openDetail(id) {
    const c = await CardDB.get(id);
    if (!c) return;
    detailId = id;
    $('#detail-photo').src = c.photo || '';
    $('#detail-photo').classList.toggle('hidden', !c.photo);
    $('#detail-name').textContent = c.name || c.company || '(Chưa có tên)';
    $('#detail-sub').textContent = [c.title, c.name ? c.company : ''].filter(Boolean).join(' · ');
    const link = (f, v) => {
      const tel = v.replace(/[^\d+]/g, '');
      if (f === 'mobile' || f === 'phone') return `<a href="tel:${esc(tel)}">${esc(v)}</a>`;
      if (f === 'email') return `<a href="mailto:${esc(v)}">${esc(v)}</a>`;
      if (f === 'website') return `<a href="${esc(/^https?:/i.test(v) ? v : 'http://' + v)}" target="_blank" rel="noopener">${esc(v)}</a>`;
      if (f === 'address') return `<a href="https://maps.apple.com/?q=${encodeURIComponent(v)}" target="_blank" rel="noopener">${esc(v)}</a>`;
      return esc(v).replace(/\n/g, '<br>');
    };
    $('#detail-fields').innerHTML = ['mobile', 'phone', 'fax', 'email', 'website', 'address', 'note']
      .filter((f) => c[f])
      .map((f) => `<div class="field"><span class="label">${FIELD_LABELS[f]}</span><span class="value">${link(f, c[f])}</span></div>`)
      .join('') + `<div class="field"><span class="label">Ngày quét</span><span class="value">${new Date(c.createdAt).toLocaleString('vi-VN')}</span></div>`;
    show('detail');
  }

  function fileSafe(s) {
    return (s || 'danh-thiep').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').replace(/[^\w-]+/g, '_').slice(0, 40);
  }

  // ---------- Sao lưu ----------
  async function backup() {
    const cards = await CardDB.all();
    const data = JSON.stringify({ app: 'danh-thiep', version: 1, exportedAt: new Date().toISOString(), cards });
    const day = new Date().toISOString().slice(0, 10);
    await shareFile(`danh-thiep-saoluu-${day}.json`, data, 'application/json');
  }

  async function restore(file) {
    try {
      const data = JSON.parse(await file.text());
      if (!Array.isArray(data.cards)) throw new Error('Tệp không đúng định dạng');
      let n = 0;
      for (const c of data.cards) {
        if (c && c.id) { await CardDB.put(c); n++; }
      }
      await renderList();
      toast(`Đã khôi phục ${n} danh thiếp`);
    } catch (e) {
      toast('Khôi phục thất bại: ' + e.message, 4000);
    }
  }

  async function showStorageInfo() {
    const el = $('#storage-info');
    const parts = [`Đang lưu ${allCards.length} danh thiếp.`];
    try {
      if (navigator.storage && navigator.storage.estimate) {
        const { usage } = await navigator.storage.estimate();
        parts.push(`Dung lượng dùng: ${(usage / 1048576).toFixed(1)} MB.`);
      }
      if (navigator.storage && navigator.storage.persisted && (await navigator.storage.persisted())) {
        parts.push('Bộ nhớ đã được đánh dấu lưu lâu dài.');
      }
    } catch (e) { /* bỏ qua */ }
    el.textContent = parts.join(' ');
  }

  // ---------- Gắn sự kiện ----------
  function bind() {
    document.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => {
      if (b.dataset.go === 'settings') { showStorageInfo(); }
      show(b.dataset.go);
    }));

    ['#pick-camera', '#pick-library'].forEach((sel) => {
      $(sel).addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        e.target.value = '';
        if (file) startNewCard(file);
      });
    });

    $('#search').addEventListener('input', renderList);
    $('#list').addEventListener('click', (e) => {
      const li = e.target.closest('li[data-id]');
      if (li) openDetail(li.dataset.id);
    });

    $('#edit-cancel').addEventListener('click', () => {
      if (editor.isNew) show('list');
      else openDetail(editor.card.id);
    });
    $('#edit-save').addEventListener('click', saveEditor);
    $('#edit-form').addEventListener('submit', (e) => e.preventDefault());
    $('#edit-form').addEventListener('focusin', (e) => {
      if (e.target.name) editor.lastField = e.target;
    });
    // Chạm vào dòng chữ: điền vào ô vừa chọn (địa chỉ/ghi chú thì nối thêm)
    $('#raw-lines').addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const field = editor.lastField;
      if (!field) { toast('Hãy chạm vào một ô ở trên trước'); return; }
      const text = chip.textContent;
      if ((field.name === 'address' || field.name === 'note') && field.value) field.value += ', ' + text;
      else field.value = text;
      toast(`Đã điền vào "${FIELD_LABELS[field.name]}"`, 1200);
    });
    $('#rotate-btn').addEventListener('click', async () => {
      if (!editor.img) return;
      editor.turns = (editor.turns + 1) % 4;
      await recognizeCurrent(editor.isNew);
    });
    $('#reocr-btn').addEventListener('click', () => editor.img && recognizeCurrent(false));

    $('#detail-edit').addEventListener('click', async () => openEditor(await CardDB.get(detailId)));
    $('#detail-delete').addEventListener('click', async () => {
      if (!confirm('Xóa danh thiếp này?')) return;
      await CardDB.remove(detailId);
      await renderList();
      show('list');
      toast('Đã xóa');
    });
    $('#detail-vcard').addEventListener('click', async () => {
      const c = await CardDB.get(detailId);
      await shareFile(fileSafe(c.name || c.company) + '.vcf', CardParser.toVCard(c), 'text/vcard');
    });

    // Cài đặt
    $('#set-engine').value = settings.engine;
    $('#set-server').value = settings.server;
    $('#set-token').value = settings.token;
    $('#set-engine').addEventListener('change', (e) => { settings.engine = e.target.value; saveSettings(); });
    $('#set-server').addEventListener('change', (e) => { settings.server = e.target.value.trim(); saveSettings(); });
    $('#set-token').addEventListener('change', (e) => { settings.token = e.target.value.trim(); saveSettings(); });
    $('#test-server').addEventListener('click', async () => {
      const out = $('#server-result');
      out.textContent = 'Đang kiểm tra… (server đang ngủ có thể mất 1–2 phút)';
      try {
        const res = await fetch(serverBase() + '/api/health');
        const h = await res.json();
        out.textContent = h.ocr ? '✅ Server VietOCR hoạt động.' : '⚠️ Server chạy nhưng VietOCR chưa sẵn sàng.';
        if (h.token_required && !settings.token) out.textContent += ' Server yêu cầu mã truy cập.';
      } catch (e) {
        out.textContent = '❌ Không kết nối được: ' + e.message;
      }
    });
    $('#export-csv').addEventListener('click', async () => {
      const cards = await CardDB.all();
      if (!cards.length) return toast('Chưa có dữ liệu');
      await shareFile(`danh-thiep-${new Date().toISOString().slice(0, 10)}.csv`, CardParser.toCSV(cards), 'text/csv');
    });
    $('#export-vcf').addEventListener('click', async () => {
      const cards = await CardDB.all();
      if (!cards.length) return toast('Chưa có dữ liệu');
      await shareFile('danh-thiep.vcf', cards.map(CardParser.toVCard).join('\r\n'), 'text/vcard');
    });
    $('#backup').addEventListener('click', backup);
    $('#restore').addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      e.target.value = '';
      if (file) restore(file);
    });
  }

  bind();
  renderList();
  // Xin Safari giữ dữ liệu lâu dài (không tự xóa khi máy thiếu dung lượng).
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
})();
