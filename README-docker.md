# Hướng dẫn đóng gói và chạy ứng dụng với Docker

## Yêu cầu hệ thống

- Docker Engine (phiên bản 19.03 trở lên)
- Docker Compose (phiên bản 1.27 trở lên)

## Chuẩn bị trước khi đóng gói

1. Đảm bảo bạn đã cấu hình file `.env` với các biến môi trường cần thiết:
   - `SECRET_KEY`: Khóa bí mật cho ứng dụng Flask
   - `OPENAI_API_KEY`: API key của OpenAI (nếu sử dụng tính năng AI)

   Bạn có thể sao chép từ file `.env.example` và điền các giá trị phù hợp:
   ```bash
   cp .env.example .env
   ```

## Đóng gói và chạy ứng dụng

### Cách 1: Sử dụng Docker Compose (Khuyến nghị)

1. Đóng gói và chạy ứng dụng:
   ```bash
   docker-compose up --build
   ```

2. Để chạy ở chế độ nền (detached mode):
   ```bash
   docker-compose up --build -d
   ```

3. Để dừng ứng dụng:
   ```bash
   docker-compose down
   ```

### Cách 2: Sử dụng Docker trực tiếp

1. Đóng gói ứng dụng:
   ```bash
   docker build -t updatelan5:latest .
   ```

2. Chạy ứng dụng:
   ```bash
   docker run -p 5000:5000 --env-file .env -v "$(pwd)/uploads:/app/uploads" -v "$(pwd)/instance:/app/instance" -v "$(pwd)/form_data.json:/app/form_data.json" -v "$(pwd)/form_history.json:/app/form_history.json" -v "$(pwd)/flask_session:/app/flask_session" updatelan5:latest
   ```

## Truy cập ứng dụng

Sau khi container đã chạy thành công, bạn có thể truy cập ứng dụng tại:

```
http://localhost:5000
```

## Xử lý các lỗi thường gặp

### 1. Lỗi về NLTK data

Nếu gặp lỗi liên quan đến NLTK data, bạn có thể thử các cách sau:

- **Kiểm tra logs của container**:
  ```bash
  docker-compose logs web
  ```

- **Truy cập vào container để kiểm tra**:
  ```bash
  docker-compose exec web bash
  ```
  Sau đó kiểm tra thư mục NLTK data:
  ```bash
  ls -la /usr/share/nltk_data
  ```
  Và thử tải lại các resource NLTK:
  ```bash
  python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
  ```

### 2. Lỗi quyền truy cập

Nếu gặp lỗi về quyền truy cập vào các thư mục như uploads, instance, flask_session:

- Đảm bảo các thư mục này tồn tại trên máy host và có quyền ghi.
- Kiểm tra quyền sở hữu của các thư mục này trong container:
  ```bash
  docker-compose exec web ls -la /app
  ```

### 3. Lỗi kết nối cơ sở dữ liệu

Nếu gặp lỗi kết nối đến cơ sở dữ liệu SQLite:

- Kiểm tra xem volume cho thư mục instance đã được mount đúng cách chưa.
- Đảm bảo file database.db có quyền ghi trong container.

### 4. Lỗi biến môi trường

Nếu ứng dụng không nhận được các biến môi trường:

- Kiểm tra file `.env` đã được cấu hình đúng.
- Đảm bảo Docker Compose đã load file `.env` bằng cách kiểm tra logs.

### 5. Lỗi port đã được sử dụng

Nếu port 5000 đã được sử dụng bởi ứng dụng khác:

- Thay đổi port mapping trong file `docker-compose.yml`:
  ```yaml
  ports:
    - "8080:5000"  # Thay đổi 5000 thành 8080 ở bên ngoài
  ```

## Tối ưu hóa Docker image

- **Sử dụng Docker layer caching**: Dockerfile đã được tối ưu để tận dụng layer caching, giúp giảm thời gian build khi chỉ có thay đổi nhỏ trong mã nguồn.
- **Multi-stage builds**: Nếu cần giảm kích thước image, bạn có thể cân nhắc sử dụng multi-stage builds.

## Môi trường production

Khi triển khai trong môi trường production, bạn nên:

1. Sử dụng một web server như Nginx làm reverse proxy trước ứng dụng Flask.
2. Cấu hình HTTPS với chứng chỉ SSL.
3. Đảm bảo các biến môi trường nhạy cảm được bảo vệ đúng cách.
4. Cân nhắc sử dụng Docker Swarm hoặc Kubernetes cho khả năng mở rộng và quản lý container.