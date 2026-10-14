"""API nội bộ của app desktop (chỉ chạy trên máy bạn, địa chỉ 127.0.0.1)."""

import json
import os
import shutil
import zipfile
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine.classify import DEFAULT_FILE as DEFAULT_CATEGORIES, load_categories
from .engine.pipeline import FIELDS, analyze_card, process_image
from .export import export_vcf, export_xlsx
from .learn import Learner
from .storage import Store, default_data_dir

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD = 40 * 1024 * 1024


class State:
    engine = None
    engine_error = ""
    ready = threading.Event()
    store: Store | None = None
    learner: Learner | None = None
    categories_file: Path | None = None


state = State()


def categories() -> list[dict]:
    return load_categories(state.categories_file)


def _load_engine(use_vietocr: bool):
    try:
        from .engine.ocr import OCREngine

        state.engine = OCREngine(use_vietocr=use_vietocr)
    except Exception as exc:
        state.engine_error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        state.ready.set()


def init(data_dir: Path | None = None, use_vietocr: bool = True, background: bool = True):
    data_dir = Path(data_dir or default_data_dir())
    state.store = Store(data_dir)
    state.categories_file = data_dir / "phan-loai.json"
    state.learner = Learner(data_dir / "hoc-tu-sua.json")
    if not state.categories_file.exists():
        shutil.copy(DEFAULT_CATEGORIES, state.categories_file)
    if background:
        threading.Thread(target=_load_engine, args=(use_vietocr,), daemon=True).start()
    else:
        _load_engine(use_vietocr)


def open_path(path: Path):
    if os.environ.get("DANHTHIEP_NO_OPEN") == "1":
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        print("Không mở được", path, exc, flush=True)


def get_engine():
    if not state.ready.wait(timeout=600) or state.engine is None:
        raise HTTPException(503, f"Bộ nhận dạng chưa sẵn sàng. {state.engine_error}")
    return state.engine


app = FastAPI(title="Danh thiếp")


@app.get("/api/status")
def status():
    e = state.engine
    return {
        "ready": state.ready.is_set() and e is not None,
        "loading": not state.ready.is_set(),
        "error": state.engine_error,
        "recognizer": e.recognizer if e else "",
        "vietocr_error": e.load_error if e else "",
        "data_dir": str(state.store.dir),
        "categories": [c["name"] for c in categories()],
    }


@app.post("/api/process")
def process(file: UploadFile = File(...), batch: str = Form("")):
    engine = get_engine()
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Ảnh quá lớn (tối đa 40 MB).")
    t0 = time.time()
    try:
        found = process_image(engine, data, categories())
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(400, f"Không xử lý được ảnh: {exc}") from exc
    saved = []
    for info in found:
        info["auto_fields"] = json.dumps({f: info.get(f, "") for f in FIELDS + ["category"]}, ensure_ascii=False)
        learned = state.learner.apply(info)
        if learned:
            print(f"Áp dụng điều đã học: {learned} cho {info.get('company')}", flush=True)
        dup = state.store.find_duplicate(info)
        if dup:
            info["review"] = ", ".join(x for x in (info.get("review"), f"có thể trùng với {dup}") if x)
        info["source_file"] = file.filename or ""
        info["batch"] = batch
        saved.append(state.store.add(info))
    return {"cards": saved, "seconds": round(time.time() - t0, 1)}


@app.get("/api/cards")
def list_cards():
    return state.store.all()


class CardUpdate(BaseModel):
    fields: dict


@app.patch("/api/cards/{card_id}")
def update_card(card_id: str, body: CardUpdate):
    before = state.store.get(card_id)
    if not before:
        raise HTTPException(404, "Không tìm thấy danh thiếp")
    card = state.store.update(card_id, body.fields)
    changed = {k: v for k, v in body.fields.items() if k in ("category", "company") and before.get(k) != v}
    if changed:
        state.learner.record(card, changed)
    return card


class Ids(BaseModel):
    ids: list[str]
    category: str = ""


@app.post("/api/cards/delete")
def delete_cards(body: Ids):
    state.store.delete(body.ids)
    return {"ok": True}


