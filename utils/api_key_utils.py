from openai import OpenAI
import time
from datetime import datetime

def check_openai_api_key(api_key):
    """
    Kiểm tra tính hợp lệ của OpenAI API key
    
    Args:
        api_key (str): API key cần kiểm tra
        
    Returns:
        dict: Kết quả kiểm tra bao gồm trạng thái, thông báo và thông tin chi tiết
    """
    if not api_key or api_key.strip() == "" or api_key == "your-api-key-here":
        return {
            "valid": False,
            "message": "API key không được cung cấp hoặc không hợp lệ",
            "details": None
        }
    
    try:
        # Tạo client OpenAI với API key cần kiểm tra
        client = OpenAI(api_key=api_key)
        
        # Gọi API đơn giản để kiểm tra key
        start_time = time.time()
        response = client.models.list()
        end_time = time.time()
        
        # Tính thời gian phản hồi
        response_time = round((end_time - start_time) * 1000)  # Đổi sang milliseconds
        
        # Lấy danh sách models để hiển thị
        available_models = [model.id for model in response.data[:5]]  # Chỉ lấy 5 model đầu tiên
        
        return {
            "valid": True,
            "message": "API key hợp lệ và đang hoạt động",
            "details": {
                "response_time_ms": response_time,
                "available_models": available_models,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        }
    except Exception as e:
        error_message = str(e)
        
        # Phân tích lỗi để đưa ra thông báo phù hợp
        if "Incorrect API key" in error_message or "Invalid API key" in error_message:
            message = "API key không hợp lệ"
        elif "exceeded your current quota" in error_message:
            message = "API key đã vượt quá hạn mức sử dụng"
        elif "deactivated" in error_message:
            message = "API key đã bị vô hiệu hóa"
        elif "expired" in error_message:
            message = "API key đã hết hạn"
        else:
            message = f"Lỗi khi kiểm tra API key: {error_message}"
        
        return {
            "valid": False,
            "message": message,
            "details": {
                "error": error_message,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        }