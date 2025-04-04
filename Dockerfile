FROM python:3.9-slim

# Thiết lập biến môi trường không lưu cache Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Tạo người dùng không phải root để chạy ứng dụng
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các gói phụ thuộc hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    wget \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Sao chép requirements.txt trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện phụ thuộc Python với pip retry để tránh lỗi mạng
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --timeout 100 --default-timeout=100 --retries 5 -r requirements.txt

# Cài đặt NLTK data cần thiết cho ứng dụng và đảm bảo quyền truy cập
RUN mkdir -p /usr/share/nltk_data && \
    python -m nltk.downloader -d /usr/share/nltk_data punkt_tab stopwords wordnet && \
    chmod -R 755 /usr/share/nltk_data && \
    chown -R appuser:appuser /usr/share/nltk_data

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Tạo thư mục uploads và instance và cấp quyền cho người dùng appuser
RUN mkdir -p uploads instance && \
    chown -R appuser:appuser /app

# Thiết lập biến môi trường
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False
ENV PYTHONPATH=/app

# Sử dụng biến môi trường từ .env file hoặc giá trị mặc định
# Không đặt giá trị mặc định cho các biến nhạy cảm trong Dockerfile
ARG OPENAI_API_KEY
ENV OPENAI_API_KEY=${OPENAI_API_KEY:-your-api-key-here}
ARG SECRET_KEY
ENV SECRET_KEY=${SECRET_KEY:-your-secret-key-here}

# Thiết lập biến môi trường cơ sở dữ liệu
ENV SQLALCHEMY_DATABASE_URI=sqlite:///database.db

# Mở cổng 5000 để truy cập ứng dụng
EXPOSE 5000

# Chuyển sang người dùng không phải root
USER appuser

# Chạy ứng dụng khi container được khởi động
CMD ["python", "app.py"]