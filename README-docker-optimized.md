# Hướng dẫn sử dụng Docker cho UpdateLan5

## Giới thiệu

Tài liệu này hướng dẫn cách build và chạy ứng dụng UpdateLan5 sử dụng Docker đã được tối ưu hóa. Phiên bản Docker này đã được cải tiến để giảm thời gian build và kích thước image.

## Yêu cầu hệ thống

- Docker Desktop (Windows/Mac) hoặc Docker Engine (Linux)
- Docker Compose

## Cách sử dụng

### Phương pháp 1: Sử dụng script tự động

1. Chạy file `build-and-run.bat` (Windows) để tự động build và chạy container:
   ```
   build-and-run.bat
   ```

2. Truy cập ứng dụng tại địa chỉ: http://localhost:5000

### Phương pháp 2: Sử dụng lệnh Docker Compose

1. Build Docker image:
   ```
   docker-compose build --no-cache
   ```

2. Chạy container:
   ```
   docker-compose up -d
   ```

3. Xem logs:
   ```
   docker-compose logs -f
   ```

4. Truy cập ứng dụng tại địa chỉ: http://localhost:5000

## Cải tiến đã thực hiện

1. **Multi-stage build**: Sử dụng hai giai đoạn build để giảm kích thước image cuối cùng.
   - Stage 1: Cài đặt dependencies và build ứng dụng
   - Stage 2: Chỉ chứa những gì cần thiết để chạy ứng dụng

2. **Tối ưu hóa cài đặt dependencies**:
   - Tăng timeout và số lần retry khi cài đặt packages
   - Chỉ cài đặt các gói hệ thống cần thiết

3. **Cải thiện cách tải dữ liệu NLTK**:
   - Tải dữ liệu NLTK trong giai đoạn build
   - Sao chép dữ liệu đã tải vào image cuối cùng

4. **Sắp xếp lại các layer**:
   - Sao chép requirements.txt trước để tận dụng cache
   - Sao chép mã nguồn sau cùng để tránh phải rebuild khi mã nguồn thay đổi

## Xử lý lỗi thường gặp

### 1. Lỗi về NLTK data

Nếu gặp lỗi liên quan đến NLTK data, bạn có thể thử các cách sau:

```bash
# Truy cập vào container
docker exec -it updatelan5-app bash

# Kiểm tra thư mục NLTK data
ls -la /usr/share/nltk_data

# Tải lại các resource NLTK
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

### 2. Lỗi về quyền truy cập file

Nếu gặp lỗi về quyền truy cập file, bạn có thể thử:

```bash
# Truy cập vào container với quyền root
docker exec -it --user root updatelan5-app bash

# Cấp quyền cho các thư mục
chmod -R 755 /app/uploads /app/instance /app/flask_session
chown -R appuser:appuser /app/uploads /app/instance /app/flask_session
```

### 3. Lỗi kết nối cơ sở dữ liệu

Nếu gặp lỗi kết nối cơ sở dữ liệu, hãy kiểm tra volume mount trong docker-compose.yml và đảm bảo thư mục instance được mount đúng cách.

## Dừng và xóa container

```bash
# Dừng container
docker-compose down

# Xóa container và volume
docker-compose down -v
```