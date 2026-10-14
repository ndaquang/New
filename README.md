# Danh thiếp: app desktop quét danh thiếp hàng loạt bằng VietOCR

App cá nhân cho Windows, tương tự *ABBYY Business Card Reader*:

1. **Chọn nhiều ảnh, cả thư mục, hoặc kéo thả** ảnh danh thiếp vào cửa sổ.
2. App **tự cắt từng danh thiếp**: ảnh chụp nghiêng trên bàn, ảnh scan nhiều thẻ cùng lúc, hay ảnh danh thiếp điện tử đều được. Mỗi thẻ được nắn thẳng và **xoay đúng chiều**, kể cả khi bị lộn ngược hay xoay dọc.
3. **Đọc chữ bằng VietOCR** (tiếng Việt có dấu), **đọc cả mã QR** nếu thẻ có.
4. **Tách thông tin**: họ tên, chức vụ, công ty, di động, điện thoại, fax, email, website, địa chỉ và địa chỉ chi nhánh. Mã số thuế được nhận ra và bỏ qua.
5. **Phân loại** theo nhóm (Chủ đầu tư, Nhà thầu, Tư vấn, MEP, Nhà cung cấp, Ngân hàng…). Bạn sửa được danh sách nhóm và từ khóa.
6. Ra **một bảng danh sách** có thể tìm kiếm, lọc, sửa và đổi phân loại hàng loạt. App **cảnh báo** thẻ thiếu thông tin hoặc trùng với thẻ đã có.
7. **Xuất Excel** (kèm ảnh thẻ, có trang tổng hợp theo nhóm) hoặc **vCard** (nhập vào Outlook, Danh bạ điện thoại, Google Contacts).

Mọi xử lý chạy **ngay trên máy tính của bạn**: không cần Internet, không gửi ảnh đi đâu.

---

## Cài đặt: cách 1, tải bản đóng gói sẵn (khuyên dùng, không cần cài Python)

Mỗi lần code được cập nhật, GitHub tự build bản Windows và chạy thử VietOCR trên ảnh mẫu.

1. Vào trang GitHub của repo, mở tab **Actions** rồi chọn **Build Windows app**.
2. Bấm vào lần chạy mới nhất có dấu ✅ xanh.
3. Kéo xuống mục **Artifacts** và tải **DanhThiep-Windows** (khoảng 400–600 MB).
4. Giải nén **2 lần**: lần đầu ra `DanhThiep-Windows.zip`, giải nén tiếp vào một thư mục cố định, ví dụ `C:\DanhThiep`.
5. Bấm đúp **`DanhThiep.exe`**.
   - Nếu Windows báo *"Windows protected your PC"*, bấm **More info**, rồi **Run anyway**. App không có chữ ký số nên Windows cảnh báo như vậy.
   - Lần đầu mất khoảng 20–40 giây để nạp mô hình.
   - Cửa sổ đen đi kèm hiện nhật ký hoạt động. Đóng nó là thoát app.

> Bản tải ở mục Artifacts được giữ 30 ngày. Khi hết hạn, vào **Actions → Build Windows app → Run workflow** để build lại.

## Cài đặt: cách 2, chạy từ mã nguồn

1. Cài **Python 3.11** từ <https://www.python.org/downloads/release/python-3119/>. Khi cài, tick **"Add python.exe to PATH"**.
2. Tải mã nguồn: **Code → Download ZIP** rồi giải nén.
3. Bấm đúp **`Chay DanhThiep.bat`**. Lần đầu app tự cài thư viện và tải mô hình VietOCR, mất khoảng 5–10 phút. Các lần sau mở ngay.

---

## Cách dùng

