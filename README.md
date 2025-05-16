# Hệ Thống Nhập Liệu Thông Minh

## Giới thiệu

Hệ thống nhập liệu thông minh hỗ trợ AI, giúp người dùng nhập thông tin một cách thông minh với sự hỗ trợ của AI và gợi ý tự động.

## Yêu cầu hệ thống

- Docker và Docker Compose
- PowerShell (cho Windows) hoặc Terminal (cho Linux/Mac)

## Cài đặt và chạy ứng dụng với Docker

### 1. Chuẩn bị file .env

Đảm bảo bạn đã tạo file `.env` với các biến môi trường cần thiết:

```
# Cấu hình Flask
FLASK_APP=app.py
FLASK_ENV=production

# Cấu hình bảo mật
SECRET_KEY=your_secret_key_here

# Cấu hình OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Cấu hình cơ sở dữ liệu
SQLALCHEMY_DATABASE_URI=sqlite:///database.db

# Cấu hình Google OAuth (nếu sử dụng)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://localhost:55003/login/google/callback
```

### 2. Build Docker image

#### Sử dụng PowerShell script (Windows)

```powershell
.\docker-build.ps1
```

#### Hoặc sử dụng lệnh Docker trực tiếp

```bash
docker build -t sys_55003:latest .
```

### 3. Chạy ứng dụng

#### Sử dụng Docker Compose (khuyến nghị)

```bash
docker-compose up -d
```

#### Hoặc sử dụng Docker run

```bash
docker run -p 55003:55003 --env-file .env --name sys_55003-app sys_55003:latest
```

### 4. Truy cập ứng dụng

Mở trình duyệt và truy cập địa chỉ: [http://localhost:55003](http://localhost:55003)

## Xử lý sự cố

### Kiểm tra logs

```bash
docker logs sys_55003-app
```

### Khởi động lại container

```bash
docker restart sys_55003-app
```

### Dừng và xóa container

```bash
docker stop sys_55003-app
docker rm sys_55003-app
```

## Lưu ý bảo mật

- Không bao giờ commit file `.env` chứa các khóa bí mật vào repository
- Các biến môi trường nhạy cảm nên được truyền vào container thông qua file `.env` hoặc biến môi trường khi chạy container
- Không sử dụng ARG trong Dockerfile để lưu trữ các thông tin nhạy cảm