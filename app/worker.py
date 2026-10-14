"""Chạy bộ nhận dạng trong một tiến trình riêng để app không bị treo theo.

Nếu một ảnh làm bộ nhận dạng treo (quá `timeout` giây), tiến trình đó bị dừng và khởi động lại
tự động; ảnh lỗi được báo về, các ảnh sau vẫn xử lý tiếp.
"""

import multiprocessing as mp
import queue
import threading
import time
import traceback


def _worker_main(req_q, resp_q, use_vietocr: bool):
    try:
        from .engine.ocr import OCREngine

        engine = OCREngine(use_vietocr=use_vietocr)
        resp_q.put(("ready", engine.recognizer, engine.load_error))
    except BaseException:
        resp_q.put(("fatal", traceback.format_exc()))
        return
    from .engine.pipeline import analyze_card, process_image

    while True:
        job = req_q.get()
        if job is None:
            return
        job_id, kind, payload = job
        try:
            if kind == "process":
                data, cats = payload
                result = process_image(engine, data, cats)
            elif kind == "sleep":  # chỉ dùng để kiểm thử cơ chế chống treo
                time.sleep(payload)
                result = "awake"
            elif kind == "read":  # đọc lại một ảnh thẻ (sau khi xoay)
                img, cats = payload
                result = analyze_card(engine, img, engine.read_lines(img), cats)
            else:
                raise ValueError(kind)
            resp_q.put((job_id, "ok", result))
        except BaseException as exc:
            resp_q.put((job_id, "error", f"{type(exc).__name__}: {exc}"))


class WorkerTimeout(Exception):
    pass


class OCRWorker:
    def __init__(self, use_vietocr: bool = True, timeout: float = 180.0):
        self.use_vietocr = use_vietocr
        self.timeout = timeout
        self.ctx = mp.get_context("spawn")
        self.lock = threading.Lock()
        self.proc = None
        self.recognizer = ""
        self.load_error = ""
        self.error = ""
        self.restarts = 0
        self.ready = threading.Event()
        self._job = 0

    def start(self):
        """Khởi động tiến trình nhận dạng và chờ nạp mô hình xong."""
        self.ready.clear()
        self.req_q = self.ctx.Queue()
        self.resp_q = self.ctx.Queue()
        self.proc = self.ctx.Process(target=_worker_main, args=(self.req_q, self.resp_q, self.use_vietocr), daemon=True)
        self.proc.start()
        try:
            msg = self.resp_q.get(timeout=600)
        except queue.Empty:
            self.error = "Bộ nhận dạng không khởi động được (quá 10 phút)."
            self._kill()
            self.ready.set()
            return
        if msg[0] == "ready":
            _, self.recognizer, self.load_error = msg
            self.error = ""
        else:
            self.error = msg[1]
        self.ready.set()

    def _kill(self):
        if self.proc is not None and self.proc.is_alive():
            self.proc.terminate()
            self.proc.join(5)
            if self.proc.is_alive():
                self.proc.kill()
        self.proc = None

    def restart(self):
        self._kill()
        self.restarts += 1
        self.start()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.is_alive() and not self.error

    def run(self, kind: str, payload, timeout: float | None = None):
        with self.lock:
            if not self.alive():
                self.restart()
                if not self.alive():
                    raise RuntimeError(self.error or "Bộ nhận dạng không chạy.")
            self._job += 1
            job_id = self._job
            self.req_q.put((job_id, kind, payload))
            deadline = time.time() + (timeout or self.timeout)
            while True:
                left = deadline - time.time()
                try:
                    msg = self.resp_q.get(timeout=max(0.1, min(left, 2.0)))
                except queue.Empty:
                    if not self.proc.is_alive():
                        self.restart()
                        raise RuntimeError("Bộ nhận dạng bị dừng đột ngột khi xử lý ảnh này; đã khởi động lại.")
                    if left <= 0:
                        self.restart()
                        raise WorkerTimeout(f"Xử lý quá {int(timeout or self.timeout)} giây; đã khởi động lại bộ nhận dạng.")
                    continue
                if msg[0] != job_id:
                    continue  # phản hồi muộn của việc cũ
                if msg[1] == "ok":
                    return msg[2]
                raise RuntimeError(msg[2])

    def stop(self):
        try:
            if self.proc is not None and self.proc.is_alive():
                self.req_q.put(None)
                self.proc.join(3)
        finally:
            self._kill()