| Việc | Thao tác |
|---|---|
| Nhập ảnh | **＋ Chọn ảnh** (chọn nhiều ảnh), **📁 Chọn cả thư mục**, hoặc kéo thả vào cửa sổ. Hỗ trợ jpg, png, bmp, webp, tiff. |
| Xem / sửa một thẻ | Bấm vào dòng. Khung bên phải hiện ảnh thẻ và các ô thông tin. Sửa xong bấm ra ngoài ô là **tự lưu**. |
| Điền nhanh từ chữ đã đọc | Bấm vào ô cần điền, rồi bấm dòng chữ ở mục **Chữ đọc được**. |
| Thẻ bị xoay sai | Bấm **↻ Xoay 90° và đọc lại**. |
| Lọc / tìm | Bấm nhóm ở cột trái (hoặc **⚠ Cần kiểm tra**). Ô tìm kiếm gõ không dấu cũng được, tìm được cả theo số điện thoại. |
| Đổi phân loại / xóa hàng loạt | Tick chọn các dòng rồi dùng thanh công cụ phía trên bảng. |
| Xuất Excel | **📊 Xuất Excel**: file được lưu và tự mở. Muốn bỏ ảnh trong file Excel cho nhẹ: **⋯ → bỏ tick "Chèn ảnh thẻ vào Excel"**. |
| Nhập vào Outlook / điện thoại | **👥 Xuất vCard**, rồi mở file `.vcf` bằng Outlook, hoặc gửi sang điện thoại và mở. |
| Sửa nhóm phân loại | **⋯ → Sửa danh sách phân loại…** Mở file bằng Notepad, sửa tên nhóm hoặc từ khóa, lưu lại rồi khởi động lại app. |

**Mẹo chụp/scan để đọc chính xác:**
- Đặt thẻ trên **nền tối hoặc khác màu thẻ**, chụp đủ sáng, không lóa.
- Với máy scan, có thể xếp nhiều thẻ trên mặt kính, **để cách nhau khoảng 1 cm**.
- Ảnh từ điện thoại dùng trực tiếp được, không cần cắt trước.

**Dữ liệu được lưu ở `Documents\DanhThiep`:**
- `danhthiep.db`: toàn bộ danh sách. **Nên sao lưu cả thư mục này định kỳ.**
- `anh-the\`: ảnh từng thẻ đã cắt.
- `xuat-file\`: các file Excel / vCard đã xuất.
- `phan-loai.json`: nhóm phân loại và từ khóa.

---

## Cách hoạt động (dành cho người muốn tìm hiểu)

```
Ảnh ─► tìm viền thẻ (OpenCV: ngưỡng sáng/tối, cạnh, màu) ─► nắn phối cảnh
     └► không thấy viền? gom các cụm chữ (scan nhiều thẻ) hoặc dùng cả ảnh
   ─► xoay đúng chiều (hướng dòng chữ + bộ phân loại góc 0°/180°)
   ─► tìm dòng chữ (RapidOCR/DBNet) ─► đọc chữ (VietOCR vgg_seq2seq) + đọc mã QR
   ─► tách trường (quy tắc cho danh thiếp Việt Nam) ─► phân loại theo từ khóa ─► SQLite
```

```
DanhThiep.py               Điểm khởi chạy (mở cửa sổ app)
app/main.py                Khởi động bộ xử lý nội bộ + cửa sổ (pywebview)
app/server.py              API nội bộ (127.0.0.1): xử lý ảnh, danh sách, xuất file
app/engine/crop.py         Tìm, cắt, nắn thẳng và xoay từng danh thiếp
app/engine/ocr.py          RapidOCR (tìm dòng chữ) + VietOCR (đọc chữ)
app/engine/qr.py           Đọc mã QR (vCard / MECARD / link)
app/engine/parser.py       Tách họ tên, chức vụ, công ty, SĐT, email, địa chỉ…
app/engine/classify.py     Phân loại theo nhóm ngành (app/config/categories.json)
app/storage.py             Lưu trữ SQLite + ảnh thẻ
app/export.py              Xuất Excel (kèm ảnh) và vCard
app/static/                Giao diện
app/samples.py             Ảnh danh thiếp mẫu để tự kiểm tra
tests/                     Kiểm thử:  python -m pytest tests
DanhThiep.spec             Cấu hình đóng gói .exe (PyInstaller)
.github/workflows/         GitHub tự build bản Windows + chạy tự kiểm tra
```

Kiểm tra bộ nhận dạng trên máy: `python DanhThiep.py --selftest`. Mở bằng trình duyệt thay cho cửa sổ riêng: `python DanhThiep.py --browser`.
