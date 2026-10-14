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
    "pte", "sdn", "bhd", "gmbh", "pty", "plc", "llp", "corporation", "incorporated",
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
NOT_COMPANY_RE = re.compile(r"\b(a member of|member of|thành viên của|subsidiary of|platform)\b", re.I)
# Khẩu hiệu ("Your trustworthy partner", "Uy tín - Chất lượng") dễ bị nhầm là chức vụ.
SLOGAN_RE = re.compile(r"\b(your|our|we|trust|trustworthy|quality|uy tín|chất lượng|hàng đầu|by heart|since|member of)\b", re.I)
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


# Mã quốc gia hay gặp trên danh thiếp (ngoài Việt Nam).
COUNTRY_CODES = ("852", "853", "886", "65", "86", "81", "82", "66", "60", "62", "63", "91", "61", "44", "49",
                 "48", "33", "39", "34", "31", "41", "43", "45", "46", "47", "971", "974")


def canonical_phone(raw: str) -> str:
    """Chuẩn hóa chuỗi số điện thoại đã đọc, sửa các lỗi OCR hay gặp:
    "+" bị đọc thành chữ số ("484937665059" -> 0937665059), "(+84) (0)28..." , số 0 thừa ở đầu.
    Trả về "0xxxxxxxxx" (Việt Nam), "+cc..." (nước ngoài) hoặc chuỗi số gốc nếu không chắc."""
    d = digits_of(raw)
    if re.match(r"^(1800|1900)\d{4,6}$", d):
        return d
    if d.startswith("0") and len(d) in (10, 11) and not d.startswith("00"):
        return d
    if re.match(r"^[35789]\d{8}$", d):  # di động thiếu số 0 đầu
        return "0" + d
    # "+84": cho phép tối đa 3 ký tự rác phía trước (dấu +, ngoặc, biểu tượng bị đọc thành số).
    for p in range(0, 4):
        if d[p:p + 2] != "84":
            continue
        rest = d[p + 2:]
        if rest.startswith("0"):
            rest = rest[1:]  # "+84 (0)28 ..."
        if (len(rest) == 9 and rest[0] in "35789") or (len(rest) == 10 and rest[0] == "2"):
            return "0" + rest
    stripped = d.lstrip("0")
    if len(d) - len(stripped) >= 2 and ((len(stripped) == 9 and stripped[0] in "35789") or (len(stripped) == 10 and stripped[0] == "2")):
        return "0" + stripped
    # Số nước ngoài: thử nguyên chuỗi, rồi bỏ 1 ký tự rác đầu.
    for cand in (d, d[1:]):
        if 10 <= len(cand) <= 13 and cand.startswith(COUNTRY_CODES) and not cand.startswith("0"):
            return "+" + cand
    return d


def format_phone(raw: str) -> str:
    d = canonical_phone(raw)
    if d.startswith("+"):
        return d
    if len(d) == 10 and d.startswith("0"):  # di động: 0903 123 456
        return f"{d[:4]} {d[4:7]} {d[7:]}"
    if len(d) == 11 and d.startswith("0"):  # máy bàn: 028 3823 4567
        return f"{d[:3]} {d[3:7]} {d[7:]}"
    return d


def is_mobile(raw: str) -> bool:
    d = canonical_phone(raw)
    return len(d) == 10 and bool(re.match(r"0[35789]", d))


WWW_RE = re.compile(r"(?i)(?<![a-z0-9])[0o]?w{3,4}\s*[.,·]?\s*(?=[a-z0-9-]{2,}\.[a-z]{2,})")


def fix_www(s: str) -> str:
    """OCR hay làm mất/sai dấu chấm sau www: "wwwtico-sg.vn", "WWWW.hitchins.com", "0wwwbestmix.vn"."""
    return WWW_RE.sub("www.", s)


FREE_MAIL = ("gmail.com", "yahoo.com", "yahoo.com.vn", "hotmail.com", "outlook.com", "icloud.com", "live.com")
AT_LIKE = set("@oaq0dgeOQDGơô©")  # các ký tự "@" hay bị đọc nhầm thành
DOMAIN_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9-]+)*\.(com\.vn|net\.vn|org\.vn|edu\.vn|gov\.vn|vn|com|net|org|info|biz|io|co|asia|sg|cn|jp|kr|de|pl|be|fr|es|th|my|hk|tw|au|uk)$"
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", strip_accents(text).lower()))


