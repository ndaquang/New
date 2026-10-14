# Cấu hình PyInstaller để đóng gói app thành thư mục chạy được trên Windows (DanhThiep.exe).
# Build: pyinstaller DanhThiep.spec --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("app/static", "app/static"),
    ("app/config", "app/config"),
    ("app/vietocr_config", "app/vietocr_config"),
    ("app/weights", "app/weights"),
]
binaries = []
hiddenimports = collect_submodules("vietocr") + collect_submodules("uvicorn") + ["multipart", "python_multipart"]
for pkg in ("rapidocr_onnxruntime", "webview", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["DanhThiep.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DanhThiep",
    console=True,  # cửa sổ đen hiện thông báo/lỗi; đóng nó là thoát app
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="DanhThiep")
