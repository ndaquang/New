---
title: Danh thiep OCR
emoji: 🪪
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Danh thiếp: app quét danh thiếp cho iPhone bằng VietOCR

Một ứng dụng cá nhân tương tự *ABBYY Business Card Reader*. Bạn chụp danh thiếp, app tự nhận dạng chữ tiếng Việt và tách ra họ tên, chức vụ, công ty, số điện thoại, email, website, địa chỉ. Sau đó bạn kiểm tra lại rồi lưu.

- **Không cần máy Mac, không cần tài khoản Apple Developer.** App là một *web app (PWA)*: mở bằng Safari rồi "Thêm vào Màn hình chính", sau đó dùng như app bình thường.
- **Dữ liệu chỉ nằm trên iPhone của bạn** (bộ nhớ của Safari). Server chỉ đọc chữ trên ảnh rồi trả kết quả, không lưu lại gì.
- **Nhận dạng bằng VietOCR** (rất tốt với tiếng Việt có dấu). Khi server không truy cập được, app tự chuyển sang Tesseract chạy ngay trên iPhone.
- Xuất dữ liệu: **Lưu vào Danh bạ iPhone** (vCard), **xuất Excel (CSV)**, **sao lưu/khôi phục** ra file JSON (lưu vào iCloud Drive).

---

## Cài đặt lần đầu (khoảng 15 phút, chỉ làm một lần)

Bạn sẽ đưa app lên **Hugging Face Spaces**. Dịch vụ này miễn phí, có sẵn địa chỉ `https://...` và chạy được VietOCR.

### Bước 1. Tạo tài khoản Hugging Face
Vào <https://huggingface.co/join> và đăng ký bằng email (miễn phí).

### Bước 2. Tạo Space
1. Vào <https://huggingface.co/new-space>.
2. **Space name**: ví dụ `danh-thiep`.
3. **Select the Space SDK**: chọn **Docker**, rồi chọn **Blank**.
4. **Space hardware**: giữ **CPU basic · Free**.
5. **Public** hay **Private**: chọn **Public**. Với Private thì Safari không mở được nếu chưa đăng nhập. Bạn vẫn bảo vệ được server bằng mã truy cập ở Bước 4.
6. Bấm **Create Space**.

### Bước 3. Tải mã nguồn lên Space
**Cách A (dễ nhất, trên máy tính):**
1. Trên trang GitHub của dự án này, bấm **Code → Download ZIP** rồi giải nén.
2. Trong Space vừa tạo, mở tab **Files**, chọn **Add file → Upload files**.
3. Kéo **toàn bộ nội dung** thư mục đã giải nén vào (gồm `Dockerfile`, `README.md`, thư mục `server/` và `web/`). Các thư mục `.git` và `tests/` không bắt buộc.
4. Bấm **Commit changes to main**.

**Cách B (nếu bạn dùng Git):**
```bash
git remote add space https://huggingface.co/spaces/<tên-bạn>/danh-thiep
git push space HEAD:main
```

Space sẽ tự build trong khoảng 5–10 phút. Trạng thái chuyển sang **Running** là xong.

### Bước 4 (khuyên dùng). Đặt mã truy cập
Mục đích là để người lạ có địa chỉ Space cũng không dùng ké server được.
1. Trong Space, mở **Settings → Variables and secrets → New secret**.
2. **Name**: `APP_TOKEN`. **Value**: một chuỗi bí mật bạn tự nghĩ ra, ví dụ `ngoc-2026-xyz`.
3. Space sẽ tự khởi động lại.

### Bước 5. Cài lên iPhone
1. Mở **Safari** trên iPhone (bắt buộc là Safari).
2. Truy cập `https://<tên-bạn>-danh-thiep.hf.space`. Địa chỉ này nằm ở nút **⋯ → Embed this Space → Direct URL** trong Space.
3. Bấm nút **Chia sẻ** (ô vuông có mũi tên lên), chọn **Thêm vào MH chính** rồi **Thêm**.
4. Mở app **Danh thiếp** vừa xuất hiện trên màn hình chính.
5. Nếu đã đặt `APP_TOKEN` ở Bước 4: vào **⚙︎ Cài đặt**, nhập mã vào ô **Mã truy cập**, rồi bấm **Kiểm tra kết nối server**.

> ⚠️ Luôn mở app từ biểu tượng trên màn hình chính. Dữ liệu trong app tách biệt với tab Safari thường, và iOS sẽ giữ dữ liệu của app ở màn hình chính lâu dài.

---

## Cách dùng

