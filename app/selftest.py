"""Tự kiểm tra: chạy toàn bộ quy trình trên các ảnh mẫu và in kết quả (dùng khi build trên Windows)."""

import json
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
}
# Chỉ kiểm tra khi dùng VietOCR (đọc được tiếng Việt có dấu).
EXPECT_VIETOCR = {
    "anh_chup_ban_go.jpg": [{"name": "Nguyen Dang Quang"}],
    "danh_thiep_dien_tu.png": [{"name": "Vũ Anh Kim Long", "company": "Công Ty TNHH CESCO"}],
}


def run() -> int:
    t0 = time.time()
    engine = OCREngine()
    print(f"Bộ đọc chữ: {engine.recognizer} (nạp trong {time.time() - t0:.1f}s) {engine.load_error}", flush=True)
    cats = load_categories()
    failures = []
    for name, make in SAMPLES.items():
        t = time.time()
        cards = process_image(engine, encode(name, make()), cats)
        print(f"\n== {name}: {len(cards)} thẻ, {time.time() - t:.1f}s", flush=True)
        for c in cards:
            show = {k: c[k] for k in ("name", "title", "company", "mobile", "phone", "fax", "email",
                                     "website", "address", "address2", "category", "review", "crop_method")}
            print(json.dumps(show, ensure_ascii=False, indent=1), flush=True)
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
    print("\n" + ("TỰ KIỂM TRA ĐẠT" if not failures else "TỰ KIỂM TRA LỖI:\n- " + "\n- ".join(failures)), flush=True)
    return 1 if failures else 0
