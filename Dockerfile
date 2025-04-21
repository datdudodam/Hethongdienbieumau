# Stage 1: Builder stage - cài đặt dependencies và build ứng dụng
FROM python:3.9-slim AS builder

# Thiết lập biến môi trường không lưu cache Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --timeout 100 --retries 5 -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Tải dữ liệu NLTK cần thiết
RUN mkdir -p /usr/share/nltk_data && \
    python -c "import nltk; nltk.download('punkt', download_dir='/usr/share/nltk_data'); nltk.download('stopwords', download_dir='/usr/share/nltk_data'); nltk.download('wordnet', download_dir='/usr/share/nltk_data')"

# Stage 2: Runtime stage - chỉ chứa những gì cần thiết để chạy ứng dụng
FROM python:3.9-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=False \
    SQLALCHEMY_DATABASE_URI=sqlite:///database.db

# Tạo user không phải root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Tạo thư mục làm việc
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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

# Biến môi trường bí mật
ARG OPENAI_API_KEY
ENV OPENAI_API_KEY=${OPENAI_API_KEY:-your-api-key-here}
ARG SECRET_KEY
ENV SECRET_KEY=${SECRET_KEY:-your-secret-key-here}
ENV TRANSFORMERS_CACHE=/app/hf_cache
ENV HF_HOME=/app/hf_cache

# Mở port 5000 để phù hợp với docker-compose.yml
EXPOSE 55003

# Chạy app với user không phải root
USER appuser

# Chạy ứng dụng Flask
CMD ["python", "app.py", "run", "--host=0.0.0.0", "--port=55003"]