| Việc cần làm | Thao tác |
|---|---|
| Quét danh thiếp | **📷 Chụp danh thiếp** (hoặc **🖼️ Chọn ảnh** từ thư viện). Đặt thẻ trên nền tối, chụp thẳng, đủ sáng. |
| Sửa ô bị nhận sai | Chạm vào ô cần sửa, rồi chạm vào **dòng chữ nhận dạng được** ở cuối trang để điền vào. Bạn cũng có thể gõ tay. |
| Ảnh bị ngược/nghiêng | Bấm **↻ Xoay ảnh**, app sẽ nhận dạng lại. |
| Gọi điện, email, xem bản đồ | Mở danh thiếp rồi chạm vào số điện thoại, email hoặc địa chỉ. |
| Đưa vào Danh bạ iPhone | Mở danh thiếp → **👤 Lưu vào Danh bạ** → **Tạo liên hệ mới**. |
| Xuất ra Excel | **⚙︎ → 📊 Xuất Excel (CSV)** → lưu vào Tệp rồi mở bằng Excel hoặc Numbers. |
| Sao lưu | **⚙︎ → 💾 Tạo bản sao lưu** → **Lưu vào Tệp** (chọn iCloud Drive). Nên làm định kỳ. |
| Chuyển sang iPhone mới | Trên máy mới: **⚙︎ → ♻️ Khôi phục** rồi chọn file sao lưu. |

**Lưu ý về server miễn phí:** Space miễn phí sẽ "ngủ" nếu không ai dùng trong 48 giờ. Lần quét đầu tiên sau đó mất khoảng 1–2 phút để server thức dậy, các lần sau chỉ vài giây. Nếu không muốn chờ, app tự dùng Tesseract trên iPhone. Tesseract kém chính xác hơn với tiếng Việt.

**Về quyền riêng tư:** ảnh danh thiếp được gửi lên server của bạn trên Hugging Face để đọc chữ, rồi bị bỏ đi ngay. Server không lưu ảnh hay kết quả. Danh sách danh thiếp chỉ nằm trên iPhone.

---

## (Tùy chọn) Chạy server trên máy tính Windows của bạn

Cách này dùng khi bạn không muốn gửi ảnh lên Internet. iPhone và máy tính phải dùng chung mạng Wi‑Fi.

```bash
# Cài Python 3.11 từ python.org, rồi mở Command Prompt trong thư mục dự án:
pip install -r server/requirements.txt
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Trên iPhone, mở Safari và truy cập `http://<IP-máy-tính>:8000`. Xem IP bằng lệnh `ipconfig`, dòng IPv4.

Lưu ý: địa chỉ `http://` không có biểu tượng khóa, nên app sẽ không mở được khi không có mạng. Dữ liệu của app gắn với địa chỉ này, nên đổi IP sẽ thành "app mới". Cách tốt nhất vẫn là dùng app trên Hugging Face, rồi vào **⚙︎ → Địa chỉ server VietOCR** điền địa chỉ máy tính khi cần. Muốn vậy, máy tính phải có địa chỉ `https` (ví dụ qua Cloudflare Tunnel).

---

## Cấu trúc mã nguồn (dành cho người muốn tìm hiểu)

```
Dockerfile               Đóng gói server cho Hugging Face Spaces
server/app.py            FastAPI: phục vụ giao diện web + API /api/ocr
server/ocr_engine.py     RapidOCR (tìm vị trí dòng chữ) + VietOCR (đọc chữ tiếng Việt)
server/vietocr_config/   Cấu hình mô hình VietOCR vgg_seq2seq
web/index.html, app.js   Giao diện app trên iPhone
web/parser.js            Tách họ tên / chức vụ / công ty / SĐT / email / địa chỉ; xuất vCard, CSV
web/db.js                Lưu dữ liệu trên iPhone (IndexedDB)
web/sw.js                Cho phép mở app khi không có mạng
tests/parser.test.js     Kiểm thử bộ tách thông tin:  node --test tests/parser.test.js
```

Biến môi trường của server:

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `APP_TOKEN` | Mã truy cập bắt buộc cho `/api/ocr` | (không có) |
| `OCR_THREADS` | Số luồng CPU cho VietOCR | `2` |
| `VIETOCR_WEIGHTS_URL` | Nơi tải trọng số VietOCR | `https://vocr.vn/data/vietocr/vgg_seq2seq.pth` |

## Hướng phát triển thêm
- Tự cắt viền danh thiếp và nắn phẳng ảnh chụp nghiêng.
- Quét cả mặt sau (thường là tiếng Anh).
- Gắn nhãn hoặc nhóm (khách hàng, nhà cung cấp, nhà thầu phụ…).
- Đồng bộ dữ liệu sang Google Sheets.
