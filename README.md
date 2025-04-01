# UpdateLan5

Ứng dụng quản lý biểu mẫu và tạo tài liệu

## Cài đặt

### Cài đặt từ file wheel

```bash
pip install dist/updatelan5-1.0.0-py3-none-any.whl
```

### Cài đặt từ mã nguồn

```bash
pip install dist/updatelan5-1.0.0.tar.gz
```

hoặc

```bash
pip install -e .
```

### Cài đặt và chạy với Docker

#### Chuẩn bị môi trường

1. Sao chép file `.env.example` thành `.env` và cấu hình các biến môi trường:

```bash
cp .env.example .env
# Chỉnh sửa file .env với thông tin thực tế
```

#### Sử dụng Dockerfile

```bash
# Build Docker image
docker build -t updatelan5:latest .

# Chạy container
docker run -p 5000:5000 --env-file .env -v "$(pwd)/uploads:/app/uploads" -v "$(pwd)/instance:/app/instance" --name updatelan5-app updatelan5:latest
```

#### Sử dụng Docker Compose (Khuyến nghị)

```bash
# Khởi động ứng dụng và build image
docker-compose up --build

# Chạy ở chế độ nền
docker-compose up -d

# Xem logs
docker-compose logs -f

# Dừng ứng dụng
docker-compose down

# Xóa volumes (cẩn thận, sẽ mất dữ liệu)
docker-compose down -v
```

#### Kiểm tra trạng thái

```bash
# Kiểm tra container đang chạy
docker ps

# Xem logs của container
docker logs updatelan5-app
```

Sau khi khởi động, ứng dụng sẽ chạy tại địa chỉ http://localhost:5000

#### Xử lý lỗi phổ biến khi sử dụng Docker

1. **Lỗi kết nối cơ sở dữ liệu**
   - Đảm bảo thư mục `instance` đã được tạo và có quyền ghi
   - Kiểm tra volume mount trong docker-compose.yml

2. **Lỗi API OpenAI**
   - Kiểm tra OPENAI_API_KEY trong file .env đã được cấu hình đúng
   - Đảm bảo biến môi trường được truyền vào container

3. **Lỗi khi build Docker image**
   - Xóa các container và image cũ: `docker-compose down --rmi all`
   - Xóa cache: `docker builder prune -a`
   - Build lại: `docker-compose up --build`

4. **Lỗi thư mục uploads**
   - Đảm bảo thư mục `uploads` đã được tạo và có quyền ghi
   - Kiểm tra volume mount trong docker-compose.yml

5. **Lỗi cài đặt thư viện Python**
   - Nếu gặp lỗi khi cài đặt các thư viện Python, hãy thử tăng thời gian timeout trong Dockerfile
   - Sử dụng proxy nếu bạn đang ở sau firewall

6. **Lỗi kết nối mạng trong container**
   - Kiểm tra cấu hình mạng của Docker
   - Đảm bảo container có thể truy cập internet

## Sử dụng

Sau khi cài đặt, bạn có thể chạy ứng dụng bằng lệnh:

```bash
updatelan5
```

hoặc chạy trực tiếp từ mã nguồn:

```bash
python app.py
```

## Yêu cầu hệ thống

- Python 3.8 trở lên
- Các thư viện phụ thuộc được liệt kê trong file requirements.txt
- Docker (nếu sử dụng phương pháp cài đặt Docker)