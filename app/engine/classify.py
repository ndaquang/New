"""Phân loại danh thiếp theo nhóm ngành dựa trên từ khóa (sửa được trong categories.json)."""

import json
import re
from pathlib import Path

from .parser import normalize, strip_accents

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "config" / "categories.json"


def load_categories(path: Path | None = None) -> list[dict]:
    for p in (path, DEFAULT_FILE):
        if p and Path(p).exists():
            try:
                cats = json.loads(Path(p).read_text(encoding="utf-8"))["categories"]
                if cats:
                    return cats
            except (ValueError, KeyError) as exc:
                print(f"Lỗi đọc {p}: {exc}; dùng danh sách mặc định.", flush=True)
    return json.loads(DEFAULT_FILE.read_text(encoding="utf-8"))["categories"]


def sync_user_categories(user_path: Path) -> bool:
    """Cập nhật file phân loại của người dùng khi app có bộ từ khóa mới hơn.

    Giữ nguyên tên nhóm và từ khóa người dùng đã thêm; thêm từ khóa/nhóm mới; bỏ các từ khóa
    mà bản mới đánh dấu là gây phân loại sai ("removed_keywords"). Trả về True nếu có cập nhật.
    """
    default = json.loads(DEFAULT_FILE.read_text(encoding="utf-8"))
    try:
        user = json.loads(Path(user_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if user.get("version", 1) >= default.get("version", 1):
        return False
    removed = {k.lower() for k in default.get("removed_keywords", [])}
    by_name = {c["name"]: c for c in user.get("categories", [])}
    for dc in default["categories"]:
        uc = by_name.get(dc["name"])
        if uc is None:
            # nhóm mới: chèn trước nhóm mặc định cuối cùng ("Khác")
            user["categories"].insert(max(0, len(user["categories"]) - 1), dict(dc))
            continue
        have = {k.lower() for k in uc.get("keywords", [])}
        uc["keywords"] = [k for k in uc.get("keywords", []) if k.lower() not in removed]
        uc["keywords"] += [k for k in dc["keywords"] if k.lower() not in have]
    user["version"] = default["version"]
    user["_huong_dan"] = default["_huong_dan"]
    Path(user_path).write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _lower(s: str) -> str:
    return normalize(s).lower()


def _count(text: str, keywords: list[str]) -> int:
    """Đếm từ khóa xuất hiện. Từ khóa có dấu chỉ khớp chữ có dấu (tránh "cửa" khớp nhầm "của"),
    từ khóa không dấu khớp cả chữ có dấu lẫn không dấu."""
    folded = strip_accents(text)
    n = 0
    for kw in keywords:
        k = _lower(kw)
        hay = folded if k == strip_accents(k) else text
        if k and re.search(r"(?<![^\W_])" + re.escape(k) + r"(?![^\W_])", hay):
            n += 1
    return n


def classify(card: dict, raw_text: str, categories: list[dict]) -> str:
    company = _lower(card.get("company", ""))
    title = _lower(card.get("title", ""))
    domain = _lower(re.sub(r"[@.]", " ", card.get("email", "").split("@")[-1] + " " + card.get("website", "")))
    other = _lower(raw_text)
    best, best_score = categories[-1]["name"], 0.0
    for cat in categories[:-1]:
        kws = cat.get("keywords", [])
        score = 3 * _count(company, kws) + 1.5 * _count(domain, kws) + 1 * _count(title, kws) + 0.5 * _count(other, kws)
        # Tên miền dính liền ("viteccons") vẫn khớp từ khóa ngắn như "cons".
        score += sum(1.0 for kw in kws if len(kw) >= 4 and kw.isascii() and _lower(kw) in domain.replace(" ", ""))
        # Tên công ty bị OCR viết liền ("MITSUBISHIESTATE", "JLLVIETNAM"): khớp từ khóa dài bên trong.
        glued = [w for w in re.findall(r"[a-z0-9]+", strip_accents(company)) if len(w) >= 8]
        score += sum(2.0 for kw in kws if len(kw) >= 5 and kw.isascii() and " " not in kw
                     and any(_lower(kw) in w and _lower(kw) != w for w in glued))
        if score > best_score:
            best, best_score = cat["name"], score
    return best
