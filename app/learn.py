"""Ghi nhớ những gì bạn sửa để lần sau tự áp dụng (lưu ở hoc-tu-sua.json trong thư mục dữ liệu).

- Đổi phân loại một thẻ  -> các thẻ sau cùng tên miền / cùng tên công ty dùng phân loại đó.
- Sửa tên công ty một thẻ -> các thẻ sau cùng tên miền dùng tên công ty đó.
"""

import json
import re
import threading
from pathlib import Path

from .engine.parser import normalize, strip_accents

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.com.vn", "hotmail.com", "outlook.com", "icloud.com", "live.com",
    "msn.com", "ymail.com", "fpt.vn", "vnn.vn", "hcm.vnn.vn", "hn.vnn.vn", "fpt.com.vn",
}


def card_domain(card: dict) -> str:
    email = (card.get("email") or "").lower()
    if "@" in email:
        d = email.split("@", 1)[1]
    else:
        d = re.sub(r"^(https?://)?(www\.)?", "", (card.get("website") or "").lower()).split("/")[0]
    d = d.strip(". ")
    return "" if not d or d in GENERIC_DOMAINS else d


def company_key(name: str) -> str:
    s = strip_accents(normalize(name)).lower()
    s = re.sub(r"\b(cong ty|cty|tnhh|co phan|cp|jsc|co|ltd|llc|inc|corp|corporation|company|limited)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


class Learner:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = {"category_by_domain": {}, "category_by_company": {}, "company_by_domain": {}}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except ValueError:
                pass

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def record(self, card: dict, changed: dict):
        """card: thẻ sau khi sửa; changed: các trường người dùng vừa đổi."""
        dom = card_domain(card)
        ckey = company_key(card.get("company", ""))
        with self.lock:
            if "category" in changed and changed["category"]:
                if dom:
                    self.data["category_by_domain"][dom] = changed["category"]
                if ckey:
                    self.data["category_by_company"][ckey] = changed["category"]
            if "company" in changed and changed["company"] and dom:
                self.data["company_by_domain"][dom] = changed["company"]
            self._save()

    def apply(self, info: dict) -> list[str]:
        """Áp dụng điều đã học lên thẻ mới. Trả về danh sách trường đã đổi."""
        applied = []
        dom = card_domain(info)
        if dom and dom in self.data["company_by_domain"]:
            info["company"] = self.data["company_by_domain"][dom]
            applied.append("company")
        ckey = company_key(info.get("company", ""))
        cat = self.data["category_by_domain"].get(dom) if dom else None
        cat = cat or (self.data["category_by_company"].get(ckey) if ckey else None)
        if cat:
            info["category"] = cat
            applied.append("category")
        return applied