@app.post("/api/cards/category")
def set_category(body: Ids):
    for i in body.ids:
        card = state.store.update(i, {"category": body.category})
        if card:
            state.learner.record(card, {"category": body.category})
    return {"ok": True}


@app.post("/api/cards/{card_id}/rotate")
def rotate_card(card_id: str):
    """Xoay ảnh thẻ 90° theo chiều kim đồng hồ rồi nhận dạng lại."""
    import cv2

    card = state.store.get(card_id)
    if not card:
        raise HTTPException(404, "Không tìm thấy danh thiếp")
    engine = get_engine()
    path = state.store.image_path(card_id)
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    img = np.ascontiguousarray(np.rot90(img, k=-1))
    state.store.save_image(card_id, img)
    lines = engine.read_lines(img)
    info = analyze_card(engine, img, lines, categories())
    keep_note = card.get("note")
    state.learner.apply(info)
    card = state.store.replace_analysis(card_id, info)
    if keep_note and not info.get("note"):
        card = state.store.update(card_id, {"note": keep_note})
    return card


@app.get("/api/cards/{card_id}/image")
def card_image(card_id: str):
    path = state.store.image_path(card_id)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


class ExportReq(BaseModel):
    format: str = "xlsx"
    ids: list[str] = []
    images: bool = True


@app.post("/api/export")
def export(body: ExportReq):
    cards = state.store.all()
    if body.ids:
        wanted = set(body.ids)
        cards = [c for c in cards if c["id"] in wanted]
    if not cards:
        raise HTTPException(400, "Chưa có danh thiếp nào để xuất.")
    cards.sort(key=lambda c: (c.get("category") or "", (c.get("company") or "").lower(), (c.get("name") or "").lower()))
    stamp = time.strftime("%Y-%m-%d_%H%M")
    if body.format == "calib":
        path = export_calibration(cards, state.store.exports_dir / f"goi-hieu-chinh_{stamp}.zip")
        if path is None:
            raise HTTPException(400, "Chưa có thẻ nào được sửa tay. Hãy sửa các thẻ bị đọc sai trước.")
        open_path(path.parent)
        return {"path": str(path), "count": len(json.loads(zipfile.ZipFile(path).read("the-da-sua.json")))}
    if body.format == "vcf":
        path = export_vcf(cards, state.store.exports_dir / f"danh-thiep_{stamp}.vcf")
    else:
        path = export_xlsx(cards, state.store.cards_dir, state.store.exports_dir / f"danh-thiep_{stamp}.xlsx", body.images)
    open_path(path)
    return {"path": str(path), "count": len(cards)}


def export_calibration(cards: list[dict], out: Path) -> Path | None:
    """Gói các thẻ đã sửa tay: ảnh thẻ + chữ máy đọc + kết quả máy tách + kết quả bạn sửa."""
    keys = FIELDS + ["category"]
    items = []
    for c in cards:
        try:
            auto = json.loads(c.get("auto_fields") or "{}")
        except ValueError:
            auto = {}
        if not auto:
            continue
        final = {k: c.get(k, "") or "" for k in keys}
        diff = [k for k in keys if (auto.get(k) or "") != final[k] and k != "note"]
        if diff:
            items.append({"id": c["id"], "source_file": c.get("source_file"), "raw_text": c.get("raw_text"),
                          "qr_text": c.get("qr_text"), "fields_changed": diff, "auto": auto, "final": final})
    if not items:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("the-da-sua.json", json.dumps(items, ensure_ascii=False, indent=1))
        for it in items:
            img = state.store.image_path(it["id"])
            if img.exists():
                z.write(img, f"anh/{it['id']}.jpg")
    return out


class OpenReq(BaseModel):
    what: str


@app.post("/api/open")
def open_folder(body: OpenReq):
    target = {
        "data": state.store.dir,
        "exports": state.store.exports_dir,
        "categories": state.categories_file,
    }.get(body.what)
    if target is None:
        raise HTTPException(400)
    open_path(target)
    return {"path": str(target)}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
