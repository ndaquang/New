"""Tách các trường (tên, chức vụ, công ty, điện thoại...) từ các dòng chữ OCR của danh thiếp."""

import re
import unicodedata

SURNAMES = {
    "nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ", "đặng", "bùi", "đỗ",
    "hồ", "ngô", "dương", "lý", "đào", "đoàn", "vương", "trịnh", "trương", "đinh", "lâm", "mai",
    "tô", "tạ", "hà", "lương", "lưu", "cao", "châu", "chu", "quách", "thái", "tăng", "kiều",
    "la", "triệu", "từ", "khổng", "hứa", "nghiêm", "đàm", "lại", "phùng", "tiêu", "giang", "âu",
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "vu", "vo", "dang", "bui", "do", "ho", "ngo",
    "duong", "ly", "dao", "doan", "vuong", "trinh", "truong", "dinh", "lam", "luong", "luu", "chau",
}

COMPANY_KW = [
    "công ty", "cty", "tnhh", "cổ phần", "cp", "jsc", "co.", "co.,", "ltd", "llc", "inc", "corp",
    "corporation", "company", "group", "tập đoàn", "ngân hàng", "bank", "chi nhánh", "văn phòng đại diện",
    "bệnh viện", "hospital", "university", "đại học", "institute", "hợp tác xã",
    "doanh nghiệp", "enterprise", "holdings", "limited", "joint stock",
]

TITLE_KW = [
    "giám đốc", "gđ", "phó", "trưởng", "chủ tịch", "kỹ sư", "ks", "kế toán", "nhân viên", "chuyên viên",
    "tư vấn", "quản lý", "trợ lý", "thư ký", "kiến trúc sư", "kts", "bác sĩ", "luật sư", "thạc sĩ",
    "tiến sĩ", "chỉ huy", "giám sát", "điều phối", "đại diện", "kinh doanh", "sáng lập",
    "director", "manager", "ceo", "cto", "cfo", "coo", "cmo", "founder", "co-founder", "president",
    "engineer", "sales", "executive", "officer", "head", "lead", "leader", "consultant", "specialist",
    "assistant", "representative", "supervisor", "partner", "chairman", "deputy", "vice", "architect",
    "accountant", "coordinator", "designer", "developer", "owner", "general", "senior", "qs",
]

ADDRESS_KW = [
    "địa chỉ", "đ/c", "đc", "add", "addr", "address", "số", "đường", "phố", "phường", "quận", "huyện",
    "tỉnh", "thành phố", "tp", "tx", "thị xã", "thị trấn", "xã", "ấp", "thôn", "khu phố", "kp", "lô",
    "kcn", "khu công nghiệp", "tầng", "tòa", "tòa nhà", "lầu", "ngõ", "ngách", "hẻm", "kiệt",
    "street", "st", "road", "rd", "ward", "district", "dist", "city", "province", "floor", "building",
    "tower", "lot", "no.", "hà nội", "ha noi", "hồ chí minh", "ho chi minh", "hcm", "đà nẵng", "da nang",
    "việt nam", "vietnam", "viet nam", "q.", "p.",
]

IGNORE_KW = ["mst", "mã số thuế", "tax code", "tax id", "stk", "số tài khoản", "account", "a/c"]

# Nhãn chi nhánh đứng riêng đầu khối địa chỉ: "HCM:", "HN:", "Head office:"...
BRANCH_LABEL_RE = re.compile(
    r"^(hcm|hn|hà nội|ha noi|đn|dn|đà nẵng|hp|hải phòng|ct|cần thơ|head office|branch|office|factory"
    r"|headquarters?|headquater|hq|văn phòng|vp|trụ sở|chi nhánh|cn|nhà máy|showroom|xưởng)\s*[:.\-]?$",
    re.I,
)
BRANCH_PREFIX_RE = re.compile(BRANCH_LABEL_RE.pattern.rstrip("$").replace(r"\s*[:.\-]?", r"\s*:"), re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
WEB_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\."
    r"(?:com\.vn|net\.vn|org\.vn|edu\.vn|gov\.vn|vn|com|net|org|info|biz|io|co|asia)\b(?:/\S*)?",
    re.I,
)
# Khẩu hiệu ("Your trustworthy partner", "Uy tín - Chất lượng") dễ bị nhầm là chức vụ.
SLOGAN_RE = re.compile(r"\b(your|our|we|trust|trustworthy|quality|uy tín|chất lượng|hàng đầu|by heart|since)\b", re.I)
# Nhãn đứng một mình, số nằm ở dòng sau (dấu ":" bị đọc sót).
PHONE_LABEL_RE = re.compile(
    r"^(đt|dt|tel|fax|đt\s*/\s*fax|dt\s*/\s*fax|tel\s*/\s*fax|mst|hp|h/p|mobile|mob|di động|dđ|điện thoại|phone|hotline)\W*$",
    re.I,
)
PHONE_RE = re.compile(r"\+?\(?\d[\d\s.\-()]{7,}\d")
FIELDS = ["name", "title", "company", "mobile", "phone", "fax", "email", "website", "address", "note"]


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip()


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def _kw_pattern(keywords: list[str]) -> re.Pattern:
    alts = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    # Từ khóa phải đứng riêng, không nằm giữa một từ khác (hỗ trợ chữ có dấu).
    return re.compile(r"(?<![^\W\d_])(?:" + alts + r")(?![^\W\d_])", re.I)


