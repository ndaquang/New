"""Tìm dòng chữ (RapidOCR/DBNet) và đọc chữ (VietOCR) trên ảnh danh thiếp."""

import os
import re
import sys
import threading
import types
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# VietOCR 0.3.x vẫn dùng Image.ANTIALIAS, đã bị bỏ từ Pillow 10.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "vietocr_config"
WEIGHTS_URL = "https://vocr.vn/data/vietocr/vgg_seq2seq.pth"
BUNDLED_WEIGHTS = APP_DIR / "weights" / "vgg_seq2seq.pth"


def ensure_weights(path: Path, url: str = WEIGHTS_URL) -> Path:
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    print(f"Đang tải trọng số VietOCR từ {url} ...", flush=True)
    try:
        urllib.request.urlretrieve(url, tmp)
    except Exception as exc:
        # Python trên Windows hay lỗi chứng chỉ HTTPS với một số máy chủ; curl của Windows thì không.
        import shutil
        import subprocess

        curl = shutil.which("curl") or shutil.which("curl.exe")
        if not curl:
            raise
        print(f"Tải bằng Python lỗi ({exc}); thử lại bằng curl ...", flush=True)
        res = subprocess.run([curl, "-fL", "--retry", "3", "-o", str(tmp), url], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Không tải được trọng số VietOCR: {exc}; curl: {res.stderr.strip()[-300:]}") from exc
    if tmp.stat().st_size < 1_000_000:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("File trọng số VietOCR tải về không hợp lệ")
    tmp.replace(path)
    return path


def order_points(pts: np.ndarray) -> np.ndarray:
    """Sắp 4 góc theo thứ tự: trên-trái, trên-phải, dưới-phải, dưới-trái."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]],
        dtype=np.float32,
    )


def warp_quad(img: np.ndarray, quad: np.ndarray, pad_x: float = 0.0, pad_y: float = 0.0) -> np.ndarray:
    """Cắt một tứ giác trong ảnh và nắn thẳng thành hình chữ nhật."""
    q = order_points(quad)
    w = int(max(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[3] - q[2])))
    h = int(max(np.linalg.norm(q[0] - q[3]), np.linalg.norm(q[1] - q[2])))
    w, h = max(w, 1), max(h, 1)
    if pad_x or pad_y:
        center = q.mean(axis=0)
        q = center + (q - center) * np.array([1 + pad_x, 1 + pad_y], dtype=np.float32)
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(q.astype(np.float32), dst)
    return cv2.warpPerspective(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def crop_line(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Cắt một dòng chữ, nới rộng chút để không mất dấu tiếng Việt."""
    q = order_points(quad)
    w = max(np.linalg.norm(q[0] - q[1]), 1.0)
    h = max(np.linalg.norm(q[0] - q[3]), 1.0)
    out = warp_quad(img, q, pad_x=0.12 * h / w, pad_y=0.24)
    if out.shape[0] > out.shape[1] * 1.5:
        out = np.ascontiguousarray(np.rot90(out))
    return out


def quad_bbox(q: np.ndarray) -> list[float]:
    return [float(q[:, 0].min()), float(q[:, 1].min()), float(q[:, 0].max()), float(q[:, 1].max())]


def group_into_lines(items: list[dict]) -> list[dict]:
    """Ghép các đoạn chữ cùng hàng thành dòng, sắp theo thứ tự đọc."""
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
            ph, ih = prev["box"][3] - prev["box"][1], it["box"][3] - it["box"][1]
            # Cách xa (2 cột) hoặc cỡ chữ khác hẳn (logo cạnh chức vụ) thì là 2 dòng riêng.
            if it["box"][0] - prev["box"][2] > 1.2 * min(ph, ih) or max(ph, ih) > 1.6 * min(ph, ih):
                segs.append([it])
            else:
                segs[-1].append(it)
        for seg in segs:
            text = " ".join(x["text"] for x in seg if x["text"]).strip()
            if not text:
                continue
            box = [min(x["box"][0] for x in seg), min(x["box"][1] for x in seg),
                   max(x["box"][2] for x in seg), max(x["box"][3] for x in seg)]
            lines.append({
                "text": text,
                "box": [int(v) for v in box],
                "height": int(box[3] - box[1]),
                "confidence": round(float(np.mean([x["confidence"] for x in seg])), 3),
            })
    return lines


VIET_CHARS = re.compile(r"[^\x00-\x7f]")


def pick_line(viet: tuple[str, float], rapid: tuple[str, float]) -> tuple[str, float]:
    """Chọn kết quả tốt hơn cho một dòng: VietOCR (tiếng Việt có dấu) hay RapidOCR (số, email).

    VietOCR hay đọc sai chữ số ("+84 28" -> "08422") và "@" (-> D/O/Q); RapidOCR đọc đúng
    nhưng không có dấu tiếng Việt và hay dính liền chữ. Nên chỉ dùng RapidOCR cho dòng email
    và dòng phần lớn là chữ số (điện thoại, fax, mã số thuế).
    """
    v_text, _ = viet
    r_text, r_score = rapid
    if not r_text or r_score < 0.7:
        return viet
    if "@" in r_text and "@" not in v_text and not VIET_CHARS.search(r_text):
        return rapid
    body = re.sub(r"\s", "", r_text)
    digits = sum(ch.isdigit() for ch in body)
    if digits >= 7 and digits >= 0.5 * len(body):
        # Giữ nhãn có dấu của VietOCR ("Điện thoại:", "ĐT/Fax:") nếu có, thay phần số.
        label = re.match(r"^\s*([^\d+(]*?[:：]\s*)", v_text)
        r_num = re.sub(r"^[^\d+(]*", "", r_text)
        if label and VIET_CHARS.search(label.group(1)):
            return label.group(1) + r_num, r_score
        return r_text, r_score
    return viet


class OCREngine:
    """Gom các mô hình lại một chỗ; nạp một lần, dùng cho mọi ảnh."""

    def __init__(self, weights_path: Path | None = None, use_vietocr: bool = True):
        from rapidocr_onnxruntime import RapidOCR

        self.rapid = RapidOCR()
        self.lock = threading.Lock()
        self.predictor = None
        self.recognizer = "rapidocr"
        self.load_error = ""
        if use_vietocr:
            try:
                self._load_vietocr(Path(weights_path or os.environ.get("VIETOCR_WEIGHTS") or BUNDLED_WEIGHTS))
                self.recognizer = "vietocr"
            except Exception as exc:  # không tải được trọng số: dùng tạm bộ đọc của RapidOCR
                self.load_error = f"{type(exc).__name__}: {exc}"
                print("Không nạp được VietOCR, dùng tạm RapidOCR:", self.load_error, flush=True)

    def _load_vietocr(self, weights_path: Path):
        import torch
        import yaml

        # vietocr nhập gdown (cần pkg_resources) dù không dùng tới; thay bằng module rỗng nếu thiếu.
        try:
            import gdown  # noqa: F401
        except Exception:
            sys.modules["gdown"] = types.ModuleType("gdown")
        from vietocr.tool.predictor import Predictor
        from vietocr.tool.translate import build_model

        ensure_weights(weights_path)
        torch.set_num_threads(int(os.environ.get("OCR_THREADS", max(1, min(4, os.cpu_count() or 2)))))
        with open(CONFIG_DIR / "base.yml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        with open(CONFIG_DIR / "vgg-seq2seq.yml", encoding="utf-8") as f:
            cfg.update(yaml.safe_load(f))
        cfg["device"] = "cpu"
        cfg["cnn"]["pretrained"] = False
        cfg["predictor"]["beamsearch"] = False
        model, vocab = build_model(cfg)
        model.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        model.eval()
        # Tự dựng Predictor để không phải tải cấu hình từ Internet như Predictor(config) mặc định.
        pred = Predictor.__new__(Predictor)
        pred.config, pred.model, pred.vocab, pred.device = cfg, model, vocab, "cpu"
        self.predictor = pred
        self._torch = torch

    # ----- các bước cơ bản -----
    def detect(self, bgr: np.ndarray) -> list[np.ndarray]:
        boxes, _ = self.rapid(bgr, use_det=True, use_cls=False, use_rec=False)
        return [np.array(b, dtype=np.float32).reshape(4, 2) for b in (boxes if boxes is not None else [])]

    def line_angles(self, crops: list[np.ndarray]) -> list[tuple[str, float]]:
        """Bộ phân loại góc của RapidOCR: mỗi dòng là '0' (thuận) hay '180' (ngược)."""
        if not crops:
            return []
        _, cls_res, _ = self.rapid.text_cls([c.copy() for c in crops])
        return [(str(label), float(score)) for label, score in cls_res]

    def recognize(self, crops_bgr: list[np.ndarray]) -> list[tuple[str, float]]:
        if not crops_bgr:
            return []
        if self.predictor is not None:
            pils = [Image.fromarray(cv2.cvtColor(c, cv2.COLOR_BGR2RGB)) for c in crops_bgr]
            with self._torch.no_grad():
                texts, probs = self.predictor.predict_batch(pils, return_prob=True)
            viet = [(t.strip(), float(p)) for t, p in zip(texts, probs)]
            # Đọc lần 2 bằng RapidOCR: giỏi chữ số và ký tự @ hơn VietOCR.
            rapid, _ = self.rapid.text_rec([c.copy() for c in crops_bgr], False)
            return [pick_line(v, (r[0].strip(), float(r[1]))) for v, r in zip(viet, rapid)]
        res, _ = self.rapid.text_rec(crops_bgr, False)
        return [(r[0].strip(), float(r[1])) for r in res]

    def read_lines(self, bgr: np.ndarray, quads: list[np.ndarray] | None = None) -> list[dict]:
        """Đọc toàn bộ chữ trên một ảnh danh thiếp đã cắt và xoay đúng chiều."""
        with self.lock:
            quads = self.detect(bgr) if quads is None else quads
            crops = [crop_line(bgr, q) for q in quads]
            results = self.recognize(crops)
        items = [{"text": t, "box": quad_bbox(q), "confidence": p} for q, (t, p) in zip(quads, results)]
        return group_into_lines(items)
