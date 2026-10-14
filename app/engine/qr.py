"""Đọc mã QR trên danh thiếp (thường chứa vCard hoặc đường link website)."""

import re

import cv2
import numpy as np


def decode_qr(bgr: np.ndarray) -> str:
    try:
        det = cv2.QRCodeDetector()
        for img in (bgr, cv2.resize(bgr, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)):
            text, points, _ = det.detectAndDecode(img)
            if text:
                return text.strip()
    except cv2.error:
        pass
    return ""


def _unescape(v: str) -> str:
    return v.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";").strip()


def parse_qr(text: str) -> dict:
    """Chuyển nội dung QR (vCard / MECARD / URL) thành các trường danh thiếp."""
    out: dict[str, str] = {}
    if not text:
        return out
    if "BEGIN:VCARD" in text.upper():
        # Gộp các dòng bị gập (dòng tiếp theo bắt đầu bằng khoảng trắng).
        for line in re.sub(r"\r?\n[ \t]", "", text).splitlines():
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            k = key.split(";")[0].upper()
            params = key.upper()
            val = _unescape(val)
            if not val:
                continue
            if k == "FN":
                out.setdefault("name", val)
            elif k == "N" and "name" not in out:
                parts = [p for p in val.split(";") if p]
                out["name"] = " ".join(parts)
            elif k == "ORG":
                out.setdefault("company", val.replace(";", " ").strip())
            elif k == "TITLE":
                out.setdefault("title", val)
            elif k == "EMAIL":
                out.setdefault("email", val.lower())
            elif k == "URL":
                out.setdefault("website", val)
            elif k == "ADR":
                out.setdefault("address", ", ".join(p for p in val.split(";") if p.strip()))
            elif k == "TEL":
                if "FAX" in params:
                    out.setdefault("fax", val)
                elif "CELL" in params or "MOBILE" in params:
                    out.setdefault("mobile", val)
                else:
                    out.setdefault("phone", val)
    elif text.upper().startswith("MECARD:"):
        for part in re.split(r"(?<!\\);", text[7:]):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            v = _unescape(v)
            key = {"N": "name", "ORG": "company", "TEL": "phone", "EMAIL": "email", "URL": "website", "ADR": "address"}.get(k.upper())
            if key and v:
                if key == "name" and "," in v:
                    v = " ".join(reversed([x.strip() for x in v.split(",")]))
                out.setdefault(key, v)
    elif re.match(r"^(https?://|www\.)", text, re.I):
        out["website"] = text
    return out