def word_spans(text: str) -> set[str]:
    """Các chuỗi ghép từ 1–4 từ liên tiếp trên thẻ ("NAM KIM GROUP" -> "namkim", "namkimgroup"...)."""
    ws = re.findall(r"[a-z0-9]+", strip_accents(text).lower())
    return {"".join(ws[i:j]) for i in range(len(ws)) for j in range(i + 1, min(i + 5, len(ws) + 1))}


def recover_email(token: str, known: set[str], evidence: set[str], words: set[str], labeled: bool) -> str:
    """Khôi phục email bị mất "@": "ta.nguyenobluescope.com" -> "ta.nguyen@bluescope.com".

    Thử mọi vị trí đặt "@" (thay một ký tự giống @ hoặc chèn vào), chấm điểm theo bằng chứng trên thẻ:
    tên miền trùng website/email khác, là hộp thư phổ biến (gmail...), hoặc tên miền xuất hiện ở dòng khác.
    """
    tok = re.sub(r"\.{2,}", ".", token.strip().strip(".,;:")).lower()
    if "@" in tok or tok.startswith(("www.", "http")) or not re.fullmatch(r"[a-z0-9._%+-]+\.[a-z]{2,}(\.[a-z]{2})?", tok):
        return ""
    best, best_score = "", 0.0
    for i in range(2, len(tok) - 4):
        for consumed in (1, 0):  # 1: ký tự tại i chính là "@" bị đọc sai; 0: "@" bị mất hẳn
            if consumed and tok[i] not in AT_LIKE:
                continue
            local, dom = tok[:i], tok[i + consumed:]
            if not DOMAIN_RE.match(dom) or local.endswith(".") or local.startswith(".") or len(dom.split(".")[0]) < 2:
                continue
            stem = dom.split(".")[0]
            score = 0.0
            if dom in known:
                score += 6
            if dom in FREE_MAIL:
                score += 5
            if len(stem) >= 3 and stem in evidence:
                score += 3
            if consumed:
                score += 1
            tail = re.split(r"[._-]", local)[-1]
            if len(tail) >= 4 and tail in words:
                score += 2  # phần cuối trước "@" là một từ có thật trên thẻ ("mateco")
            if score > best_score:
                best, best_score = f"{local}@{dom}", score
    return best if best_score >= (2 if labeled else 3) else ""


def fix_domain(domain: str, known: set[str], evidence: set[str]) -> str:
    """"@" bị đọc thành "@d", "@o"...: "dhilti.com" -> "hilti.com" nếu có bằng chứng trên thẻ."""
    stem = domain.split(".")[0]
    if len(stem) >= 4 and stem[0] in AT_LIKE:
        cand = domain[1:]
        if domain not in known and (cand in known or (stem[1:] in evidence and stem not in evidence)):
            return cand
    return domain


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


NAME_PREFIX_RE = re.compile(r"^(mr|mrs|ms|miss|dr|ông|bà|anh|chị|eng|ks|kts|ths|ts|pgs\.?\s*ts|arch|ar)\.?\s+", re.I)
# Từ không thể có trong họ tên người (thường là chức vụ, bộ phận, tên công ty bị đọc nhầm thành tên).
NOT_NAME_WORDS = {
    "business", "development", "solutions", "solution", "engineered", "engineering", "building", "construction",
    "chemicals", "country", "manager", "managers", "office", "firm", "design", "architectural", "concrete",
    "equipment", "assembly", "handrail", "value", "sales", "sale", "furniture", "furni", "steel", "group",
    "company", "representative", "head", "team", "department", "project", "director", "vietnam", "hcmc",
    "cambodia", "international", "trading", "store", "factory", "branch", "member", "consulting", "service",
    "services", "technology", "tech", "industrial", "systems", "partner", "holdings", "corporation", "limited",
    "ltd", "jsc", "co", "products", "product", "marketing", "technical", "support", "showroom", "hotline",
}


