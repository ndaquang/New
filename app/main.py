"""Khởi động app desktop: chạy bộ xử lý trên máy và mở cửa sổ giao diện."""

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_port(port: int, timeout: float = 30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


class _Tee:
    """Ghi đồng thời ra cửa sổ đen và file nhật ký (để tìm nguyên nhân khi app bị treo/lỗi)."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, s):
        for out in (self.stream, self.log):
            try:
                out.write(s)
                out.flush()
            except Exception:
                pass
        return len(s)

    def isatty(self):
        return False

    def __getattr__(self, name):  # encoding, fileno... lấy từ luồng gốc
        return getattr(self.stream, name)

    def flush(self):
        for out in (self.stream, self.log):
            try:
                out.flush()
            except Exception:
                pass


def _setup_log(data_dir: Path) -> Path:
    import faulthandler

    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "nhat-ky.log"
    if path.exists() and path.stat().st_size > 5_000_000:
        path.replace(data_dir / "nhat-ky.cu.log")
    log = open(path, "a", encoding="utf-8", buffering=1)
    log.write(f"\n===== Mở app {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    sys.stdout = _Tee(sys.stdout, log)
    sys.stderr = _Tee(sys.stderr, log)
    faulthandler.enable(file=log)  # nếu app sập, ghi lại vị trí lỗi
    return path


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Danh thiếp - quét và quản lý danh thiếp bằng VietOCR")
    ap.add_argument("--selftest", action="store_true", help="tự kiểm tra bộ nhận dạng rồi thoát")
    ap.add_argument("--browser", action="store_true", help="mở bằng trình duyệt thay vì cửa sổ riêng")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--data", help="thư mục lưu dữ liệu (mặc định Documents/DanhThiep)")
    ap.add_argument("--timeout", type=float, default=180, help="số giây tối đa cho một ảnh trước khi coi là treo")
    args = ap.parse_args(argv)

    if args.selftest:
        from .selftest import run

        sys.exit(run())

    import uvicorn

    from . import server
    from .storage import default_data_dir

    log_path = _setup_log(Path(args.data) if args.data else default_data_dir())
    print(f"Nhật ký hoạt động: {log_path}", flush=True)
    # Bộ nhận dạng chạy ở tiến trình riêng: ảnh nào làm treo quá thời gian thì tự khởi động lại.
    server.init(args.data, use_worker=True, timeout=args.timeout)
    port = args.port or _free_port()
    config = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning")
    srv = uvicorn.Server(config)
    threading.Thread(target=srv.run, daemon=True).start()
    if not _wait_port(port):
        print("Không khởi động được bộ xử lý.", flush=True)
        sys.exit(1)
    url = f"http://127.0.0.1:{port}/"
    print(f"Danh thiếp đang chạy tại {url}", flush=True)
    print(f"Dữ liệu lưu tại: {server.state.store.dir}", flush=True)

    if not args.browser:
        try:
            import webview

            webview.create_window("Danh thiếp", url, width=1360, height=860, min_size=(900, 600))
            webview.start()
            return
        except Exception as exc:
            print("Không mở được cửa sổ riêng, chuyển sang trình duyệt:", exc, flush=True)
    webbrowser.open(url)
    print("Đóng cửa sổ này (hoặc Ctrl+C) để thoát app.", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
