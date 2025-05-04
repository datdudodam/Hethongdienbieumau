# Stage 1: Builder stage - cài đặt dependencies và build ứng dụng
FROM python:3.9.18-slim AS builder

# Thiết lập biến môi trường không lưu cache Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tạo thư mục làm việc
WORKDIR /app

# Cài đặt các gói phụ thuộc hệ thống cần thiết cho build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Sao chép requirements.txt trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện phụ thuộc Python với các tùy chọn tối ưu
# Sử dụng pip cache và tăng timeout để tránh lỗi mạng
RUN pip install --upgrade pip && \
    pip install --timeout 100 --retries 5 -r requirements.txt && \
    pip install gunicorn

# Tải dữ liệu NLTK cần thiết một cách hiệu quả
RUN mkdir -p /usr/share/nltk_data && \
    python -c "import nltk; nltk.download(['punkt', 'stopwords', 'wordnet'], download_dir='/usr/share/nltk_data', quiet=True)"

# Stage 2: Runtime stage - chỉ chứa những gì cần thiết để chạy ứng dụng
FROM python:3.9.18-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=False \
    SQLALCHEMY_DATABASE_URI=sqlite:///database.db \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tạo user không phải root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Tạo thư mục làm việc
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho runtime (chỉ cài đặt curl cho healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Sao chép các thư viện Python đã cài đặt từ builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Sao chép dữ liệu NLTK đã tải từ builder stage
COPY --from=builder /usr/share/nltk_data /usr/share/nltk_data
RUN chmod -R 755 /usr/share/nltk_data && \
    chown -R appuser:appuser /usr/share/nltk_data

# Sao chép mã nguồn
COPY . .

# Tạo thư mục cần thiết và phân quyền
RUN mkdir -p uploads instance flask_session && \
    mkdir -p /app/hf_cache && \
    chown -R appuser:appuser /app && \
    chmod -R 755 uploads instance flask_session /app/hf_cache

# Biến môi trường bí mật và cấu hình cache
ARG OPENAI_API_KEY
ENV OPENAI_API_KEY=${OPENAI_API_KEY:-your-api-key-here}
ARG SECRET_KEY
ENV SECRET_KEY=${SECRET_KEY:-your-secret-key-here}
# Cấu hình Hugging Face cache để tối ưu hóa việc tải mô hình
ENV TRANSFORMERS_CACHE=/app/hf_cache \
    HF_HOME=/app/hf_cache \
    HF_DATASETS_CACHE=/app/hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/app/hf_cache

# Mở port 55003 để phù hợp với cấu hình trong app.py
EXPOSE 55003

# Chạy app với user không phải root
USER appuser

# Chạy ứng dụng Flask với gunicorn để cải thiện hiệu suất
CMD ["gunicorn", "--bind", "0.0.0.0:55003", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

