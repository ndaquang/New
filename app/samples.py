"""Vẽ ảnh danh thiếp mẫu (mô phỏng ảnh chụp/scan thật) để tự kiểm tra bộ xử lý."""

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = {
    "regular": ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "bold": ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


def font(size: int, bold: bool = False):
    for p in FONT_CANDIDATES["bold" if bold else "regular"]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def card_viteccons() -> np.ndarray:
    """Giống danh thiếp VITECCONS: logo trái, thông tin phải, dải màu dưới, 2 địa chỉ."""
    W, H = 1050, 600
    im = Image.new("RGB", (W, H), "#fbfbf8")
    d = ImageDraw.Draw(im)
    d.text((95, 150), "VITECCONS", font=font(46, True), fill="#2a3a8c")
    d.text((140, 205), "BUILD BY HEART", font=font(16, True), fill="#c0282d")
    d.line([(425, 120), (425, 500)], fill="#c0282d", width=3)
    d.text((460, 118), "NGUYEN DANG QUANG", font=font(38, True), fill="#2a3a8c")
    d.text((460, 168), "Head of Tender Department", font=font(26, True), fill="#c0282d")
    f = font(25)
    d.ellipse((462, 247, 482, 267), fill="#2a3a8c")
    d.text((500, 243), "0795 688 399", font=f, fill="#222")
    d.ellipse((462, 287, 482, 307), fill="#2a3a8c")
    d.text((500, 283), "quang.nguyen@viteccons.vn", font=f, fill="#222")
    y = 323
    for label, rows in (("HCM:", ["109 Hoang Hoa Tham, Gia", "Dinh Ward, Ho Chi Minh City,", "Vietnam."]),
                        ("HN:", ["No. 4NVC1, Lot 4, The Manor", "Central Park, Dinh Cong Ward,", "Ha Noi City, Vietnam."])):
        d.text((500, y), label, font=f, fill="#222")
        for row in rows:
            d.text((575, y), row, font=f, fill="#222")
            y += 36
        y += 10
    d.rectangle((0, 548, 425, 600), fill="#c0282d")
    d.rectangle((425, 548, W, 600), fill="#2a3a8c")
    d.text((70, 558), "www.viteccons.vn", font=font(24, True), fill="white")
    d.text((760, 558), "MST: 0309553779", font=font(24), fill="white")
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def card_cesco() -> np.ndarray:
    """Giống danh thiếp CESCO: có mã QR, chức vụ 2 dòng, nhãn "Trụ Sở :", "ĐT/Fax :", "MST :"."""
    W, H = 1024, 624
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((60, 100), "CESCO", font=font(84, True), fill="#e0333c")
    d.text((65, 190), "Your trustworthy partner", font=font(24), fill="#e0333c")
    vcard = "BEGIN:VCARD\nVERSION:3.0\nN:Vũ;Anh Kim Long\nFN:Vũ Anh Kim Long\nORG:CESCO\nTEL;TYPE=CELL:+84918196121\nEMAIL:long.vu@cesco.com.vn\nEND:VCARD"
    qr = cv2.QRCodeEncoder.create().encode(vcard)
    qr = cv2.resize(qr, (210, 210), interpolation=cv2.INTER_NEAREST)
    im.paste(Image.fromarray(qr).convert("RGB"), (108, 280))
    d.text((80, 512), "www.cesco.com.vn", font=font(26), fill="#1e88d8")
    d.text((478, 80), "Vũ Anh Kim Long", font=font(32, True), fill="black")
    f = font(25)
    for i, t in enumerate(["Trưởng bộ phận bán hàng kỹ thuật End user", "Service sales manager-IEM",
                           "Hp: (+84) 918 196 121", "Email: long.vu@cesco.com.vn"]):
        d.text((478, 122 + i * 36), t, font=f, fill="black")
    d.text((478, 272), "Công Ty TNHH CESCO", font=font(30, True), fill="#1e88d8")
    d.text((478, 316), "CESCO Co., Ltd", font=font(30, True), fill="#1e88d8")
    f2 = font(21)
    fb = font(21, True)
    rows = [("Trụ Sở", ": Số 6 Đường số 2, Kp.5"), (None, "P.Hiệp Bình Phước, TP.Thủ Đức, Tp.HCM"),
            ("Headquater", ": 6 Street 2, Quarter 5"), (None, "H.B.Phuoc Ward, Thu Duc City, HCM City"),
            ("ĐT/Fax", ": +84 28 3727 3079"), ("MST", ": 0312 522 851")]
    for i, (lab, val) in enumerate(rows):
        y = 368 + i * 33
        if lab:
            d.text((478, y), lab, font=fb, fill="black")
            d.text((610, y), val, font=f2, fill="black")
        else:
            d.text((478, y), val, font=f2, fill="black")
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def _background(w: int, h: int, kind: str, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if kind == "wood":
        y = np.arange(h)[:, None]
        x = np.arange(w)[None, :]
        grain = (np.sin(y / 9.0 + np.sin(x / 140.0) * 3) * 12 + rng.normal(0, 6, (h, w))).astype(np.float32)
        bg = np.stack([95 + grain, 135 + grain, 175 + grain], axis=2)
    else:  # mặt kính máy scan / bàn xám
        bg = np.full((h, w, 3), 205, np.float32) + rng.normal(0, 4, (h, w, 1))
    return np.clip(bg, 0, 255).astype(np.uint8)


def place(bg: np.ndarray, card: np.ndarray, corners) -> np.ndarray:
    """Dán thẻ lên nền theo 4 góc (mô phỏng chụp nghiêng/phối cảnh), có bóng đổ nhẹ."""
    h, w = card.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32(corners)
    m = cv2.getPerspectiveTransform(src, dst)
    size = (bg.shape[1], bg.shape[0])
    warped = cv2.warpPerspective(card, m, size, flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), m, size)
    shadow = cv2.GaussianBlur(cv2.warpPerspective(np.full((h, w), 90, np.uint8), m, size), (31, 31), 0)
    out = bg.astype(np.int16) - np.roll(shadow, (8, 8), (0, 1))[:, :, None] // 2
    out = np.clip(out, 0, 255).astype(np.uint8)
    out[mask > 0] = warped[mask > 0]
    return out


def sample_photo() -> np.ndarray:
    """Một thẻ chụp nghiêng trên mặt bàn gỗ (giống ảnh mẫu VITECCONS)."""
    bg = _background(1600, 1200, "wood", 1)
    return place(bg, card_viteccons(), [[170, 160], [1440, 215], [1405, 1000], [130, 950]])


def sample_scan_two() -> np.ndarray:
    """Hai thẻ trên mặt kính máy scan, một thẻ bị lộn ngược."""
    bg = _background(2200, 1500, "scan", 2)
    a = cv2.resize(card_viteccons(), (840, 480))
    b = cv2.rotate(cv2.resize(card_cesco(), (820, 500)), cv2.ROTATE_180)
    bg = place(bg, a, [[120, 140], [960, 160], [950, 640], [110, 620]])
    return place(bg, b, [[1180, 700], [2000, 680], [2010, 1180], [1190, 1200]])


def sample_digital() -> np.ndarray:
    """Ảnh danh thiếp điện tử, không có nền (giống ảnh mẫu CESCO)."""
    return card_cesco()


def sample_rotated() -> np.ndarray:
    """Thẻ chụp xoay 90° (điện thoại cầm dọc)."""
    bg = _background(1200, 1600, "wood", 3)
    card = cv2.rotate(card_viteccons(), cv2.ROTATE_90_CLOCKWISE)
    return place(bg, card, [[260, 180], [930, 200], [950, 1400], [240, 1380]])


SAMPLES = {
    "anh_chup_ban_go.jpg": sample_photo,
    "scan_hai_the.jpg": sample_scan_two,
    "danh_thiep_dien_tu.png": sample_digital,
    "chup_xoay_doc.jpg": sample_rotated,
}


def encode(name: str, img: np.ndarray) -> bytes:
    ext = Path(name).suffix
    return cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 88] if ext == ".jpg" else [])[1].tobytes()


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in SAMPLES.items():
        (out / name).write_bytes(encode(name, fn()))
        print("Đã tạo", out / name)
