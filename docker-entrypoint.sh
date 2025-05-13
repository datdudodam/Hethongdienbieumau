#!/bin/bash
set -e

# Khởi tạo cơ sở dữ liệu nếu cần
python /app/init_db.py

# Tạo tài khoản admin nếu chưa tồn tại
python /app/create_admin.py

# Chạy ứng dụng với Gunicorn
exec gunicorn --bind 0.0.0.0:55003 --workers 4 --timeout 120 --access-logfile - --error-logfile - app:app