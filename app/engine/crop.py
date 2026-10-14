"""Tìm và cắt từng danh thiếp trong một ảnh (ảnh chụp trên bàn, ảnh scan nhiều thẻ...),
nắn thẳng và xoay về đúng chiều đọc."""

import cv2
import numpy as np

from .ocr import OCREngine, crop_line, order_points, warp_quad

WORK_SIDE = 1000  # cạnh dài của ảnh thu nhỏ dùng để dò viền thẻ


def _resize(img: np.ndarray, side: int) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    s = min(1.0, side / max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img, s


def _quad_from_contour(cnt: np.ndarray, img_area: float) -> np.ndarray | None:
    area = cv2.contourArea(cnt)
    if area < 0.04 * img_area:
        return None
    hull = cv2.convexHull(cnt)
    peri = cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, 0.02 * peri, True)
    if len(approx) == 4:
        quad = approx.reshape(4, 2).astype(np.float32)
    else:
        rect = cv2.minAreaRect(hull)
        if cv2.contourArea(hull) < 0.85 * rect[1][0] * rect[1][1]:
            return None  # không đủ "vuông vức" để là một tấm thẻ
        quad = cv2.boxPoints(rect).astype(np.float32)
    if not cv2.isContourConvex(quad.reshape(-1, 1, 2).astype(np.int32)):
        return None
    # Vùng tìm được phải phủ gần kín khung (không phải vài nét rời rạc tạo thành khung to).
    if area < 0.8 * cv2.contourArea(quad):
        return None
    q = order_points(quad)
    w = (np.linalg.norm(q[0] - q[1]) + np.linalg.norm(q[3] - q[2])) / 2
    h = (np.linalg.norm(q[0] - q[3]) + np.linalg.norm(q[1] - q[2])) / 2
    ratio = max(w, h) / max(min(w, h), 1)
    # Danh thiếp thường có tỉ lệ 1.5–1.85 (90×55 mm ≈ 1.64). Cho phép lệch vì chụp nghiêng.
    if not 1.2 <= ratio <= 2.3:
        return None
    return q


def _overlap(a: np.ndarray, b: np.ndarray) -> float:
    """Tỉ lệ diện tích giao nhau so với tấm nhỏ hơn."""
    inter, _ = cv2.intersectConvexConvex(a.astype(np.float32), b.astype(np.float32))
    return inter / max(min(cv2.contourArea(a), cv2.contourArea(b)), 1)


def _edge_contrast(lab: np.ndarray, q: np.ndarray) -> float:
    """Độ tương phản màu ngay hai bên mép tứ giác: mép thẻ thật thì bên trong khác hẳn bên ngoài.

    Trả về giá trị của cạnh YẾU nhất (khung lấn ra nền thì sẽ có một cạnh nằm giữa nền: tương phản thấp).
    Cạnh trùng mép ảnh được bỏ qua.
    """
    h, w = lab.shape[:2]
    c = q.mean(axis=0)
    off = 0.025 * min(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[0] - q[3]))
    per_edge = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        normal = np.array([b[1] - a[1], a[0] - b[0]], dtype=np.float32)
        normal /= max(np.linalg.norm(normal), 1e-6)
        if np.dot(normal, c - (a + b) / 2) < 0:
            normal = -normal  # hướng vào trong thẻ
        diffs = []
        for t in np.linspace(0.1, 0.9, 40):
            p = a + (b - a) * t
            pin, pout = p + normal * off, p - normal * off
            xi, yi, xo, yo = int(pin[0]), int(pin[1]), int(pout[0]), int(pout[1])
            if 0 <= xo < w and 0 <= yo < h and 0 <= xi < w and 0 <= yi < h:
                diffs.append(float(np.linalg.norm(lab[yi, xi] - lab[yo, xo])))
        if len(diffs) >= 12:
            per_edge.append(float(np.median(diffs)))
    return min(per_edge) if len(per_edge) >= 2 else 0.0