COMPANY_P, TITLE_P, ADDRESS_P, IGNORE_P = (_kw_pattern(k) for k in (COMPANY_KW, TITLE_KW, ADDRESS_KW, IGNORE_KW))


def has_kw(text: str, pattern: re.Pattern) -> bool:
    return bool(pattern.search(normalize(text).lower()))


def digits_of(s: str) -> str:
    return re.sub(r"\D", "", s)


def format_phone(raw: str) -> str:
    d = digits_of(raw)
    plus = raw.strip().startswith("+") or d.startswith("84")
    if d.startswith("84") and len(d) in (11, 12):
        d = "0" + d[2:]
    if plus and not d.startswith("0") and not d.startswith("84"):
        return "+" + d
    if len(d) == 10:  # di động: 0903 123 456
        return f"{d[:4]} {d[4:7]} {d[7:]}"
    if len(d) == 11:  # máy bàn: 028 3823 4567
        return f"{d[:3]} {d[3:7]} {d[7:]}"
    return d


def is_mobile(raw: str) -> bool:
    d = digits_of(raw)
    if d.startswith("84"):
        d = "0" + d[2:]
    return len(d) == 10 and bool(re.match(r"0[35789]", d))


def fix_email_spacing(s: str) -> str:
    s = re.sub(r"\s*@\s*", "@", s)
    return re.sub(r"(@\S*?)\s*\.\s*", r"\1.", s)


def strip_icon(s: str) -> str:
    """Bỏ ký tự rác do biểu tượng (điện thoại, phong bì, ghim bản đồ) bị đọc thành chữ."""
    return re.sub(r"^[^\w(+]+", "", s).strip()


def title_case(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in s.lower().split(" "))


def strip_label(text: str) -> str:
    return re.sub(
        r"^(địa chỉ|đ/c|add(ress)?|addr|a)\s*[:.\-]\s*",
        "", normalize(text), flags=re.I,
    ).strip()


NAME_PREFIX_RE = re.compile(r"^(mr|mrs|ms|miss|dr|ông|bà|anh|chị)\.?\s+", re.I)


def looks_like_name(text: str) -> bool:
    t = NAME_PREFIX_RE.sub("", normalize(text))
    if re.search(r"[\d@:/|]", t):
        return False
    words = t.split()
    if not 2 <= len(words) <= 5:
        return False
    return all(re.fullmatch(r"[^\W\d_][^\W\d_'’-]*\.?", w) and w[0].isupper() for w in words)


def _domain_stem(email: str, website: str) -> str:
    host = (email.split("@", 1)[1] if "@" in email else "") or re.sub(r"^(https?://)?(www\.)?", "", website)
    host = host.split("/")[0].lower()
    if not host:
        return ""
    stem = host.split(".")[0]
    generic = {"gmail", "yahoo", "hotmail", "outlook", "icloud", "live", "msn", "ymail", "fpt", "vnn"}
    return "" if stem in generic else stem


def raw_text(l) -> str:
    return normalize(l if isinstance(l, str) else l.get("text", ""))


