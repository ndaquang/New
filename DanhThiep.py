"""Điểm khởi chạy app desktop "Danh thiếp" (python DanhThiep.py)."""

import multiprocessing

from app.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