def find_card_quads(bgr: np.ndarray) -> list[np.ndarray]:
    """Dò viền các tấm danh thiếp; trả về tứ giác theo tọa độ ảnh gốc."""
    small, s = _resize(bgr, WORK_SIDE)
    area = small.shape[0] * small.shape[1]
    smooth = cv2.GaussianBlur(small, (5, 5), 0)
    gray = cv2.cvtColor(smooth, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).astype(np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    masks = []
    # (1) Khác màu nền: lấy màu nền từ dải mép ảnh (bàn gỗ, mặt kính scan...), vùng khác hẳn là thẻ.
    bh, bw = max(4, small.shape[0] // 25), max(4, small.shape[1] // 25)
    border = np.concatenate([lab[:bh].reshape(-1, 3), lab[-bh:].reshape(-1, 3),
                             lab[:, :bw].reshape(-1, 3), lab[:, -bw:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)
    dist = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, md = cv2.threshold(dist, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    md = cv2.morphologyEx(md, cv2.MORPH_CLOSE, kernel, iterations=3)
    masks.append(cv2.morphologyEx(md, cv2.MORPH_OPEN, kernel, iterations=2))
    # (2) Thẻ sáng/tối hơn nền: ngưỡng Otsu theo cả hai chiều.
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    for m in (th, 255 - th):
        masks.append(cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel))
    # (3) Theo đường viền (cạnh) của thẻ.
    edges = cv2.Canny(gray, 30, 120)
    masks.append(cv2.morphologyEx(cv2.dilate(edges, kernel), cv2.MORPH_CLOSE, kernel, iterations=2))
    # (4) Thẻ trắng trên nền có màu (gỗ...): vùng ít bão hòa màu.
    sat = cv2.cvtColor(smooth, cv2.COLOR_BGR2HSV)[:, :, 1]
    _, ths = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    masks.append(cv2.morphologyEx(ths, cv2.MORPH_OPEN, kernel, iterations=2))

    cands: list[tuple[float, np.ndarray]] = []
    for m in masks:
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            q = _quad_from_contour(c, area)
            if q is None:
                continue
            # Bỏ khung trùng gần hết với mép ảnh (ảnh đã là danh thiếp, không cần cắt).
            if cv2.contourArea(q) > 0.93 * area:
                continue
            contrast = _edge_contrast(lab, q)
            if contrast < 10:
                continue  # mép mờ, không phải mép thẻ
            cands.append((contrast * np.sqrt(cv2.contourArea(q) / area), q))

    # Ưu tiên khung có mép rõ nhất; bỏ khung chồng lên khung đã chọn.
    cands.sort(key=lambda x: -x[0])
    picked: list[np.ndarray] = []
    for _, q in cands:
        if all(_overlap(q, p) < 0.3 for p in picked):
            picked.append(q)
    return [p / s for p in picked]


def text_cluster_boxes(quads: list[np.ndarray], shape) -> list[np.ndarray]:
    """Khi không thấy viền thẻ: gom các dòng chữ ở gần nhau thành từng cụm (mỗi cụm một thẻ)."""
    if not quads:
        return []
    boxes = [(q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max()) for q in quads]
    hs = [b[3] - b[1] for b in boxes]
    mh = float(np.median(hs))
    parent = list(range(len(boxes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # Các thẻ trên bàn scan cách nhau xa; trong một thẻ, cột trái/phải cách nhau gần hơn.
    gx, gy = 6.0 * mh, 4.0 * mh
    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if a[0] - gx < b[2] and b[0] - gx < a[2] and a[1] - gy < b[3] and b[1] - gy < a[3]:
                parent[find(i)] = find(j)
    groups: dict[int, list] = {}
    for i, b in enumerate(boxes):
        groups.setdefault(find(i), []).append(b)

    H, W = shape[:2]
    out = []
    biggest = max(len(g) for g in groups.values())
    for g in groups.values():
        # Cụm quá ít chữ so với cụm lớn nhất thường chỉ là mảnh của thẻ khác / chữ trên nền.
        if len(g) < 3 or len(g) < 0.25 * biggest:
            continue
        x0, y0 = min(b[0] for b in g), min(b[1] for b in g)
        x1, y1 = max(b[2] for b in g), max(b[3] for b in g)
        m = 2.5 * mh  # chừa lề để không cắt mất chữ sát mép thẻ
        x0, y0, x1, y1 = max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)
        out.append(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32))
    return out


def _rot(img: np.ndarray, quarter_turns: int) -> np.ndarray:
    return np.ascontiguousarray(np.rot90(img, k=-quarter_turns % 4)) if quarter_turns % 4 else img


def orient_card(engine: OCREngine, card: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """Xoay thẻ về đúng chiều đọc. Trả về (ảnh đã xoay, các dòng chữ đã dò)."""
    quads = engine.detect(card)
    if quads:
        ws = [np.linalg.norm(order_points(q)[0] - order_points(q)[1]) for q in quads]
        hs = [np.linalg.norm(order_points(q)[0] - order_points(q)[3]) for q in quads]
        vertical = sum(1 for w, h in zip(ws, hs) if h > 1.5 * w)
        if vertical > len(quads) / 2:  # chữ chạy dọc: thẻ đang nằm nghiêng 90°
            card = _rot(card, 1)
            quads = engine.detect(card)
    if not quads:
        return card, quads
    # Hỏi bộ phân loại góc trên những dòng dài nhất xem chữ có bị lộn ngược không.
    longest = sorted(quads, key=lambda q: -np.linalg.norm(order_points(q)[0] - order_points(q)[1]))[:8]
    votes = engine.line_angles([crop_line(card, q) for q in longest])
    upside = sum(s for lab, s in votes if lab == "180")
    upright = sum(s for lab, s in votes if lab == "0")
    if upside > upright:
        card = _rot(card, 2)
        quads = engine.detect(card)
    return card, quads


CARD_MAX_SIDE = 1800  # cạnh dài tối đa của ảnh thẻ sau khi cắt (đủ nét để đọc, không quá chậm)


def _crosses(box: np.ndarray, quad: np.ndarray) -> bool:
    """Dòng chữ nằm vắt qua mép khung (một phần trong, một phần ngoài)."""
    poly = quad.reshape(-1, 1, 2).astype(np.float32)
    inside = [cv2.pointPolygonTest(poly, (float(x), float(y)), False) >= 0 for x, y in box]
    return any(inside) and not all(inside)


def extract_cards(engine: OCREngine, bgr: np.ndarray, max_side: int = 2400) -> list[dict]:
    """Toàn bộ quy trình cho một ảnh: cắt từng thẻ → xoay đúng chiều → đọc chữ.

    Trả về danh sách {image: ảnh thẻ (BGR), lines: [...], method: cách cắt}.
    """
    img, s = _resize(bgr, max_side)  # ảnh làm việc để dò; cắt thẻ thì lấy từ ảnh gốc cho nét

    def cut(q: np.ndarray) -> np.ndarray:
        card = warp_quad(bgr, q / s)
        card, _ = _resize(card, CARD_MAX_SIDE)
        return card

    quads = find_card_quads(img)
    all_quads = engine.detect(img)
    if quads and all_quads:
        centers = [q.mean(axis=0) for q in all_quads]
        inside = sum(1 for c in centers if any(cv2.pointPolygonTest(k.reshape(-1, 1, 2), (float(c[0]), float(c[1])), False) >= 0 for k in quads))
        # Nhiều chữ nằm ngoài các khung thì khung sai (vd. ảnh đã là danh thiếp, khung chỉ là
        # một mảng màu bên trong): bỏ, chuyển sang cách gom theo cụm chữ.
        if inside < 0.7 * len(centers):
            quads = []
        # Khung cắt ngang nhiều dòng chữ thì chỉ là một mảnh, không phải cả tấm thẻ.
        quads = [k for k in quads if sum(_crosses(b, k) for b in all_quads) <= 2]
    regions: list[tuple[np.ndarray, str]] = [(cut(q), "viền thẻ") for q in quads]

    results = []
    for card, method in regions:
        card, found = orient_card(engine, card)
        if len(found) >= 3:  # khung không có (đủ) chữ thì không phải danh thiếp
            results.append({"image": card, "quads": found, "method": method})

    if not results:
        # Không dò được viền: cắt theo từng cụm chữ (có chừa lề), hoặc dùng nguyên ảnh.
        boxes = text_cluster_boxes(all_quads, img.shape)
        H, W = img.shape[:2]
        if not boxes or (len(boxes) == 1 and cv2.contourArea(boxes[0]) > 0.8 * H * W):
            boxes = [None]
        for b in boxes:
            if b is None:
                card, _ = _resize(bgr, CARD_MAX_SIDE)
            else:
                card = cut(b)
            card, found = orient_card(engine, card)
            if found:
                results.append({"image": card, "quads": found, "method": "cả ảnh" if b is None else "cụm chữ"})

    for r in results:
        r["lines"] = engine.read_lines(r["image"], r.pop("quads"))
    return results
