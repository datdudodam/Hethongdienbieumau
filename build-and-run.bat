@echo off
echo ===== Bat dau qua trinh build va chay Docker container =====

REM Kiem tra Docker da duoc cai dat chua
docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Loi: Docker chua duoc cai dat. Vui long cai dat Docker truoc khi chay script nay.
    exit /b 1
)

echo ===== Dang build Docker image =====
docker-compose build --no-cache

if %errorlevel% neq 0 (
    echo Loi: Khong the build Docker image. Vui long kiem tra log de biet them chi tiet.
    exit /b 1
)

echo ===== Build thanh cong! Dang chay container =====
docker-compose up -d

if %errorlevel% neq 0 (
    echo Loi: Khong the chay Docker container. Vui long kiem tra log de biet them chi tiet.
    exit /b 1
)

echo ===== Container da duoc chay thanh cong! =====
echo Ung dung dang chay tai: http://localhost:5000

echo ===== Hien thi log cua container =====
echo Ban co the nhan Ctrl+C de thoat khoi log ma khong dung container.
docker-compose logs -f