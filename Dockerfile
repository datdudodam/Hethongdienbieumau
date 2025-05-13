# Stage 1: Builder - chỉ dùng để cài đặt và chuẩn bị dependencies
FROM python:3.9.18-slim-bookworm AS builder

# Biến môi trường để tăng hiệu năng và không lưu cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cài các công cụ cần thiết để build Python packages và xóa ngay sau đó
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc build-essential python3-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --timeout 100 --retries 5 -r requirements.txt \
    && pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu\
    && pip install --no-cache-dir gunicorn sentence-transformers \
    && python -c "import nltk; nltk.download(['punkt', 'stopwords', 'wordnet'], download_dir='/usr/share/nltk_data', quiet=True)" \
    && apt-get purge -y gcc build-essential python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Runtime - chỉ chứa những gì cần thiết để chạy app
FROM python:3.9.18-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=False \
    SQLALCHEMY_DATABASE_URI=postgresql://postgres:postgres@db:5432/updatelan5 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tạo user không phải root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Cài gói tối thiểu cho runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Copy các thư viện đã cài đặt từ builder
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/share/nltk_data /usr/share/nltk_data

# Sao chép mã nguồn (nên chỉ định rõ thư mục thay vì `.` nếu cần tiết kiệm)
COPY . .


# Tạo các thư mục cần thiết và đảm bảo quyền truy cập
RUN mkdir -p uploads instance flask_session /app/hf_cache \
    && touch instance/database.db \
    && chown -R appuser:appuser /app /usr/share/nltk_data instance/database.db \
    && chmod -R 755 /app \
    && chmod 666 instance/database.db

# Biến môi trường và cấu hình mô hình
# Sử dụng biến môi trường từ file .env thay vì ARG để tăng tính bảo mật
# Các biến nhạy cảm sẽ được truyền vào container khi chạy thông qua --env-file
# hoặc -e flag thay vì lưu trữ trong image

ENV TRANSFORMERS_CACHE=/app/hf_cache \
    HF_HOME=/app/hf_cache \
    HF_DATASETS_CACHE=/app/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/app/hf_cache

EXPOSE 55003

USER appuser

# Tạo entrypoint script để khởi tạo DB và chạy ứng dụng
COPY --chown=appuser:appuser ./docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
