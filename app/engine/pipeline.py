"""Quy trình cho một ảnh: cắt thẻ → xoay → đọc chữ → đọc QR → tách trường → phân loại."""

import cv2
import numpy as np
from PIL import Image, ImageOps

from .classify import classify
from .crop import extract_cards
from .ocr import OCREngine
from .parser import format_phone, parse_card
from .qr import decode_qr, parse_qr

FIELDS = ["name", "title", "company", "mobile", "phone", "fax", "email", "website", "address", "address2", "note"]


def load_image(data: bytes) -> np.ndarray:
    """Đọc ảnh (xoay theo EXIF của điện thoại) thành mảng BGR."""
    import io

    pil = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def fields_from_text(lines: list, qr_text: str, categories: list[dict]) -> dict:
    """Tách trường + đọc QR + phân loại từ các dòng chữ (dùng cả khi phân tích lại thẻ đã lưu)."""
    fields = parse_card(lines)
    for k, v in parse_qr(qr_text).items():  # QR chỉ bổ sung ô còn trống
        if k in fields and not fields[k]:
            fields[k] = format_phone(v) if k in ("mobile", "phone", "fax") else v
    raw = "\n".join(l if isinstance(l, str) else l["text"] for l in lines)
    review = []
    if not fields["name"]:
        review.append("thiếu họ tên")
    if not (fields["mobile"] or fields["phone"] or fields["email"]):
        review.append("thiếu SĐT/email")
    return {**fields, "category": classify(fields, raw, categories), "raw_text": raw, "qr_text": qr_text,
            "review": ", ".join(review)}


def analyze_card(engine: OCREngine, card_img: np.ndarray, lines: list[dict], categories: list[dict]) -> dict:
    info = fields_from_text(lines, decode_qr(card_img), categories)
    confs = [l["confidence"] for l in lines if l.get("confidence") is not None]
    conf = float(np.mean(confs)) if confs else 0.0
    if engine.recognizer == "vietocr" and conf < 0.75:
        info["review"] = ", ".join(x for x in (info["review"], "chữ khó đọc") if x)
    info["confidence"] = round(conf, 3)
    return info


def process_image(engine: OCREngine, data: bytes, categories: list[dict]) -> list[dict]:
    """Trả về danh sách thẻ tìm được, mỗi thẻ gồm các trường + ảnh thẻ đã cắt (BGR)."""
    bgr = load_image(data)
    out = []
    for found in extract_cards(engine, bgr):
        info = analyze_card(engine, found["image"], found["lines"], categories)
        info["image"] = found["image"]
        info["crop_method"] = found["method"]
        out.append(info)
    return out
