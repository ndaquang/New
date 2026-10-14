"""Tự kiểm tra: chạy toàn bộ quy trình trên các ảnh mẫu và in kết quả (dùng khi build trên Windows)."""

import json
import os
import time

from .engine.classify import load_categories
from .engine.ocr import OCREngine
from .engine.pipeline import process_image
from .samples import SAMPLES, encode

# (số thẻ phải tìm được, các trường bắt buộc phải đọc đúng)
EXPECT = {
    "anh_chup_ban_go.jpg": (1, [{"mobile": "0795 688 399", "email": "quang.nguyen@viteccons.vn"}]),
    "scan_hai_the.jpg": (2, None),
    "danh_thiep_dien_tu.png": (1, [{"mobile": "0918 196 121", "email": "long.vu@cesco.com.vn"}]),
    "chup_xoay_doc.jpg": (1, [{"mobile": "0795 688 399", "email": "quang.nguyen@viteccons.vn"}]),
    "the_nho_ban_go_sang.jpg": (1, [{"mobile": "0918 196 121", "email": "long.vu@cesco.com.vn"}]),
}
# Chỉ kiểm tra khi dùng VietOCR (đọc được tiếng Việt có dấu).
EXPECT_VIETOCR = {
    "anh_chup_ban_go.jpg": [{"name": "Nguyen Dang Quang"}],
    "danh_thiep_dien_tu.png": [{"name": "Vũ Anh Kim Long", "company": "Công Ty TNHH CESCO",
                                "phone": "028 3727 3079", "fax": "028 3727 3079"}],
}


def _annotate(level: str, title: str, text: str):
    """Trên GitHub Actions: ghi kết quả thành chú thích để xem nhanh mà không cần mở log."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        body = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::{level} title={title}::{body}", flush=True)


def run() -> int:
    try:
        return _run()
    except BaseException:
        import traceback

        tb = traceback.format_exc()
        print(tb, flush=True)
        _annotate("error", "selftest crash", tb[-3000:])
        return 2


def _run() -> int:
    t0 = time.time()
    engine = OCREngine()
    print(f"Bộ đọc chữ: {engine.recognizer} (nạp trong {time.time() - t0:.1f}s) {engine.load_error}", flush=True)
    cats = load_categories()
    failures = []
    for name, make in SAMPLES.items():
        t = time.time()
        cards = process_image(engine, encode(name, make()), cats)
        print(f"\n== {name}: {len(cards)} thẻ, {time.time() - t:.1f}s", flush=True)
        summary = []
        for c in cards:
            show = {k: c[k] for k in ("name", "title", "company", "mobile", "phone", "fax", "email",
                                     "website", "address", "address2", "category", "review", "crop_method")}
            print(json.dumps(show, ensure_ascii=False, indent=1), flush=True)
            summary.append(json.dumps(show, ensure_ascii=False) + "\nRAW: " + c["raw_text"].replace("\n", " | "))
        _annotate("notice", f"{name} ({len(cards)} the, {time.time() - t:.1f}s)", "\n\n".join(summary) or "(không có thẻ)")
        want_n, want_fields = EXPECT[name]
        if len(cards) != want_n:
            failures.append(f"{name}: tìm được {len(cards)} thẻ, cần {want_n}")
        checks = list(want_fields or [])
        if engine.recognizer == "vietocr":
            checks += EXPECT_VIETOCR.get(name, [])
        for want in checks:
            if not any(all(c.get(k) == v for k, v in want.items()) for c in cards):
                failures.append(f"{name}: không đọc đúng {want}")
    if engine.recognizer != "vietocr":
        failures.append("Không nạp được VietOCR: " + engine.load_error)
    for f in failures:
        _annotate("error", "selftest", f)
    print("\n" + ("TỰ KIỂM TRA ĐẠT" if not failures else "TỰ KIỂM TRA LỖI:\n- " + "\n- ".join(failures)), flush=True)
    return 1 if failures else 0