def clean_name(text: str) -> str:
    t = NAME_PREFIX_RE.sub("", normalize(text))
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)  # biệt danh: "Vo Dinh Quoc (Bean)"
    return t.strip()


def looks_like_name(text: str) -> bool:
    t = clean_name(text)
    if re.search(r"[\d@:/|]", t):
        return False
    words = t.split()
    if not 2 <= len(words) <= 5:
        return False
    if any(strip_accents(w).lower().strip(".") in NOT_NAME_WORDS for w in words):
        return False
    if any(w.endswith(".") for w in words):
        return False  # chữ viết tắt ("VP. TP Hồ") không phải tên người
    return all(re.fullmatch(r"[^\W\d_][^\W\d_'’-]*", w) and w[0].isupper() for w in words)


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
        text = fix_www(strip_icon(normalize(text)))
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
    def other_text(idx: int) -> str:
        return " ".join(x["text"] for x in lines if x["index"] != idx)

    def evidence_without(idx: int) -> set[str]:
        return word_spans(other_text(idx))

    web_host = re.sub(r"^(https?://)?(www\.)?", "", r["website"]).split("/")[0]
    known = {web_host} if web_host else set()
    for l in lines:
        em = EMAIL_RE.search(fix_email_spacing(l["text"]))
        if em:
            local, dom = em.group(0).lower().split("@", 1)
            if len(local) < 2 or local in ("www", "http"):
                continue
            r["email"] = local + "@" + fix_domain(dom, known, evidence_without(l["index"]))
            used.add(l["index"])
            break
    if not r["email"]:
        # VietOCR hay đọc "@" thành D/O/Q/o: "quang.nguyen Dviteccons.vn" -> dựa vào tên miền website.
        if web_host:
            pat = re.compile(r"([A-Za-z0-9._%+-]+?)\s*[^\s.]?" + re.escape(web_host) + r"\b", re.I)
            for l in lines:
                if re.search(r"www|http", l["text"], re.I):
                    continue
                text = re.sub(r"\.{2,}", ".", re.sub(r"^(e-?mail|email|e)\s*[:.]\s*", "", l["text"], flags=re.I))
                m = pat.search(text)
                if m and len(m.group(1).strip(".")) >= 2 and re.search(r"[A-Za-z]", m.group(1)):
                    r["email"] = (m.group(1).rstrip(".") + "@" + web_host).lower()
                    used.add(l["index"])
                    break
    if not r["email"] and web_host:
        # Chữ đầu tên miền cũng bị đọc sai ("quang.nguyen Quiteccons.vn"): so gần đúng.
        from difflib import SequenceMatcher

        for l in lines:
            if l["index"] in used:
                continue
            m = re.match(r"^(?:e-?mail\s*[:.]?\s*)?([A-Za-z0-9._%+-]*[A-Za-z][A-Za-z0-9._%+-]*)\s+(\S+\.[A-Za-z]{2,})$", l["text"], re.I)
            if m and SequenceMatcher(None, m.group(2).lower(), web_host.lower()).ratio() >= 0.8:
                r["email"] = (m.group(1).rstrip(".") + "@" + web_host).lower()
                used.add(l["index"])
                break
    if not r["email"]:
        # Mất "@" và không có website để đối chiếu: thử từng chỗ đặt "@" và chấm điểm theo bằng chứng trên thẻ.
        for l in lines:
            if re.search(r"www|http", l["text"], re.I):
                continue
            labeled = bool(re.match(r"^(e-?mail|email|e)\s*[:.]", l["text"], re.I))
            body = re.sub(r"^(e-?mail|email|e)\s*[:.]\s*", "", l["text"], flags=re.I)
            ev = evidence_without(l["index"])
            for tok in body.split():
                em = recover_email(tok, known, ev, _words(other_text(l["index"])), labeled)
                if em:
                    r["email"] = em
                    used.add(l["index"])
                    # Token đó đã bị lấy nhầm làm website: bỏ đi.
                    if r["website"] and r["website"] in tok.lower() and not re.search(r"www|http", r["website"]):
                        r["website"] = ""
                    break
            if r["email"]:
                break
    # Website không có "www" mà thực ra là email bị mất "@" -> đã khôi phục ở trên.
    if r["email"] and r["website"] and "@" not in r["website"]:
        host = re.sub(r"^(https?://)?(www\.)?", "", r["website"]).split("/")[0]
        if host and not re.search(r"www|http", r["website"]) and host.endswith(r["email"].split("@")[1]) \
                and host != r["email"].split("@")[1]:
            r["website"] = r["email"].split("@")[1]

    # 3. Điện thoại, di động, fax
    extra: list[str] = []
    for l in lines:
        if has_kw(l["text"], IGNORE_P):
            used.add(l["index"])
            continue
        lt = l["text"].lower()
        matches = []
        for m in PHONE_RE.findall(l["text"]):
            d = digits_of(m)
            if len(d) > 13:  # hai số viết liền nhau: tách ra
                parts = re.split(r"\s*[–/|;]\s*|\s-\s", m)
                if len(parts) == 1 and len(d) in (20, 21, 22) and d.startswith("0"):
                    # "09373822050982939733": hai số di động không có dấu phân cách
                    k = d.find("0", 10, 12) if d[10] != "0" else 10
                    parts = [d[:k], d[k:]] if k > 0 else [d]
                matches += parts
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
    def company_ok(l) -> bool:
        t = l["text"]
        if l["index"] in used or not has_kw(t, COMPANY_P):
            return False
        if re.search(r"www|http|@|linkedin|\.(com|vn|net)\b", t, re.I):
            return False  # dòng website / email / mạng xã hội có chữ "company"
        if t.startswith("(") or NOT_COMPANY_RE.search(t):
            return False  # "(An RPM Platform Company)", "A Member Of The Pan Group"
        if re.match(r"^(giám đốc|phó|trưởng|director|manager|head|deputy)\b", t, re.I):
            return False  # "Giám đốc Chi nhánh ..." là chức vụ
        if re.search(r"\d", t) and t.count(",") >= 2:
            return False  # dòng địa chỉ có chữ "Group 23", "Lot..."
        return True

    company_lines = [l for l in lines if company_ok(l)]
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
            if not r["company"] and len(stem) <= 20:
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
        and not (" / " in l["text"] and looks_like_name(l["text"].split(" / ")[0]))
        and not re.search(r"\d", l["text"]) and len(l["text"].split()) <= 10
    ]
    title_line = title_lines[0] if title_lines else None
    if title_line:
        picked = [title_line] + [l for l in title_lines[1:2] if l["index"] - title_line["index"] <= 2]
        r["title"] = " / ".join(l["text"] for l in picked)
        used.update(l["index"] for l in picked)

    # 7. Họ tên: chọn dòng giống tên người nhất
    max_h = max([1] + [l["height"] for l in lines])
    org = re.sub(r"[^a-z0-9]", "", strip_accents(r["company"] + " " + r["website"] + " " + r["email"].split("@")[-1]).lower())
    cands = []
    for l in lines:
        if l["index"] in used:
            continue
        t = l["text"]
        # "KS. HUỲNH LÊ TOÀN / Quản lý dự án": tên và chức vụ chung một dòng
        if " / " in t and looks_like_name(t.split(" / ")[0]):
            cands.append((l, t.split(" / ")[0], t.split(" / ", 1)[1]))
            continue
        words = clean_name(t).split()
        # Một chữ rác đứng trước họ ("ONEO Ngô Hoàng Hải")
        if len(words) >= 3 and words[0].lower() not in SURNAMES and strip_accents(words[1]).lower() in SURNAMES:
            t = " ".join(words[1:])
        if looks_like_name(t):
            cands.append((l, t, ""))
    best, best_score, best_title = None, float("-inf"), ""
    for l, t, extra_title in cands:
        words = clean_name(t).split()
        compact = re.sub(r"[^a-z0-9]", "", strip_accents(t).lower())
        if len(compact) >= 5 and compact in org:
            continue  # "Quang Phong" trùng tên công ty / tên miền
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
            best, best_score, best_name, best_title = l, score, t, extra_title
    if best:
        name = clean_name(best_name)
        r["name"] = title_case(name) if name == name.upper() else name
        used.add(best["index"])
        if best_title and not r["title"]:
            r["title"] = best_title

    r["note"] = "; ".join(notes)
    return r
