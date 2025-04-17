@echo off
echo ===== Đóng gói và chạy ứng dụng với Docker =====

REM Kiểm tra xem Docker đã được cài đặt chưa
docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [CẢNH BÁO] Docker chưa được cài đặt hoặc không chạy. Vui lòng cài đặt Docker và thử lại.
    exit /b 1
)

REM Kiểm tra file .env
if not exist .env (
    echo [THÔNG BÁO] File .env không tồn tại. Đang tạo từ .env.example...
    copy .env.example .env
    echo [CẢNH BÁO] Vui lòng cập nhật các giá trị trong file .env trước khi tiếp tục.
    exit /b 1
)

REM Tạo các thư mục cần thiết nếu chưa tồn tại
if not exist uploads mkdir uploads
if not exist instance mkdir instance
if not exist flask_session mkdir flask_session

REM Đảm bảo file form_data.json và form_history.json tồn tại
if not exist form_data.json echo {} > form_data.json
if not exist form_history.json echo [] > form_history.json

echo [THÔNG BÁO] Đang đóng gói và chạy ứng dụng với Docker Compose...

REM Dừng container cũ nếu đang chạy
docker-compose down

REM Đóng gói và chạy ứng dụng
docker-compose up --build

echo [THÔNG BÁO] Ứng dụng đã được khởi động. Truy cập http://localhost:5000 để sử dụng.