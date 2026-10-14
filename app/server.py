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

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine.classify import DEFAULT_FILE as DEFAULT_CATEGORIES, load_categories, sync_user_categories
from .engine.pipeline import FIELDS, analyze_card, fields_from_text, process_image
from .dw_export import export_dw
from .export import export_vcf, export_xlsx
from .learn import Learner
from .storage import Store, default_data_dir

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD = 40 * 1024 * 1024


class InProcessRunner:
    """Chạy bộ nhận dạng ngay trong tiến trình này (dùng cho kiểm thử)."""

    def __init__(self, use_vietocr: bool):
        from .engine.ocr import OCREngine

        self.engine = OCREngine(use_vietocr=use_vietocr)
        self.recognizer, self.load_error, self.error, self.restarts = self.engine.recognizer, self.engine.load_error, "", 0

    def run(self, kind, payload, timeout=None):
        if kind == "process":
            return process_image(self.engine, *payload)
        img, cats = payload
        return analyze_card(self.engine, img, self.engine.read_lines(img), cats)


class State:
    runner = None
    engine_error = ""
    ready = threading.Event()
    store: Store | None = None
    learner: Learner | None = None
    categories_file: Path | None = None


state = State()


def categories() -> list[dict]:
    return load_categories(state.categories_file)


def _load_engine(use_vietocr: bool, use_worker: bool, timeout: float):
    try:
        if use_worker:
            from .worker import OCRWorker

            w = OCRWorker(use_vietocr=use_vietocr, timeout=timeout)
            w.start()
            if w.error:
                raise RuntimeError(w.error)
            state.runner = w
        else:
            state.runner = InProcessRunner(use_vietocr)
    except Exception as exc:
        state.engine_error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        state.ready.set()


def init(data_dir: Path | None = None, use_vietocr: bool = True, background: bool = True,
         use_worker: bool = False, timeout: float = 180.0):
    data_dir = Path(data_dir or default_data_dir())
    state.store = Store(data_dir)
    state.categories_file = data_dir / "phan-loai.json"
    state.learner = Learner(data_dir / "hoc-tu-sua.json")
    if not state.categories_file.exists():
        shutil.copy(DEFAULT_CATEGORIES, state.categories_file)
    elif sync_user_categories(state.categories_file):
        print("Đã cập nhật từ khóa phân loại mới vào", state.categories_file, flush=True)
    state.ready.clear()
    args = (use_vietocr, use_worker, timeout)
    if background:
        threading.Thread(target=_load_engine, args=args, daemon=True).start()
    else:
        _load_engine(*args)


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


def get_runner():
    if not state.ready.wait(timeout=900) or state.runner is None:
        raise HTTPException(503, f"Bộ nhận dạng chưa sẵn sàng. {state.engine_error}")
    return state.runner


app = FastAPI(title="Danh thiếp")


@app.get("/api/status")
def status():
    r = state.runner
    return {
        "ready": state.ready.is_set() and r is not None,
        "loading": not state.ready.is_set(),
        "error": state.engine_error or (r.error if r else ""),
        "recognizer": r.recognizer if r else "",
        "vietocr_error": r.load_error if r else "",
        "restarts": r.restarts if r else 0,
        "data_dir": str(state.store.dir),
        "categories": [c["name"] for c in categories()],
    }


class FileCheck(BaseModel):
    fingerprints: list[str]


@app.post("/api/files/check")
def files_check(body: FileCheck):
    """Ảnh nào đã xử lý xong ở lần trước (chạy lại sau khi treo/tắt app thì bỏ qua)."""
    return {"done": state.store.done_files(body.fingerprints)}


@app.post("/api/files/forget")
def files_forget():
    state.store.forget_files()
    return {"ok": True}


@app.post("/api/process")
def process(file: UploadFile = File(...), batch: str = Form(""), fingerprint: str = Form(""),
            skip_duplicates: str = Form("")):
    runner = get_runner()
    name = file.filename or ""
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        state.store.record_file(fingerprint, name, "error", message="quá lớn")
        raise HTTPException(413, "Ảnh quá lớn (tối đa 40 MB).")
    t0 = time.time()
    try:
        found = runner.run("process", (data, categories()))
    except Exception as exc:
        traceback.print_exc()
        state.store.record_file(fingerprint, name, "error", message=str(exc)[:300])
        code = 504 if type(exc).__name__ == "WorkerTimeout" else 400
        raise HTTPException(code, f"Không xử lý được ảnh: {exc}") from exc
    saved, merged = [], []
    for info in found:
        info["auto_fields"] = json.dumps({f: info.get(f, "") for f in FIELDS + ["category"]}, ensure_ascii=False)
        learned = state.learner.apply(info)
        if learned:
            print(f"Áp dụng điều đã học: {learned} cho {info.get('company')}", flush=True)
        dup_id = state.store.find_duplicate(info, return_id=True)
        if dup_id and skip_duplicates == "1":
            # Bỏ thẻ trùng: chỉ bổ sung ô còn trống của thẻ đã có, không lưu thêm thẻ mới.
            old = state.store.get(dup_id)
            fill = {f: info[f] for f in FIELDS if info.get(f) and not old.get(f)}
            if fill:
                state.store.update(dup_id, fill)
            merged.append(state.store.get(dup_id))
            continue
        if dup_id:
            dup = state.store.get(dup_id)
            info["review"] = ", ".join(x for x in (info.get("review"), f"có thể trùng với {dup.get('name') or dup_id}") if x)
        info["source_file"] = name
        info["batch"] = batch
        saved.append(state.store.add(info))
    state.store.record_file(fingerprint, name, "ok", cards=len(saved) + len(merged))
    return {"cards": saved, "merged": merged, "seconds": round(time.time() - t0, 1)}


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

    card = state.store.get(card_id)
    if not card:
        raise HTTPException(404, "Không tìm thấy danh thiếp")
    runner = get_runner()
    path = state.store.image_path(card_id)
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    img = np.ascontiguousarray(np.rot90(img, k=-1))
    state.store.save_image(card_id, img)
    try:
        info = runner.run("read", (img, categories()), timeout=120)
    except Exception as exc:
        raise HTTPException(400, f"Không đọc lại được: {exc}") from exc
    keep_note = card.get("note")
    state.learner.apply(info)
    card = state.store.replace_analysis(card_id, info)
    if keep_note and not info.get("note"):
        card = state.store.update(card_id, {"note": keep_note})
    return card


