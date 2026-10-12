"""Server cho ứng dụng quét danh thiếp.

- Phục vụ giao diện web (thư mục ../web) để mở trên iPhone.
- POST /api/ocr: nhận ảnh, trả về các dòng chữ do VietOCR nhận dạng.

Server không lưu ảnh hay dữ liệu danh thiếp nào; mọi dữ liệu nằm trên iPhone.
"""

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
APP_TOKEN = os.environ.get("APP_TOKEN", "")

engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    if os.environ.get("OCR_DISABLED") != "1":
        from server.ocr_engine import CardOCR

        engine = CardOCR()
    yield


app = FastAPI(title="Danh thiếp OCR", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["X-App-Token"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "ocr": engine is not None, "token_required": bool(APP_TOKEN)}


@app.post("/api/ocr")
def ocr(file: UploadFile = File(...), x_app_token: str = Header(default="")):
    if APP_TOKEN and not secrets.compare_digest(x_app_token, APP_TOKEN):
        raise HTTPException(status_code=401, detail="Sai mã truy cập (APP_TOKEN).")
    if engine is None:
        raise HTTPException(status_code=503, detail="Bộ nhận dạng chưa sẵn sàng.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh quá lớn (tối đa 8 MB).")
    try:
        return engine.recognize(data)
    except Exception as exc:  # ảnh hỏng, định dạng lạ...
        raise HTTPException(status_code=400, detail=f"Không đọc được ảnh: {exc}") from exc


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
