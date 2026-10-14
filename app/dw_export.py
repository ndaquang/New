"""Xuất dữ liệu danh thiếp ở dạng chuẩn để kiểm tra và nạp vào kho dữ liệu (data warehouse).

Mỗi lần xuất tạo một thư mục gồm:
  cards.csv          UTF-8, phân cách bằng dấu phẩy, dòng đầu là tên cột (snake_case)
  cards.jsonl        mỗi dòng một bản ghi JSON (dễ nạp vào BigQuery / Snowflake / Postgres...)
  schema.json        tên cột, kiểu dữ liệu, mô tả
  create_table.sql   câu lệnh tạo bảng (SQL chuẩn)
  README.md          hướng dẫn
"""

import csv
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from .engine.parser import canonical_phone

SCHEMA = [
    ("card_id", "STRING", "Mã danh thiếp (duy nhất, không đổi) - dùng làm khóa chính khi nạp/cập nhật"),
    ("status", "STRING", "confirmed = đã kiểm tra và xác nhận; pending = chưa xác nhận"),
    ("confirmed_at", "TIMESTAMP", "Thời điểm xác nhận (UTC, ISO 8601)"),
    ("created_at", "TIMESTAMP", "Thời điểm quét (UTC)"),
    ("updated_at", "TIMESTAMP", "Thời điểm sửa gần nhất (UTC)"),
    ("full_name", "STRING", "Họ tên đầy đủ"),
    ("family_name", "STRING", "Họ (từ đầu tiên của họ tên kiểu Việt Nam)"),
    ("given_name", "STRING", "Tên đệm + tên"),
    ("job_title", "STRING", "Chức vụ"),
    ("company", "STRING", "Công ty"),
    ("category", "STRING", "Nhóm phân loại"),
    ("mobile", "STRING", "Di động (như hiển thị)"),
    ("mobile_e164", "STRING", "Di động dạng quốc tế E.164, ví dụ +84912345678"),
    ("phone", "STRING", "Điện thoại bàn (như hiển thị)"),
    ("phone_e164", "STRING", "Điện thoại bàn dạng E.164"),
    ("fax", "STRING", "Fax (như hiển thị)"),
    ("fax_e164", "STRING", "Fax dạng E.164"),
    ("email", "STRING", "Email (chữ thường)"),
    ("email_domain", "STRING", "Tên miền email"),
    ("website", "STRING", "Website"),
    ("website_domain", "STRING", "Tên miền website (bỏ http, www)"),
    ("address", "STRING", "Địa chỉ chính"),
    ("address2", "STRING", "Địa chỉ chi nhánh / thứ hai"),
    ("note", "STRING", "Ghi chú"),
    ("review_flags", "STRING", "Cảnh báo tự động lúc quét (thiếu họ tên, chữ khó đọc, có thể trùng...)"),
    ("source_file", "STRING", "Tên file ảnh gốc"),
    ("batch_id", "STRING", "Mã lượt quét"),
    ("ocr_confidence", "FLOAT", "Độ tin cậy trung bình của bộ đọc chữ (0-1)"),
    ("image_file", "STRING", "Tên file ảnh thẻ đã cắt (trong thư mục anh-the, hoặc images/ nếu xuất kèm ảnh)"),
    ("raw_text", "STRING", "Toàn bộ chữ máy đọc được (các dòng cách nhau bằng xuống dòng)"),
    ("exported_at", "TIMESTAMP", "Thời điểm xuất file này (UTC)"),
]
SQL_TYPES = {"STRING": "VARCHAR(2000)", "TIMESTAMP": "TIMESTAMP", "FLOAT": "DOUBLE PRECISION"}


def _iso(ts) -> str | None:
    if not ts:
        return None  # để trống (NULL) thay vì chuỗi rỗng: kho dữ liệu không nhận "" cho cột thời gian
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def e164(raw: str) -> str:
    d = canonical_phone(raw or "")
    if d.startswith("+"):
        return d
    if d.startswith("0") and len(d) in (10, 11):
        return "+84" + d[1:]
    return ""


def _domain(s: str) -> str:
    s = (s or "").lower().strip()
    if "@" in s:
        s = s.split("@", 1)[1]
    return re.sub(r"^(https?://)?(www\.)?", "", s).split("/")[0]