@app.post("/api/reanalyze")
def reanalyze():
    """Áp dụng bộ tách thông tin / phân loại mới nhất cho mọi thẻ đã lưu (không cần quét lại ảnh).

    Ô nào bạn đã sửa tay thì giữ nguyên; ô còn nguyên kết quả máy thì thay bằng kết quả mới.
    """
    cats = categories()
    keys = FIELDS + ["category"]
    changed_cards = changed_fields = 0
    for c in state.store.all():
        lines = [t for t in (c.get("raw_text") or "").split("\n") if t.strip()]
        if not lines or c.get("status") == "confirmed":
            continue  # thẻ đã xác nhận là dữ liệu chuẩn, không tự sửa nữa
        new = fields_from_text(lines, c.get("qr_text") or "", cats)
        state.learner.apply(new)
        try:
            auto = json.loads(c.get("auto_fields") or "{}")
        except ValueError:
            auto = {}
        never_edited = (c.get("updated_at") or 0) - (c.get("created_at") or 0) < 1.5
        update = {}
        for k in keys:
            current = c.get(k) or ""
            untouched = (current == (auto.get(k) or "")) if auto else never_edited
            if untouched and new.get(k, "") != current:
                update[k] = new.get(k, "")
        if update:
            changed_cards += 1
            changed_fields += len(update)
        # Ghi lại kết quả máy mới để lần sau vẫn nhận ra ô đã sửa tay.
        update["auto_fields"] = json.dumps({k: new.get(k, "") for k in keys}, ensure_ascii=False)
        # Cảnh báo "cần kiểm tra": tính lại, giữ cảnh báo trùng; thẻ bạn đã xem và xóa cảnh báo thì để trống.
        old_review = c.get("review") or ""
        if old_review or never_edited:
            dup = [x for x in old_review.split(", ") if x.startswith("có thể trùng")]
            update["review"] = ", ".join(x for x in [new["review"], *dup] if x)
        state.store.set_fields_silently(c["id"], update)
    return {"cards": changed_cards, "fields": changed_fields}


class Confirm(BaseModel):
    ids: list[str]
    confirmed: bool = True


@app.post("/api/cards/confirm")
def confirm_cards(body: Confirm):
    """Xác nhận các thẻ đã kiểm tra (dữ liệu chuẩn để xuất vào kho dữ liệu)."""
    state.store.confirm(body.ids, body.confirmed)
    return [state.store.get(i) for i in body.ids]


@app.get("/api/duplicates")
def duplicates():
    groups = state.store.duplicate_groups()
    return {"groups": [[{"id": c["id"], "name": c["name"], "company": c["company"], "email": c["email"],
                         "mobile": c["mobile"], "status": c.get("status", "")} for c in g] for g in groups],
            "extra_cards": sum(len(g) - 1 for g in groups)}


@app.post("/api/duplicates/merge")
def merge_duplicates():
    """Bỏ thẻ trùng: mỗi nhóm giữ 1 thẻ (đã xác nhận / đầy đủ nhất), gộp ô còn trống, xóa thẻ thừa."""
    groups = state.store.duplicate_groups()
    removed = 0
    for g in groups:
        state.store.merge_group(g, FIELDS)
        removed += len(g) - 1
    return {"groups": len(groups), "removed": removed}


@app.get("/api/cards/{card_id}/thumb")
def card_thumb(card_id: str):
    path = state.store.thumb_path(card_id)
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


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
    only_confirmed: bool = False
    incremental: bool = False


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
    if body.format == "dw":
        started = time.time()
        since = float(state.store.get_meta("dw_last_export", "0") or 0) if body.incremental else 0
        picked = [c for c in cards if (not body.only_confirmed or c.get("status") == "confirmed")
                  and (c.get("updated_at") or 0) > since]
        if not picked:
            raise HTTPException(400, "Không có thẻ nào phù hợp để xuất (chưa xác nhận, hoặc không có thay đổi từ lần xuất trước).")
        note = ("Chỉ gồm thẻ đã xác nhận. " if body.only_confirmed else "Gồm cả thẻ chưa xác nhận (cột status). ") + \
               (f"Chỉ gồm thẻ thay đổi sau lần xuất trước ({time.strftime('%d/%m/%Y %H:%M', time.localtime(since))})." if since else "Toàn bộ dữ liệu.")
        path = export_dw(picked, state.store.cards_dir, state.store.exports_dir / f"kho-du-lieu_{stamp}", body.images, note)
        state.store.set_meta("dw_last_export", str(started))
        open_path(path)
        return {"path": str(path), "count": len(picked)}
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
