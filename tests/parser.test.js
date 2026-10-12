// Chạy: node --test tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const { parseCard, toVCard, toCSV, formatPhone } = require('../web/parser.js');

test('danh thiếp tiếng Việt điển hình', () => {
  const r = parseCard([
    { text: 'CÔNG TY TNHH XÂY DỰNG ABC', height: 30 },
    { text: 'NGUYỄN VĂN AN', height: 42 },
    { text: 'Giám đốc Dự án', height: 20 },
    { text: 'Mobile: 0903 123 456', height: 18 },
    { text: 'Tel: (028) 3823 4567 - Fax: 028 3823 4568', height: 18 },
    { text: 'Email: an.nguyen @ abc.com.vn', height: 18 },
    { text: 'Website: www.abc.com.vn', height: 18 },
    { text: 'Địa chỉ: 123 Nguyễn Huệ, Phường Bến Nghé,', height: 18 },
    { text: 'Quận 1, TP. Hồ Chí Minh', height: 18 },
    { text: 'MST: 0312345678', height: 18 },
  ]);
  assert.equal(r.company, 'CÔNG TY TNHH XÂY DỰNG ABC');
  assert.equal(r.name, 'Nguyễn Văn An');
  assert.equal(r.title, 'Giám đốc Dự án');
  assert.equal(r.mobile, '0903 123 456');
  assert.equal(r.phone, '028 3823 4567');
  assert.equal(r.fax, '028 3823 4568');
  assert.equal(r.email, 'an.nguyen@abc.com.vn');
  assert.equal(r.website, 'www.abc.com.vn');
  assert.equal(r.address, '123 Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh');
});

test('danh thiếp tiếng Anh, số +84', () => {
  const r = parseCard([
    'Tran Thi Bich Ngoc',
    'Senior Sales Manager',
    'XYZ Trading Co., Ltd',
    'M: +84 912 345 678',
    'E: ngoc.tran@xyz.vn',
    'Floor 5, 10 Ly Thuong Kiet Street, Hoan Kiem District, Ha Noi',
  ]);
  assert.equal(r.name, 'Tran Thi Bich Ngoc');
  assert.equal(r.title, 'Senior Sales Manager');
  assert.equal(r.company, 'XYZ Trading Co., Ltd');
  assert.equal(r.mobile, '0912 345 678');
  assert.equal(r.email, 'ngoc.tran@xyz.vn');
  assert.match(r.address, /^Floor 5, 10 Ly Thuong Kiet/);
});

test('hai số di động trên một dòng, mã số thuế bị bỏ qua', () => {
  const r = parseCard(['Lê Minh Tuấn', 'HP: 0903 111 222 / 0988 333 444', 'Mã số thuế: 0101234567']);
  assert.equal(r.mobile, '0903 111 222');
  assert.equal(r.phone, '0988 333 444');
  assert.equal(r.note, '');
});

test('định dạng số điện thoại', () => {
  assert.equal(formatPhone('0903123456'), '0903 123 456');
  assert.equal(formatPhone('+84 28 3823 4567'), '028 3823 4567');
});

test('xuất vCard và CSV', () => {
  const c = { name: 'Nguyễn Văn An', company: 'ABC; JSC', mobile: '0903 123 456', address: '1 Lê Lợi, Q.1' };
  const v = toVCard(c);
  assert.match(v, /N:Nguyễn;Văn An;;;/);
  assert.match(v, /ORG:ABC\\; JSC/);
  assert.match(v, /ADR;TYPE=WORK:;;1 Lê Lợi\\, Q.1;;;;/);
  const csv = toCSV([c]);
  assert.ok(csv.startsWith('﻿"Họ tên"'));
  assert.match(csv, /"0903 123 456"/);
});
