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
    "status",  # "" = chưa xác nhận, "confirmed" = bạn đã kiểm tra và xác nhận
    "confirmed_at",
]
REAL_COLUMNS = {"confidence", "confirmed_at"}
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
        cols = ", ".join(f"{c} {'REAL' if c in REAL_COLUMNS else 'TEXT'} DEFAULT ''" for c in COLUMNS)
        self.db.execute(f"CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, created_at REAL, updated_at REAL, image TEXT, {cols})")
        # Thêm cột mới nếu file dữ liệu tạo từ phiên bản cũ hơn.
        have = {r[1] for r in self.db.execute("PRAGMA table_info(cards)")}
        for c in COLUMNS:
            if c not in have:
                self.db.execute(f"ALTER TABLE cards ADD COLUMN {c} {'REAL' if c in REAL_COLUMNS else 'TEXT'} DEFAULT ''")
        # Ảnh gốc đã xử lý (để chạy lại thì bỏ qua) và các mốc thời gian (lần xuất kho dữ liệu gần nhất...)
        self.db.execute("CREATE TABLE IF NOT EXISTS files (fingerprint TEXT PRIMARY KEY, name TEXT, status TEXT,"
                        " cards INTEGER, message TEXT, processed_at REAL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self.db.commit()
        self.thumbs_dir = self.cards_dir / "nho"
        self.thumbs_dir.mkdir(exist_ok=True)

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
        for c in REAL_COLUMNS:
            row[c] = float(info.get(c) or 0)
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

    def thumb_path(self, card_id: str) -> Path:
        """Ảnh nhỏ cho bảng danh sách (ảnh thẻ gốc có thể tới 1800px, tải hàng trăm ảnh lớn làm treo app)."""
        src, dst = self.image_path(card_id), self.thumbs_dir / f"{card_id}.jpg"
        if src.exists() and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime):
            import numpy as np

            img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                s = 320 / max(h, w)
                if s < 1:
                    img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
                cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tofile(str(dst))
        return dst

    def confirm(self, card_ids: list[str], confirmed: bool) -> None:
        now = time.time()
        with self.lock:
            self.db.executemany(
                "UPDATE cards SET status = ?, confirmed_at = ?, updated_at = ? WHERE id = ?",
                [("confirmed" if confirmed else "", now if confirmed else 0, now, i) for i in card_ids],
            )
            self.db.commit()

    # ----- ảnh gốc đã xử lý -----
    def record_file(self, fingerprint: str, name: str, status: str, cards: int = 0, message: str = "") -> None:
        if not fingerprint:
            return
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?, ?)",
                            (fingerprint, name, status, cards, message, time.time()))
            self.db.commit()

    def done_files(self, fingerprints: list[str]) -> list[str]:
        if not fingerprints:
            return []
        out = []
        for i in range(0, len(fingerprints), 500):
            chunk = fingerprints[i:i + 500]
            q = f"SELECT fingerprint FROM files WHERE status = 'ok' AND fingerprint IN ({','.join('?' * len(chunk))})"
            out += [r[0] for r in self.db.execute(q, chunk)]
        return out

    def forget_files(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM files")
            self.db.commit()

    def get_meta(self, key: str, default: str = "") -> str:
        r = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    def set_meta(self, key: str, value: str) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
            self.db.commit()

    # ----- thẻ trùng -----
    def duplicate_groups(self) -> list[list[dict]]:
        """Nhóm các thẻ trùng nhau: cùng email, cùng số di động, hoặc cùng họ tên + công ty."""
        from .engine.parser import canonical_phone

        cards = self.all()
        parent = {c["id"]: c["id"] for c in cards}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        seen: dict[str, str] = {}
        for c in cards:
            keys = []
            if c.get("email"):
                keys.append("e:" + c["email"].lower().strip())
            mob = canonical_phone(c.get("mobile") or "")
            if len(mob) >= 9:
                keys.append("m:" + mob)
            name = _fold(c.get("name"))
            if len(name) >= 6:
                keys.append("n:" + name + "|" + _fold(c.get("company"))[:12])
            for k in keys:
                if k in seen:
                    parent[find(c["id"])] = find(seen[k])
                else:
                    seen[k] = c["id"]
        groups: dict[str, list[dict]] = {}
        for c in cards:
            groups.setdefault(find(c["id"]), []).append(c)
        return [g for g in groups.values() if len(g) > 1]

    def merge_group(self, group: list[dict], fields: list[str]) -> dict:
        """Giữ 1 thẻ tốt nhất (đã xác nhận > nhiều thông tin nhất > mới nhất), điền ô trống từ các thẻ
        còn lại, rồi xóa các thẻ thừa. Trả về thẻ được giữ."""
        def quality(c):
            return (c.get("status") == "confirmed", sum(1 for f in fields if c.get(f)), c.get("created_at") or 0)

        group = sorted(group, key=quality, reverse=True)
        keep, rest = group[0], group[1:]
        fill = {}
        for f in fields:
            if not keep.get(f):
                v = next((c.get(f) for c in rest if c.get(f)), "")
                if v:
                    fill[f] = v
        review = ", ".join(x for x in (keep.get("review") or "").split(", ") if x and not x.startswith("có thể trùng"))
        fill["review"] = review
        self.update(keep["id"], fill)
        self.delete([c["id"] for c in rest])
        return self.get(keep["id"])

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
            (self.thumbs_dir / f"{i}.jpg").unlink(missing_ok=True)

    def find_duplicate(self, info: dict, exclude: str = "", return_id: bool = False) -> str:
        """Tìm thẻ đã có trùng email, số di động hoặc họ tên + công ty.

        Trả về tên thẻ trùng (hoặc id nếu return_id=True); chuỗi rỗng nếu không trùng."""
        from .engine.parser import canonical_phone

        email = (info.get("email") or "").lower().strip()
        mobile = canonical_phone(info.get("mobile") or "")
        name = _fold(info.get("name"))
        company = _fold(info.get("company"))[:12]
        for r in self.db.execute("SELECT id, email, mobile, name, company FROM cards WHERE id != ?", (exclude,)):
            hit = (email and r["email"].lower().strip() == email) \
                or (len(mobile) >= 9 and canonical_phone(r["mobile"] or "") == mobile) \
                or (len(name) >= 6 and _fold(r["name"]) == name and _fold(r["company"])[:12] == company)
            if hit:
                return r["id"] if return_id else (r["name"] or r["id"])
        return ""


def _fold(s) -> str:
    import re
    import unicodedata

    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^a-z0-9]", "", s.lower())
