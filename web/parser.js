// Tách các trường (tên, chức vụ, công ty, điện thoại...) từ các dòng chữ OCR của danh thiếp.
// Dùng được cả trong trình duyệt (window.CardParser) và Node (module.exports) để chạy test.
(function (root) {
  'use strict';

  const SURNAMES = [
    'nguyễn', 'trần', 'lê', 'phạm', 'hoàng', 'huỳnh', 'phan', 'vũ', 'võ', 'đặng', 'bùi', 'đỗ',
    'hồ', 'ngô', 'dương', 'lý', 'đào', 'đoàn', 'vương', 'trịnh', 'trương', 'đinh', 'lâm', 'mai',
    'tô', 'tạ', 'hà', 'lương', 'lưu', 'cao', 'châu', 'chu', 'quách', 'thái', 'tăng', 'văn', 'kiều',
    'la', 'triệu', 'từ', 'khổng', 'hứa', 'nghiêm', 'đàm', 'lại', 'phùng', 'tiêu', 'giang', 'âu',
    'nguyen', 'tran', 'le', 'pham', 'hoang', 'huynh', 'vu', 'vo', 'dang', 'bui', 'do', 'ho', 'ngo',
    'duong', 'ly', 'dao', 'doan', 'vuong', 'trinh', 'truong', 'dinh', 'lam', 'luong', 'luu', 'chau',
  ];

  const COMPANY_KW = [
    'công ty', 'cty', 'tnhh', 'cổ phần', 'cp', 'jsc', 'co.', 'co.,', 'ltd', 'llc', 'inc', 'corp',
    'corporation', 'company', 'group', 'tập đoàn', 'ngân hàng', 'bank', 'chi nhánh', 'văn phòng đại diện',
    'bệnh viện', 'hospital', 'trường', 'university', 'đại học', 'viện', 'institute', 'hợp tác xã',
    'doanh nghiệp', 'enterprise', 'holdings', 'limited', 'trading', 'xây dựng', 'construction',
  ];

  const TITLE_KW = [
    'giám đốc', 'gđ', 'phó', 'trưởng', 'chủ tịch', 'kỹ sư', 'ks', 'kế toán', 'nhân viên', 'chuyên viên',
    'tư vấn', 'quản lý', 'trợ lý', 'thư ký', 'kiến trúc sư', 'kts', 'bác sĩ', 'luật sư', 'thạc sĩ',
    'tiến sĩ', 'chỉ huy', 'giám sát', 'điều phối', 'đại diện', 'kinh doanh', 'sáng lập',
    'director', 'manager', 'ceo', 'cto', 'cfo', 'coo', 'cmo', 'founder', 'co-founder', 'president',
    'engineer', 'sales', 'executive', 'officer', 'head', 'lead', 'leader', 'consultant', 'specialist',
    'assistant', 'representative', 'supervisor', 'partner', 'chairman', 'deputy', 'vice', 'architect',
    'accountant', 'coordinator', 'designer', 'developer', 'owner', 'general', 'senior', 'qs',
  ];

  const ADDRESS_KW = [
    'địa chỉ', 'đ/c', 'đc', 'add', 'addr', 'address', 'số', 'đường', 'phố', 'phường', 'quận', 'huyện',
    'tỉnh', 'thành phố', 'tp', 'tx', 'thị xã', 'thị trấn', 'xã', 'ấp', 'thôn', 'khu phố', 'kp', 'lô',
    'kcn', 'khu công nghiệp', 'tầng', 'tòa', 'tòa nhà', 'lầu', 'ngõ', 'ngách', 'hẻm', 'kiệt',
    'street', 'st', 'road', 'rd', 'ward', 'district', 'dist', 'city', 'province', 'floor', 'building',
    'tower', 'lot', 'hà nội', 'ha noi', 'hồ chí minh', 'ho chi minh', 'hcm', 'đà nẵng', 'da nang',
    'việt nam', 'vietnam', 'viet nam', 'q.', 'p.',
  ];

  const IGNORE_KW = ['mst', 'mã số thuế', 'tax code', 'tax id', 'stk', 'số tài khoản', 'account', 'a/c'];

  const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/;
  const WEB_RE = /\b(?:https?:\/\/)?(?:www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com\.vn|net\.vn|org\.vn|edu\.vn|gov\.vn|vn|com|net|org|info|biz|io|co|asia)\b(?:\/\S*)?/i;
  const PHONE_RE = /(?:\+?\(?\d[\d\s.\-()]{7,}\d)/g;

  function normalize(s) {
    return (s || '').normalize('NFC').replace(/\s+/g, ' ').trim();
  }

  function lower(s) {
    return normalize(s).toLowerCase();
  }

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  // Tìm từ khóa đứng riêng (không nằm giữa một từ khác), hỗ trợ chữ có dấu.
  function hasKeyword(text, keywords) {
    const t = lower(text);
    return keywords.some((kw) => {
      const re = new RegExp('(^|[^\\p{L}])' + escapeRe(kw) + '(?=$|[^\\p{L}])', 'u');
      return re.test(t);
    });
  }

  function stripLabel(text) {
    return normalize(text)
      .replace(/^(địa chỉ|đ\/c|add(ress)?|addr|a|văn phòng|vp|office|trụ sở|head office|showroom|nhà máy|factory)\s*[:.\-]\s*/i, '')
      .trim();
  }

  function digitsOf(s) {
    return (s.match(/\d/g) || []).join('');
  }

  function formatPhone(raw) {
    let d = digitsOf(raw);
    const plus = /^\s*\+/.test(raw) || d.startsWith('84');
    if (d.startsWith('84') && (d.length === 11 || d.length === 12)) d = '0' + d.slice(2);
    if (plus && !d.startsWith('0') && !d.startsWith('84')) return '+' + d;
    // 10 số (di động): 0903 123 456 ; 11 số (bàn): 028 3823 4567
    if (d.length === 10) return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`;
    if (d.length === 11) return `${d.slice(0, 3)} ${d.slice(3, 7)} ${d.slice(7)}`;
    return d;
  }

  function isMobile(raw) {
    let d = digitsOf(raw);
    if (d.startsWith('84')) d = '0' + d.slice(2);
    return d.length === 10 && /^0[35789]/.test(d);
  }

  // Sửa các lỗi OCR hay gặp trong email: khoảng trắng quanh @ và dấu chấm.
  function fixEmailSpacing(s) {
    return s.replace(/\s*@\s*/g, '@').replace(/(@[^\s]*?)\s*\.\s*/g, '$1.');
  }

  function toTitleCase(s) {
    return s
      .toLowerCase()
      .split(' ')
      .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
      .join(' ');
  }

  function looksLikeName(text) {
    const t = normalize(text).replace(/^(mr|mrs|ms|miss|dr|ông|bà|anh|chị)\.?\s+/i, '');
    if (/\d|@|[:/|]/.test(t)) return false;
    const words = t.split(' ').filter(Boolean);
    if (words.length < 2 || words.length > 5) return false;
    return words.every((w) => /^\p{Lu}[\p{L}'’-]*\.?$/u.test(w));
  }

  function parseCard(input) {
    // input: mảng chuỗi, hoặc mảng {text, height}
    const lines = (input || [])
      .map((l, i) => (typeof l === 'string' ? { text: l, height: 0, index: i } : { ...l, index: i }))
      .map((l) => ({ ...l, text: normalize(l.text) }))
      .filter((l) => l.text.length > 0);

    const result = {
      name: '', title: '', company: '', mobile: '', phone: '', fax: '',
      email: '', website: '', address: '', note: '',
    };
    const used = new Set();

    // 1. Email & website
    for (const l of lines) {
      const fixed = fixEmailSpacing(l.text);
      const em = fixed.match(EMAIL_RE);
      if (em && !result.email) {
        result.email = em[0].toLowerCase();
        used.add(l.index);
      }
      const rest = em ? fixed.replace(em[0], ' ') : l.text;
      const web = rest.match(WEB_RE);
      if (web && !result.website && !/@/.test(web[0])) {
        result.website = web[0].replace(/[.,;]+$/, '').toLowerCase();
        used.add(l.index);
      }
    }

    // 2. Điện thoại, di động, fax
    const extraPhones = [];
    for (const l of lines) {
      if (hasKeyword(l.text, IGNORE_KW)) continue;
      const lt = lower(l.text);
      const matches = [];
      for (const m of l.text.match(PHONE_RE) || []) {
        // Hai số viết liền nhau ("0903 123 456 - 0912 345 678") thì tách ra
        if (digitsOf(m).length > 13) matches.push(...m.split(/\s*[–\/|;]\s*|\s-\s/));
        else matches.push(m);
      }
      let found = false;
      for (const m of matches) {
        const d = digitsOf(m);
        if (d.length < 9 || d.length > 13) continue;
        found = true;
        const formatted = formatPhone(m);
        // Nhãn đứng ngay trước số điện thoại (vd. "Fax:", "Mobile:", "HP:")
        const idx = l.text.indexOf(m);
        const label = lt.slice(Math.max(0, idx - 14), Math.max(0, idx));
        if (/fax|\bf\s*[:.]/.test(label) || (/fax/.test(lt) && !/(tel|điện thoại|mobile|hp|dđ)/.test(lt))) {
          if (!result.fax) result.fax = formatted; else extraPhones.push(formatted);
        } else if (/(mobile|mob|cell|hp|h\/p|dđ|di động|hotline|\bm\s*[:.])/.test(label) || isMobile(m)) {
          if (!result.mobile) result.mobile = formatted;
          else extraPhones.push(formatted);
        } else if (!result.phone) {
          result.phone = formatted;
        } else {
          extraPhones.push(formatted);
        }
      }
      if (found) used.add(l.index);
    }
    if (!result.phone && extraPhones.length) result.phone = extraPhones.shift();
    if (extraPhones.length) result.note = 'SĐT khác: ' + extraPhones.join(', ');

    // 3. Công ty
    const companyLines = lines.filter((l) => !used.has(l.index) && hasKeyword(l.text, COMPANY_KW));
    if (companyLines.length) {
      // Ưu tiên dòng có "công ty"/"company" rõ ràng, rồi tới dòng dài nhất
      companyLines.sort((a, b) => {
        const sa = /công ty|company|cty|tập đoàn|group|ngân hàng|bank/i.test(a.text) ? 1 : 0;
        const sb = /công ty|company|cty|tập đoàn|group|ngân hàng|bank/i.test(b.text) ? 1 : 0;
        return sb - sa || b.text.length - a.text.length;
      });
      result.company = companyLines[0].text;
      used.add(companyLines[0].index);
    }

    // 4. Địa chỉ: gom các dòng có từ khóa địa chỉ (thường nằm liền nhau)
    const addrLines = lines.filter(
      (l) => !used.has(l.index) && (hasKeyword(l.text, ADDRESS_KW) && (/\d/.test(l.text) || /,/.test(l.text) || /^(địa chỉ|add|address|đ\/c)/i.test(l.text)))
    );
    if (addrLines.length) {
      const first = addrLines[0];
      const group = [first];
      for (const l of addrLines.slice(1)) {
        if (l.index - group[group.length - 1].index <= 2) group.push(l);
      }
      result.address = group.map((l) => stripLabel(l.text)).join(', ').replace(/,\s*,/g, ',');
      group.forEach((l) => used.add(l.index));
    }

    // 5. Chức vụ
    const titleLine = lines.find(
      (l) => !used.has(l.index) && hasKeyword(l.text, TITLE_KW) && !/\d/.test(l.text) && l.text.split(' ').length <= 10
    );
    if (titleLine) {
      result.title = titleLine.text;
      used.add(titleLine.index);
    }

    // 6. Họ tên: chọn dòng giống tên người nhất
    const maxH = Math.max(1, ...lines.map((l) => l.height || 0));
    let best = null;
    let bestScore = -Infinity;
    for (const l of lines) {
      if (used.has(l.index) || !looksLikeName(l.text)) continue;
      const words = l.text.split(' ');
      let score = 0;
      if (SURNAMES.includes(lower(words[0]).replace(/^(mr|mrs|ms|dr)\.?$/, ''))) score += 3;
      if (l.height) score += (2 * l.height) / maxH;
      if (titleLine && Math.abs(l.index - titleLine.index) === 1) score += 2;
      if (words.length >= 2 && words.length <= 4) score += 1;
      if (hasKeyword(l.text, ADDRESS_KW)) score -= 2;
      if (score > bestScore) {
        bestScore = score;
        best = l;
      }
    }
    if (best) {
      let name = best.text.replace(/^(mr|mrs|ms|miss|dr|ông|bà)\.?\s+/i, '');
      if (name === name.toUpperCase()) name = toTitleCase(name);
      result.name = name;
      used.add(best.index);
    }

    return result;
  }

  // ---------- Xuất vCard / CSV ----------

  function vEscape(s) {
    return String(s || '').replace(/\\/g, '\\\\').replace(/\n/g, '\\n').replace(/([,;])/g, '\\$1');
  }

  // Tên người Việt: từ đầu là họ, phần còn lại là tên đệm + tên.
  function splitVietnameseName(full) {
    const words = normalize(full).split(' ').filter(Boolean);
    if (words.length <= 1) return { family: '', given: words[0] || '' };
    return { family: words[0], given: words.slice(1).join(' ') };
  }

  function toVCard(c) {
    const { family, given } = splitVietnameseName(c.name);
    const out = ['BEGIN:VCARD', 'VERSION:3.0'];
    out.push(`N:${vEscape(family)};${vEscape(given)};;;`);
    out.push(`FN:${vEscape(c.name || c.company || 'Danh thiếp')}`);
    if (c.company) out.push(`ORG:${vEscape(c.company)}`);
    if (c.title) out.push(`TITLE:${vEscape(c.title)}`);
    if (c.mobile) out.push(`TEL;TYPE=CELL,VOICE:${c.mobile}`);
    if (c.phone) out.push(`TEL;TYPE=WORK,VOICE:${c.phone}`);
    if (c.fax) out.push(`TEL;TYPE=WORK,FAX:${c.fax}`);
    if (c.email) out.push(`EMAIL;TYPE=INTERNET,WORK:${c.email}`);
    if (c.website) out.push(`URL:${/^https?:/i.test(c.website) ? c.website : 'http://' + c.website}`);
    if (c.address) out.push(`ADR;TYPE=WORK:;;${vEscape(c.address)};;;;`);
    if (c.note) out.push(`NOTE:${vEscape(c.note)}`);
    out.push('END:VCARD');
    return out.join('\r\n');
  }

  const CSV_COLUMNS = [
    ['name', 'Họ tên'], ['title', 'Chức vụ'], ['company', 'Công ty'], ['mobile', 'Di động'],
    ['phone', 'Điện thoại'], ['fax', 'Fax'], ['email', 'Email'], ['website', 'Website'],
    ['address', 'Địa chỉ'], ['note', 'Ghi chú'], ['createdAt', 'Ngày quét'],
  ];

  function csvCell(v) {
    const s = String(v == null ? '' : v);
    // Chặn Excel hiểu nhầm ô bắt đầu bằng = + - @ là công thức.
    const safe = /^[=+\-@]/.test(s) ? "'" + s : s;
    return '"' + safe.replace(/"/g, '""') + '"';
  }

  function toCSV(contacts) {
    const header = CSV_COLUMNS.map(([, label]) => csvCell(label)).join(',');
    const rows = contacts.map((c) =>
      CSV_COLUMNS.map(([key]) => {
        let v = c[key];
        if (key === 'createdAt' && v) v = new Date(v).toLocaleString('vi-VN');
        return csvCell(v);
      }).join(',')
    );
    return '\uFEFF' + [header, ...rows].join('\r\n');
  }

  const api = { parseCard, toVCard, toCSV, formatPhone, splitVietnameseName, normalize };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.CardParser = api;
})(typeof self !== 'undefined' ? self : this);