def to_record(c: dict, exported_at: str) -> dict:
    words = (c.get("name") or "").split()
    return {
        "card_id": c["id"],
        "status": "confirmed" if c.get("status") == "confirmed" else "pending",
        "confirmed_at": _iso(c.get("confirmed_at")),
        "created_at": _iso(c.get("created_at")),
        "updated_at": _iso(c.get("updated_at")),
        "full_name": c.get("name") or "",
        "family_name": words[0] if len(words) > 1 else "",
        "given_name": " ".join(words[1:]) if len(words) > 1 else " ".join(words),
        "job_title": c.get("title") or "",
        "company": c.get("company") or "",
        "category": c.get("category") or "",
        "mobile": c.get("mobile") or "",
        "mobile_e164": e164(c.get("mobile")),
        "phone": c.get("phone") or "",
        "phone_e164": e164(c.get("phone")),
        "fax": c.get("fax") or "",
        "fax_e164": e164(c.get("fax")),
        "email": (c.get("email") or "").lower(),
        "email_domain": _domain(c.get("email")) if c.get("email") else "",
        "website": c.get("website") or "",
        "website_domain": _domain(c.get("website")),
        "address": c.get("address") or "",
        "address2": c.get("address2") or "",
        "note": c.get("note") or "",
        "review_flags": c.get("review") or "",
        "source_file": c.get("source_file") or "",
        "batch_id": c.get("batch") or "",
        "ocr_confidence": round(float(c.get("confidence") or 0), 3),
        "image_file": c.get("image") or "",
        "raw_text": c.get("raw_text") or "",
        "exported_at": exported_at,
    }


def export_dw(cards: list[dict], images_dir: Path, out_dir: Path, include_images: bool = False,
              note: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    exported_at = _iso(time.time())
    records = [to_record(c, exported_at) for c in cards]
    cols = [n for n, _, _ in SCHEMA]

    with open(out_dir / "cards.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(records)
    with open(out_dir / "cards.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "schema.json").write_text(json.dumps(
        {"table": "business_cards", "primary_key": "card_id",
         "columns": [{"name": n, "type": t, "description": d} for n, t, d in SCHEMA]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    ddl = ",\n".join(f"  {n} {SQL_TYPES[t]}{' NOT NULL' if n == 'card_id' else ''}" for n, t, _ in SCHEMA)
    (out_dir / "create_table.sql").write_text(
        f"-- Bảng danh thiếp. Nạp lại nhiều lần: dùng MERGE/UPSERT theo card_id.\n"
        f"CREATE TABLE IF NOT EXISTS business_cards (\n{ddl},\n  PRIMARY KEY (card_id)\n);\n", encoding="utf-8")
    if include_images:
        img_out = out_dir / "images"
        img_out.mkdir(exist_ok=True)
        for c in cards:
            src = images_dir / (c.get("image") or "")
            if src.is_file():
                shutil.copy2(src, img_out / src.name)
    (out_dir / "README.md").write_text(f"""# Dữ liệu danh thiếp - xuất lúc {exported_at}

{note}

Số bản ghi: {len(records)}

| File | Nội dung |
|---|---|
| cards.csv | Dữ liệu dạng bảng, UTF-8, mọi ô đặt trong dấu ngoặc kép. Mở bằng Excel: Data → From Text/CSV → chọn UTF-8. |
| cards.jsonl | Mỗi dòng 1 bản ghi JSON (nạp thẳng vào BigQuery, Snowflake, Postgres...). |
| schema.json | Tên cột, kiểu dữ liệu, mô tả. |
| create_table.sql | Câu lệnh tạo bảng `business_cards`. |

Nạp nhiều lần (bản xuất "chỉ phần thay đổi"): dùng MERGE/UPSERT theo khóa `card_id`,
cột `updated_at` cho biết bản nào mới hơn. Thẻ có `status = confirmed` là dữ liệu đã được kiểm tra.

Ví dụ nạp vào BigQuery:
    bq load --source_format=NEWLINE_DELIMITED_JSON dataset.business_cards cards.jsonl schema_bq.json

Ví dụ nạp vào PostgreSQL:
    \\copy business_cards FROM 'cards.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
""", encoding="utf-8")
    (out_dir / "schema_bq.json").write_text(json.dumps(
        [{"name": n, "type": t, "mode": "REQUIRED" if n == "card_id" else "NULLABLE", "description": d} for n, t, d in SCHEMA],
        ensure_ascii=False, indent=2), encoding="utf-8")
    return out_dir
