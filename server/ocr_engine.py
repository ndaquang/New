"""Nhận dạng chữ trên ảnh danh thiếp.

Quy trình 2 bước:
  1. RapidOCR (DBNet, ONNX) tìm vị trí các dòng chữ trong ảnh.
  2. VietOCR đọc nội dung từng dòng (hỗ trợ tiếng Việt có dấu).
"""

import os
import threading
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import torch
import yaml
from PIL import Image, ImageOps

# VietOCR 0.3.x vẫn dùng Image.ANTIALIAS, đã bị bỏ từ Pillow 10.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

CONFIG_DIR = Path(__file__).parent / "vietocr_config"
DEFAULT_WEIGHTS_URL = "https://vocr.vn/data/vietocr/vgg_seq2seq.pth"
DEFAULT_WEIGHTS_PATH = Path(__file__).parent / "weights" / "vgg_seq2seq.pth"


def ensure_weights(path: Path, url: str) -> Path:
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    print(f"Đang tải trọng số VietOCR từ {url} ...", flush=True)
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(path)
    return path


def load_vietocr_config() -> dict:
    with open(CONFIG_DIR / "base.yml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(CONFIG_DIR / "vgg-seq2seq.yml", encoding="utf-8") as f:
        cfg.update(yaml.safe_load(f))
    cfg["device"] = "cpu"
    cfg["cnn"]["pretrained"] = False  # trọng số đầy đủ được nạp ngay sau đó
    cfg["predictor"]["beamsearch"] = False
    return cfg


def order_points(pts: np.ndarray) -> np.ndarray:
    """Sắp xếp 4 góc theo thứ tự: trên-trái, trên-phải, dưới-phải, dưới-trái."""
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype=np.float32,
    )


def crop_quad(img: np.ndarray, quad: np.ndarray, pad: float = 0.12) -> np.ndarray:
    """Cắt vùng chữ (tứ giác) và nắn thẳng thành hình chữ nhật."""
    q = order_points(quad.astype(np.float32))
    w = int(max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2])))
    h = int(max(np.linalg.norm(q[0] - q[3]), np.linalg.norm(q[1] - q[2])))
    w, h = max(w, 1), max(h, 1)
    # Nới rộng một chút để không mất dấu tiếng Việt ở trên/dưới dòng.
    center = q.mean(axis=0)
    q = center + (q - center) * np.array([1 + pad * h / w, 1 + pad * 2], dtype=np.float32)
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(q.astype(np.float32), dst)
    out = cv2.warpPerspective(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)
    if h > w * 1.5:
        out = np.rot90(out)
    return out


def group_into_lines(items: list[dict]) -> list[dict]:
    """Ghép các đoạn chữ nằm cùng một hàng thành một dòng, theo thứ tự đọc."""
    items = sorted(items, key=lambda it: (it["box"][1] + it["box"][3]) / 2)
    rows: list[list[dict]] = []
    for it in items:
        cy = (it["box"][1] + it["box"][3]) / 2
        h = it["box"][3] - it["box"][1]
        if rows:
            last = rows[-1]
            ly = sum((x["box"][1] + x["box"][3]) / 2 for x in last) / len(last)
            lh = sum(x["box"][3] - x["box"][1] for x in last) / len(last)
            if abs(cy - ly) < 0.5 * min(h, lh):
                last.append(it)
                continue
        rows.append([it])

    lines = []
    for row in rows:
        row.sort(key=lambda x: x["box"][0])
        # Hai đoạn cách xa nhau trên cùng hàng (vd. 2 cột) thì giữ thành 2 dòng.
        segs: list[list[dict]] = [[row[0]]]
        for it in row[1:]:
            prev = segs[-1][-1]
            gap = it["box"][0] - prev["box"][2]
            if gap > 2.5 * (prev["box"][3] - prev["box"][1]):
                segs.append([it])
            else:
                segs[-1].append(it)
        for seg in segs:
            text = " ".join(x["text"] for x in seg if x["text"]).strip()
            if not text:
                continue
            box = [
                min(x["box"][0] for x in seg),
                min(x["box"][1] for x in seg),
                max(x["box"][2] for x in seg),
                max(x["box"][3] for x in seg),
            ]
            lines.append(
                {
                    "text": text,
                    "box": [int(v) for v in box],
                    "height": int(box[3] - box[1]),
                    "confidence": round(float(np.mean([x["confidence"] for x in seg])), 3),
                }
            )
    return lines


class CardOCR:
    def __init__(self, weights_path: Path | None = None, weights_url: str | None = None):
        from rapidocr_onnxruntime import RapidOCR
        from vietocr.tool.predictor import Predictor
        from vietocr.tool.translate import build_model

        torch.set_num_threads(int(os.environ.get("OCR_THREADS", "2")))
        weights_path = Path(weights_path or os.environ.get("VIETOCR_WEIGHTS", DEFAULT_WEIGHTS_PATH))
        weights_url = weights_url or os.environ.get("VIETOCR_WEIGHTS_URL", DEFAULT_WEIGHTS_URL)
        ensure_weights(weights_path, weights_url)

        cfg = load_vietocr_config()
        model, vocab = build_model(cfg)
        model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        model.eval()
        # Tự dựng Predictor để không phải tải cấu hình/trọng số từ Internet mỗi lần khởi động.
        self.predictor = Predictor.__new__(Predictor)
        self.predictor.config = cfg
        self.predictor.model = model
        self.predictor.vocab = vocab
        self.predictor.device = "cpu"

        self.detector = RapidOCR()
        self.lock = threading.Lock()

    def recognize(self, image_bytes: bytes, max_side: int = 1800) -> dict:
        import io

        pil = Image.open(io.BytesIO(image_bytes))
        pil = ImageOps.exif_transpose(pil).convert("RGB")
        if max(pil.size) > max_side:
            pil.thumbnail((max_side, max_side))
        rgb = np.asarray(pil)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        with self.lock:
            boxes, _ = self.detector(bgr, use_det=True, use_cls=False, use_rec=False)
            boxes = boxes if boxes is not None else []
            quads = [np.array(b, dtype=np.float32).reshape(4, 2) for b in boxes]
            crops = [Image.fromarray(np.ascontiguousarray(crop_quad(rgb, q))) for q in quads]
            if crops:
                with torch.no_grad():
                    texts, probs = self.predictor.predict_batch(crops, return_prob=True)
            else:
                texts, probs = [], []

        items = []
        for q, text, prob in zip(quads, texts, probs):
            items.append(
                {
                    "text": text.strip(),
                    "box": [float(q[:, 0].min()), float(q[:, 1].min()), float(q[:, 0].max()), float(q[:, 1].max())],
                    "confidence": float(prob),
                }
            )
        lines = group_into_lines(items)
        return {
            "width": pil.size[0],
            "height": pil.size[1],
            "lines": lines,
            "text": "\n".join(line["text"] for line in lines),
        }
