"""Lưu danh thiếp trong SQLite + ảnh thẻ đã cắt, nằm trong thư mục Documents/DanhThiep."""

import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import cv2

COLUMNS = [
    "name", "title", "company", "mobile", "phone", "fax", "email", "website", "address", "address2",
    "note", "category", "raw_text", "qr_text", "confidence", "review", "source_file", "crop_method", "batch",
    "auto_fields",  # kết quả máy tự tách lúc quét (JSON), để so với bản bạn đã sửa
]
EDITABLE = {"name", "title", "company", "mobile", "phone", "fax", "email", "website", "address", "address2", "note", "category", "review"}


def default_data_dir() -> Path:
    env = os.environ.get("DANHTHIEP_DATA")
    if env:
        return Path(env)
    docs = Path.home() / "Documents"
    return (docs if docs.exists() else Path.home()) / "DanhThiep"


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.cards_dir = self.dir / "anh-the"
        self.exports_dir = self.dir / "xuat-file"
        for d in (self.dir, self.cards_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.dir / "danhthiep.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        cols = ", ".join(f"{c} {'REAL' if c == 'confidence' else 'TEXT'} DEFAULT ''" for c in COLUMNS)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, created_at REAL, updated_at REAL, image TEXT, {cols})")
        # Thêm cột mới nếu file dữ liệu tạo từ phiên bản cũ hơn.
        have = {r[1] for r in self.db.execute("PRAGMA table_info(cards)")}
        for c in COLUMNS:
            if c not in have:
                self.db.execute(f"ALTER TABLE cards ADD COLUMN {c} {'REAL' if c == 'confidence' else 'TEXT'} DEFAULT ''")
        self.db.commit()

    def image_path(self, card_id: str) -> Path:
        return self.cards_dir / f"{card_id}.jpg"

    def save_image(self, card_id: str, bgr) -> None:
        cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tofile(str(self.image_path(card_id)))

    def add(self, info: dict) -> dict:
        card_id = uuid.uuid4().hex[:12]
        now = time.time()
        if info.get("image") is not None:
            self.save_image(card_id, info["image"])
        row = {c: info.get(c, "") for c in COLUMNS}
        row["confidence"] = float(info.get("confidence") or 0)
        with self.lock:
            self.db.execute(
                f"INSERT INTO cards (id, created_at, updated_at, image, {', '.join(COLUMNS)}) VALUES (?, ?, ?, ?, {', '.join('?' * len(COLUMNS))})",
                [card_id, now, now, f"{card_id}.jpg", *[row[c] for c in COLUMNS]],
            )
            self.db.commit()
        return self.get(card_id)

    def get(self, card_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return dict(r) if r else None

    def all(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM cards ORDER BY created_at DESC, rowid DESC")]

    def update(self, card_id: str, fields: dict) -> dict | None:
        fields = {k: ("" if v is None else str(v)) for k, v in fields.items() if k in EDITABLE}
        if fields:
            with self.lock:
                sets = ", ".join(f"{k} = ?" for k in fields)
                self.db.execute(f"UPDATE cards SET {sets}, updated_at = ? WHERE id = ?", [*fields.values(), time.time(), card_id])
                self.db.commit()
        return self.get(card_id)

    def replace_analysis(self, card_id: str, info: dict) -> dict | None:
        fields = {c: info.get(c, "") for c in COLUMNS if c in info and c not in ("source_file", "batch")}
        if fields:
            with self.lock:
                sets = ", ".join(f"{k} = ?" for k in fields)
                self.db.execute(f"UPDATE cards SET {sets}, updated_at = ? WHERE id = ?", [*fields.values(), time.time(), card_id])
                self.db.commit()
        return self.get(card_id)

    def set_fields_silently(self, card_id: str, fields: dict) -> None:
        """Ghi kết quả phân tích lại mà không đổi updated_at (để vẫn phân biệt được ô bạn đã sửa tay)."""
        fields = {k: v for k, v in fields.items() if k in COLUMNS}
        if fields:
            with self.lock:
                sets = ", ".join(f"{k} = ?" for k in fields)
                self.db.execute(f"UPDATE cards SET {sets} WHERE id = ?", [*fields.values(), card_id])
                self.db.commit()

    def delete(self, card_ids: list[str]) -> None:
        with self.lock:
            self.db.executemany("DELETE FROM cards WHERE id = ?", [(i,) for i in card_ids])
            self.db.commit()
        for i in card_ids:
            self.image_path(i).unlink(missing_ok=True)

    def find_duplicate(self, info: dict, exclude: str = "") -> str:
        """Tìm thẻ đã có trùng email hoặc số di động (so theo chữ số)."""
        email = (info.get("email") or "").lower()
        mobile = "".join(ch for ch in (info.get("mobile") or "") if ch.isdigit())
        name = _fold(info.get("name"))
        company = _fold(info.get("company"))
        for r in self.db.execute("SELECT id, email, mobile, name, company FROM cards WHERE id != ?", (exclude,)):
            if email and r["email"].lower() == email:
                return r["name"] or r["id"]
            if mobile and "".join(ch for ch in r["mobile"] if ch.isdigit()) == mobile:
                return r["name"] or r["id"]
            if name and len(name) >= 6 and _fold(r["name"]) == name and (not company or _fold(r["company"]) == company):
                return r["name"] or r["id"]
        return ""


def _fold(s) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]", "", s.lower())
