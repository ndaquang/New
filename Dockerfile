# Dùng cho Hugging Face Spaces (SDK: Docker). Cũng chạy được ở bất kỳ máy nào có Docker.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir --user -r server/requirements.txt

COPY --chown=user . .
# Tải sẵn trọng số VietOCR lúc build để khởi động nhanh hơn (nếu lỗi, server sẽ tự tải lại khi chạy).
RUN python -c "from server.ocr_engine import ensure_weights, DEFAULT_WEIGHTS_PATH, DEFAULT_WEIGHTS_URL; ensure_weights(DEFAULT_WEIGHTS_PATH, DEFAULT_WEIGHTS_URL)" || true

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
