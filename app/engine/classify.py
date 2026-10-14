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
        if score > best_score:
            best, best_score = cat["name"], score
    return best
