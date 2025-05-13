# Script PowerShell để build và chạy Docker image

# Kiểm tra Docker đã được cài đặt chưa
try {
    docker --version
    Write-Host "Docker đã được cài đặt. Tiếp tục quá trình build..."
} catch {
    Write-Host "Lỗi: Docker chưa được cài đặt hoặc không chạy. Vui lòng cài đặt Docker Desktop và thử lại." -ForegroundColor Red
    exit 1
}

Write-Host "\nBắt đầu build Docker image..." -ForegroundColor Cyan
Write-Host "-----------------------------------"

# Build Docker image với tag và thời gian
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$imageName = "sys_55003"
$imageTag = "latest"
$imageFullName = "${imageName}:${imageTag}"

try {
    # Build Docker image
    docker build -t $imageFullName .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Lỗi: Quá trình build Docker image thất bại." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "\nBuild Docker image thành công!" -ForegroundColor Green
    Write-Host "-----------------------------------"
    
    # Hiển thị kích thước image
    Write-Host "\nKiểm tra kích thước image..." -ForegroundColor Cyan
    docker images $imageFullName --format "{{.Repository}}:{{.Tag}} - {{.Size}}"
    
    # Hướng dẫn chạy ứng dụng
    Write-Host "\nĐể chạy ứng dụng, sử dụng một trong các lệnh sau:" -ForegroundColor Yellow
    Write-Host "1. Sử dụng docker-compose (khuyến nghị):" -ForegroundColor White
    Write-Host "   docker-compose up -d" -ForegroundColor Cyan
    Write-Host "\n2. Hoặc sử dụng docker run:" -ForegroundColor White
    Write-Host "   docker run -p 55003:55003 $imageFullName" -ForegroundColor Cyan
    
    Write-Host "\nỨng dụng sẽ chạy tại địa chỉ: http://localhost:55003" -ForegroundColor Green
} catch {
    Write-Host "Lỗi không xác định trong quá trình build: $_" -ForegroundColor Red
    exit 1
}