def parse_card(lines_in: list) -> dict:
    """lines_in: danh sách chuỗi, hoặc dict {text, height}. Trả về dict các trường."""
    lines = []
    for i, l in enumerate(lines_in or []):
        text = l if isinstance(l, str) else l.get("text", "")
        height = 0 if isinstance(l, str) else l.get("height", 0) or 0
        text = strip_icon(normalize(text))
        if not text:
            continue
        # Nhãn và giá trị bị tách thành 2 đoạn ("MST" | ": 0312 522 851"): ghép lại.
        prev = lines[-1]["text"] if lines else ""
        colon_value = re.match(r"^\s*:", raw_text(l)) and not re.search(r"\d", prev) \
            and len(prev.split()) <= 3 and not prev.endswith(":")
        number_after_label = PHONE_LABEL_RE.match(prev) and re.match(r"^[+(\d]", text)
        if lines and (colon_value or number_after_label):
            lines[-1]["text"] += ": " + text
            continue
        lines.append({"text": text, "height": height, "index": i})

    r = {f: "" for f in FIELDS}
    r["address2"] = ""
    used: set[int] = set()

    # 1. Website: ưu tiên dòng có "www"/"http" (dòng email cũng có tên miền, dễ bị lấy nhầm).
    web_lines = sorted(lines, key=lambda l: not re.search(r"www|http", l["text"], re.I))
    for l in web_lines:
        if EMAIL_RE.search(fix_email_spacing(l["text"])):
            continue
        web = WEB_RE.search(l["text"])
        if web and "@" not in web.group(0):
            r["website"] = re.sub(r"[.,;]+$", "", web.group(0)).lower()
            used.add(l["index"])
            break

    # 2. Email
    for l in lines:
        em = EMAIL_RE.search(fix_email_spacing(l["text"]))
        if em:
            r["email"] = em.group(0).lower()
            used.add(l["index"])
            break
    if not r["email"]:
        # VietOCR hay đọc "@" thành D/O/Q/o: "quang.nguyen Dviteccons.vn" -> dựa vào tên miền website.
        domain = re.sub(r"^(https?://)?(www\.)?", "", r["website"]).split("/")[0]
        if domain:
            pat = re.compile(r"([A-Za-z0-9._%+-]+?)\s*[^\s.]?" + re.escape(domain) + r"\b", re.I)
            for l in lines:
                text = re.sub(r"\.{2,}", ".", re.sub(r"^(e-?mail|email|e)\s*[:.]\s*", "", l["text"], flags=re.I))
                m = pat.search(text)
                if m and re.search(r"[A-Za-z]", m.group(1)) and not re.match(r"(www|https?)$", m.group(1), re.I) \
                        and not text.lower().startswith("www"):
                    r["email"] = (m.group(1).rstrip(".") + "@" + domain).lower()
                    used.add(l["index"])
                    break

    # 3. Điện thoại, di động, fax
    extra: list[str] = []
    for l in lines:
        if has_kw(l["text"], IGNORE_P):
            used.add(l["index"])
            continue
        lt = l["text"].lower()
        matches = []
        for m in PHONE_RE.findall(l["text"]):
            if len(digits_of(m)) > 13:  # hai số viết liền nhau: tách ra
                matches += re.split(r"\s*[–/|;]\s*|\s-\s", m)
            else:
                matches.append(m)
        found = False
        for m in matches:
            d = digits_of(m)
            if not 9 <= len(d) <= 13:
                continue
            found = True
            formatted = format_phone(m)
            idx = l["text"].find(m)
            label = lt[max(0, idx - 14):max(0, idx)]
            if re.search(r"(tel|đt|dt|điện thoại|phone)\s*/\s*fax", label):  # "ĐT/Fax": cùng một số
                r["phone"] = r["phone"] or formatted
                r["fax"] = r["fax"] or formatted
            elif re.search(r"fax|\bf\s*[:.]", label) or ("fax" in lt and not re.search(r"tel|điện thoại|mobile|hp|dđ", lt)):
                if not r["fax"]:
                    r["fax"] = formatted
                else:
                    extra.append(formatted)
            elif re.search(r"mobile|mob|cell|hp|h/p|dđ|di động|hotline|\bm\s*[:.]", label) or is_mobile(m):
                if not r["mobile"]:
                    r["mobile"] = formatted
                else:
                    extra.append(formatted)
            elif not r["phone"]:
                r["phone"] = formatted
            else:
                extra.append(formatted)
        if found:
            used.add(l["index"])
    if not r["phone"] and extra:
        r["phone"] = extra.pop(0)
    notes = []
    if extra:
        notes.append("SĐT khác: " + ", ".join(extra))

    # 4. Công ty
    company_lines = [l for l in lines if l["index"] not in used and has_kw(l["text"], COMPANY_P)]
    if company_lines:
        strong = re.compile(r"công ty|company|cty|tập đoàn|group|ngân hàng|bank", re.I)
        company_lines.sort(key=lambda l: (-bool(strong.search(l["text"])), -len(l["text"])))
        r["company"] = company_lines[0]["text"]
        used.update(l["index"] for l in company_lines)  # tên công ty tiếng Anh/viết tắt ở dòng khác
    else:
        # Không có chữ "công ty": thử khớp tên miền email/website với một dòng (thường là logo).
        stem = _domain_stem(r["email"], r["website"])
        if stem:
            for l in lines:
                if l["index"] in used:
                    continue
                compact = re.sub(r"[^a-z0-9]", "", strip_accents(l["text"]).lower())
                if compact and (compact == stem or (compact.startswith(stem) and len(compact) <= len(stem) + 6)):
                    r["company"] = l["text"]
                    used.add(l["index"])
                    break
            if not r["company"]:
                r["company"] = stem.upper()

    # 5. Địa chỉ: gom các dòng liền nhau thành khối; khối thứ hai là địa chỉ chi nhánh.
    def is_addr(l):
        t = l["text"]
        if not has_kw(t, ADDRESS_P):
            return False
        # Dòng cuối kiểu "Vietnam." vẫn thuộc địa chỉ nếu nối tiếp ngay dòng địa chỉ trước.
        continues = bool(blocks) and blocks[-1][-1]["index"] == l["index"] - 1
        return continues or bool(re.search(r"\d", t)) or "," in t or bool(re.match(r"(địa chỉ|add|address|đ/c)", t, re.I))

    blocks: list[list[dict]] = []
    pending_label = None
    for l in lines:
        if l["index"] in used:
            continue
        if BRANCH_LABEL_RE.match(l["text"]):
            pending_label = l
            continue
        if is_addr(l):
            starts_new = (
                not blocks
                or pending_label is not None
                or l["index"] - blocks[-1][-1]["index"] > 2
                or bool(BRANCH_PREFIX_RE.match(l["text"]))  # "HN: ...", "Trụ sở: ..."
            )
            if starts_new:
                blocks.append([pending_label] if pending_label else [])
            blocks[-1].append(l)
            pending_label = None
    for i, block in enumerate(blocks[:2]):
        parts = [strip_label(x["text"]) for x in block]
        if BRANCH_LABEL_RE.match(parts[0] or "") and len(parts) > 1:
            parts = [parts[0].rstrip(":.- ") + ": " + parts[1]] + parts[2:]
        text = re.sub(r",\s*,", ",", ", ".join(p.rstrip(",") for p in parts if p))
        r["address" if i == 0 else "address2"] = text
        for x in block:
            used.add(x["index"])

    # 6. Chức vụ (có thể 2 dòng: tiếng Việt + tiếng Anh)
    title_lines = [
        l for l in lines
        if l["index"] not in used and has_kw(l["text"], TITLE_P) and not SLOGAN_RE.search(l["text"])
        and not re.search(r"\d", l["text"]) and len(l["text"].split()) <= 10
    ]
    title_line = title_lines[0] if title_lines else None
    if title_line:
        picked = [title_line] + [l for l in title_lines[1:2] if l["index"] - title_line["index"] <= 2]
        r["title"] = " / ".join(l["text"] for l in picked)
        used.update(l["index"] for l in picked)

    # 7. Họ tên: chọn dòng giống tên người nhất
    max_h = max([1] + [l["height"] for l in lines])
    best, best_score = None, float("-inf")
    for l in lines:
        if l["index"] in used or not looks_like_name(l["text"]):
            continue
        words = NAME_PREFIX_RE.sub("", l["text"]).split()
        score = 0.0
        if words[0].lower() in SURNAMES:
            score += 3
        if l["height"]:
            score += 2 * l["height"] / max_h
        if title_line and abs(l["index"] - title_line["index"]) == 1:
            score += 2
        if 2 <= len(words) <= 4:
            score += 1
        if has_kw(l["text"], ADDRESS_P):
            score -= 2
        if score > best_score:
            best, best_score = l, score
    if best:
        name = NAME_PREFIX_RE.sub("", best["text"])
        r["name"] = title_case(name) if name == name.upper() else name
        used.add(best["index"])

    r["note"] = "; ".join(notes)
    return r
