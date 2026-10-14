(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const FIELDS = ['category', 'name', 'title', 'company', 'mobile', 'phone', 'fax', 'email', 'website', 'address', 'address2', 'note'];
  const IMAGE_RE = /\.(jpe?g|png|bmp|webp|tiff?|heic|heif)$/i;

  const state = {
    cards: [],
    categories: [],
    filter: 'all',
    search: '',
    sort: { key: 'created_at', asc: false },
    selected: new Set(),
    current: null,
    lastField: null,
    stop: false,
    busy: false,
    newIds: new Set(),
  };

  // ---------- tiện ích ----------
  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (e) { /* bỏ qua */ }
      throw new Error(msg);
    }
    return res.json();
  }
  const jsonOpts = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  let toastTimer;
  function toast(msg, ms = 3000) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), ms);
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fold = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();
  const imgUrl = (c) => `/api/cards/${c.id}/image?v=${c.updated_at}`;

  // ---------- trạng thái bộ nhận dạng ----------
  async function pollStatus() {
    try {
      const s = await api('/api/status');
      state.categories = s.categories;
      const el = $('#engine-status');
      if (s.loading) {
        el.textContent = 'Đang nạp mô hình nhận dạng…';
        el.className = 'pill';
        setTimeout(pollStatus, 1500);
      } else if (!s.ready) {
        el.textContent = 'Lỗi bộ nhận dạng';
        el.className = 'pill warn';
        el.title = s.error;
      } else if (s.recognizer === 'vietocr') {
        el.textContent = 'VietOCR sẵn sàng';
        el.className = 'pill';
        el.title = 'Dữ liệu: ' + s.data_dir;
      } else {
        el.textContent = 'Tạm dùng RapidOCR (không có dấu)';
        el.className = 'pill warn';
        el.title = 'Không nạp được VietOCR: ' + s.vietocr_error;
      }
      renderCategoryOptions();
    } catch (e) {
      setTimeout(pollStatus, 1500);
    }
  }

  function renderCategoryOptions() {
    const opts = state.categories.map((c) => `<option>${esc(c)}</option>`).join('');
    $('#d-cat').innerHTML = opts;
    $('#bulk-cat').innerHTML = '<option value="">Đổi phân loại…</option>' + opts;
    if (state.current) $('#d-cat').value = state.current.category;
  }

  // ---------- danh sách ----------
  async function loadCards() {
    state.cards = await api('/api/cards');
    render();
  }

  function visibleCards() {
    const q = fold(state.search.trim());
    const qDigits = state.search.replace(/\D/g, '');
    let list = state.cards.filter((c) => {
      if (state.filter === 'review' && !c.review) return false;
      if (state.filter !== 'all' && state.filter !== 'review' && c.category !== state.filter) return false;
      if (!q) return true;
      const hay = fold([c.name, c.title, c.company, c.email, c.website, c.address, c.address2, c.note, c.category].join(' '));
      if (hay.includes(q)) return true;
      return qDigits.length >= 3 && [c.mobile, c.phone, c.fax].join(' ').replace(/\D/g, ' ').replace(/ /g, '').includes(qDigits);
    });
    const { key, asc } = state.sort;
    list = list.slice().sort((a, b) => {
      const va = a[key] ?? '';
      const vb = b[key] ?? '';
      const r = typeof va === 'number' ? va - vb : fold(va).localeCompare(fold(vb), 'vi');
      return asc ? r : -r;
    });
    return list;
  }

  function renderSidebar() {
    const counts = {};
    state.cards.forEach((c) => { counts[c.category] = (counts[c.category] || 0) + 1; });
    const review = state.cards.filter((c) => c.review).length;
    const cats = [...new Set([...state.categories, ...Object.keys(counts)])].filter(Boolean);
    const item = (key, label, n) => `<li data-f="${esc(key)}" class="${state.filter === key ? 'active' : ''}"><span>${esc(label)}</span><span class="n">${n}</span></li>`;
    $('#cat-list').innerHTML =
      item('all', 'Tất cả', state.cards.length) +
      item('review', '⚠ Cần kiểm tra', review) +
      '<li class="sep"></li>' +
      cats.map((c) => item(c, c, counts[c] || 0)).join('');
  }

  function render() {
    renderSidebar();
    const list = visibleCards();
    const empty = state.cards.length === 0;
    $('#dropzone').classList.toggle('hidden', !empty);
    $('#table-wrap').classList.toggle('hidden', empty);
    $('#rows').innerHTML = list.map((c) => `
      <tr data-id="${c.id}" class="${state.selected.has(c.id) ? 'selected' : ''} ${state.newIds.has(c.id) ? 'new' : ''}">
        <td class="c-check"><input type="checkbox" class="row-check" ${state.selected.has(c.id) ? 'checked' : ''}></td>
        <td><img src="${imgUrl(c)}" alt="" loading="lazy"></td>
        <td title="${esc(c.name)}"><b>${esc(c.name)}</b></td>
        <td title="${esc(c.title)}">${esc(c.title)}</td>
        <td title="${esc(c.company)}">${esc(c.company)}</td>
        <td>${esc(c.mobile)}</td>
        <td>${esc(c.phone)}</td>
        <td title="${esc(c.email)}">${esc(c.email)}</td>
        <td><span class="cat">${esc(c.category)}</span></td>
        <td class="flag" title="${esc(c.review)}">${c.review ? '⚠' : ''}</td>
      </tr>`).join('');
    state.newIds.clear();
    document.querySelectorAll('th[data-sort]').forEach((th) => {
      th.classList.toggle('sorted', th.dataset.sort === state.sort.key);
      th.classList.toggle('asc', th.dataset.sort === state.sort.key && state.sort.asc);
    });
    $('#footer-count').textContent = empty ? '' : `Đang hiện ${list.length} / ${state.cards.length} danh thiếp`;
    const n = state.selected.size;
    $('#bulk').classList.toggle('hidden', n === 0);
    $('#bulk-count').textContent = `Đã chọn ${n}`;
    $('#check-all').checked = list.length > 0 && list.every((c) => state.selected.has(c.id));
  }

  // ---------- xử lý ảnh hàng loạt ----------
  async function processFiles(fileList) {
    const files = [...fileList].filter((f) => f.type.startsWith('image/') || IMAGE_RE.test(f.name));
    if (!files.length) { toast('Không có file ảnh nào trong lựa chọn.'); return; }
    if (state.busy) { toast('Đang xử lý lượt trước, vui lòng chờ.'); return; }
    state.busy = true;
    state.stop = false;
    const batch = new Date().toISOString();
    $('#progress').classList.remove('hidden');
    $('#progress-errors').innerHTML = '';
    let found = 0;
    const t0 = Date.now();
    for (let i = 0; i < files.length && !state.stop; i++) {
      const f = files[i];
      const eta = i ? Math.round(((Date.now() - t0) / i) * (files.length - i) / 1000) : null;
      $('#progress-label').textContent = `Đang xử lý ${i + 1}/${files.length}: ${f.webkitRelativePath || f.name} — đã tìm thấy ${found} danh thiếp${eta ? ` — còn khoảng ${eta}s` : ''}`;
      $('#progress-bar').style.width = `${(i / files.length) * 100}%`;
      const fd = new FormData();
      fd.append('file', f, f.webkitRelativePath || f.name);
      fd.append('batch', batch);
      try {
        const res = await api('/api/process', { method: 'POST', body: fd });
        if (!res.cards.length) throw new Error('không tìm thấy danh thiếp/chữ nào');
        res.cards.forEach((c) => { state.cards.unshift(c); state.newIds.add(c.id); });
        found += res.cards.length;
        render();
      } catch (e) {
        $('#progress-errors').insertAdjacentHTML('beforeend', `<li>${esc(f.name)}: ${esc(e.message)}</li>`);
      }
    }
    $('#progress-bar').style.width = '100%';
    const errors = $('#progress-errors').children.length;
    $('#progress-label').textContent = `${state.stop ? 'Đã dừng' : 'Xong'}: ${files.length} ảnh → ${found} danh thiếp${errors ? `, ${errors} ảnh lỗi` : ''}. Kiểm tra lại các dòng có dấu ⚠.`;
    state.busy = false;
    if (!errors) setTimeout(() => { if (!state.busy) $('#progress').classList.add('hidden'); }, 8000);
  }

  // ---------- khung chi tiết ----------
  function openDrawer(id) {
    const c = state.cards.find((x) => x.id === id);
    if (!c) return;
    state.current = c;
    $('#drawer').classList.remove('hidden');
    $('#d-title').textContent = c.name || c.company || '(Chưa có tên)';
    $('#d-img').src = imgUrl(c);
    $('#d-source').textContent = c.source_file ? `Ảnh gốc: ${c.source_file}` : '';
    $('#d-review').textContent = c.review ? '⚠ Cần kiểm tra: ' + c.review : '';
    $('#d-review').classList.toggle('hidden', !c.review);
    const form = $('#d-form');
    if (!state.categories.includes(c.category)) $('#d-cat').insertAdjacentHTML('beforeend', `<option>${esc(c.category)}</option>`);
    FIELDS.forEach((f) => { form.elements[f].value = c[f] || ''; });
    $('#d-lines').innerHTML = (c.raw_text || '').split('\n').filter(Boolean)
      .map((l) => `<button type="button" class="chip">${esc(l)}</button>`).join('');
    $('#d-saved').textContent = '';
  }

  async function saveField(name, value) {
    const c = state.current;
    if (!c || c[name] === value) return;
    const fields = { [name]: value };
    // Đã sửa tay thì coi như đã kiểm tra.
    if (c.review && name !== 'note') fields.review = '';
    try {
      const updated = await api(`/api/cards/${c.id}`, jsonOpts('PATCH', { fields }));
      Object.assign(c, updated);
      $('#d-saved').textContent = 'Đã lưu ✓';
      $('#d-review').classList.toggle('hidden', !c.review);
      $('#d-title').textContent = c.name || c.company || '(Chưa có tên)';
      render();
    } catch (e) {
      toast('Lưu thất bại: ' + e.message);
    }
  }

  // ---------- xuất file ----------
  async function exportFile(format, ids = []) {
    try {
      const res = await api('/api/export', jsonOpts('POST', { format, ids, images: $('#opt-images').checked }));
      toast(`Đã xuất ${res.count} danh thiếp ra: ${res.path}`, 6000);
    } catch (e) {
      toast('Xuất file thất bại: ' + e.message);
    }
  }

  // ---------- gắn sự kiện ----------
  function bind() {
    ['#pick-files', '#pick-folder'].forEach((sel) => $(sel).addEventListener('change', (e) => {
      const files = [...e.target.files];
      e.target.value = '';
      processFiles(files);
    }));
    $('#progress-stop').addEventListener('click', () => { state.stop = true; });

    // Kéo thả ảnh vào cửa sổ
    let dragDepth = 0;
    window.addEventListener('dragenter', (e) => { e.preventDefault(); dragDepth++; document.body.classList.add('dragging'); });
    window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove('dragging'); } });
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      dragDepth = 0;
      document.body.classList.remove('dragging');
      if (e.dataTransfer && e.dataTransfer.files.length) processFiles(e.dataTransfer.files);
    });

    $('#search').addEventListener('input', (e) => { state.search = e.target.value; render(); });
    $('#cat-list').addEventListener('click', (e) => {
      const li = e.target.closest('li[data-f]');
      if (li) { state.filter = li.dataset.f; render(); }
    });
    document.querySelectorAll('th[data-sort]').forEach((th) => th.addEventListener('click', () => {
      const key = th.dataset.sort;
      state.sort = { key, asc: state.sort.key === key ? !state.sort.asc : true };
      render();
    }));

    $('#rows').addEventListener('click', (e) => {
      const tr = e.target.closest('tr[data-id]');
      if (!tr) return;
      if (e.target.classList.contains('row-check')) {
        if (e.target.checked) state.selected.add(tr.dataset.id); else state.selected.delete(tr.dataset.id);
        render();
        return;
      }
      openDrawer(tr.dataset.id);
    });
    $('#check-all').addEventListener('change', (e) => {
      visibleCards().forEach((c) => (e.target.checked ? state.selected.add(c.id) : state.selected.delete(c.id)));
      render();
    });

    $('#bulk-cat').addEventListener('change', async (e) => {
      const category = e.target.value;
      if (!category) return;
      const ids = [...state.selected];
      await api('/api/cards/category', jsonOpts('POST', { ids, category }));
      state.cards.forEach((c) => { if (state.selected.has(c.id)) c.category = category; });
      e.target.value = '';
      toast(`Đã chuyển ${ids.length} danh thiếp sang "${category}"`);
      render();
    });
    $('#bulk-delete').addEventListener('click', async () => {
      const ids = [...state.selected];
      if (!confirm(`Xóa ${ids.length} danh thiếp đã chọn?`)) return;
      await api('/api/cards/delete', jsonOpts('POST', { ids }));
      state.cards = state.cards.filter((c) => !state.selected.has(c.id));
      if (state.current && state.selected.has(state.current.id)) $('#drawer').classList.add('hidden');
      state.selected.clear();
      render();
    });
    $('#bulk-export').addEventListener('click', () => exportFile('xlsx', [...state.selected]));

    $('#export-xlsx').addEventListener('click', () => exportFile('xlsx'));
    $('#export-vcf').addEventListener('click', () => exportFile('vcf'));
    $('#reanalyze').addEventListener('click', async () => {
      $('#menu-pop').classList.add('hidden');
      if (!confirm('Phân tích lại chữ đã đọc của mọi danh thiếp bằng bộ tách thông tin mới nhất?\nCác ô bạn đã sửa tay sẽ được giữ nguyên.')) return;
      try {
        const res = await api('/api/reanalyze', { method: 'POST' });
        await loadCards();
        if (state.current) openDrawer(state.current.id);
        toast(`Đã cập nhật ${res.fields} ô thông tin trên ${res.cards} danh thiếp.`, 6000);
      } catch (e) {
        toast('Phân tích lại thất bại: ' + e.message);
      }
    });
    $('#export-calib').addEventListener('click', () => { $('#menu-pop').classList.add('hidden'); exportFile('calib'); });
    $('#menu-btn').addEventListener('click', (e) => { e.stopPropagation(); $('#menu-pop').classList.toggle('hidden'); });
    document.addEventListener('click', (e) => { if (!e.target.closest('.menu')) $('#menu-pop').classList.add('hidden'); });
    document.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', async () => {
      $('#menu-pop').classList.add('hidden');
      const res = await api('/api/open', jsonOpts('POST', { what: b.dataset.open }));
      if (b.dataset.open === 'categories') toast('Sửa file rồi khởi động lại app để áp dụng: ' + res.path, 7000);
    }));

    // Khung chi tiết: lưu từng ô khi rời khỏi ô / đổi giá trị
    $('#d-close').addEventListener('click', () => { $('#drawer').classList.add('hidden'); state.current = null; });
    $('#d-form').addEventListener('submit', (e) => e.preventDefault());
    $('#d-form').addEventListener('change', (e) => { if (e.target.name) saveField(e.target.name, e.target.value.trim()); });
    $('#d-form').addEventListener('focusin', (e) => { if (e.target.name && e.target.name !== 'category') state.lastField = e.target; });
    $('#d-lines').addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const f = state.lastField;
      if (!f) { toast('Bấm vào một ô ở trên trước, rồi bấm dòng chữ.'); return; }
      const text = chip.textContent;
      f.value = (['address', 'address2', 'note'].includes(f.name) && f.value) ? `${f.value}, ${text}` : text;
      saveField(f.name, f.value.trim());
      f.focus();
    });
    $('#d-rotate').addEventListener('click', async () => {
      const c = state.current;
      if (!c) return;
      $('#d-rotate').disabled = true;
      try {
        const updated = await api(`/api/cards/${c.id}/rotate`, { method: 'POST' });
        Object.assign(c, updated);
        openDrawer(c.id);
        render();
      } catch (e) {
        toast('Không đọc lại được: ' + e.message);
      } finally {
        $('#d-rotate').disabled = false;
      }
    });
    $('#d-delete').addEventListener('click', async () => {
      const c = state.current;
      if (!c || !confirm('Xóa danh thiếp này?')) return;
      await api('/api/cards/delete', jsonOpts('POST', { ids: [c.id] }));
      state.cards = state.cards.filter((x) => x.id !== c.id);
      state.selected.delete(c.id);
      $('#drawer').classList.add('hidden');
      state.current = null;
      render();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && state.current) { $('#drawer').classList.add('hidden'); state.current = null; }
    });
  }

  bind();
  pollStatus();
  loadCards();
})();
