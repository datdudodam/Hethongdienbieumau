from openai import OpenAI
import time
from datetime import datetime

# Thêm vào hàm check_openai_api_key
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
        
        # Kiểm tra thông tin về hạn sử dụng (nếu có)
        subscription_info = None
        try:
            # Gọi API để lấy thông tin về subscription (nếu OpenAI API hỗ trợ)
            # Đây là giả định, cần điều chỉnh theo API thực tế của OpenAI
            subscription_response = client.subscriptions.list()
            if hasattr(subscription_response, 'data') and subscription_response.data:
                subscription_info = {
                    "expiration_date": subscription_response.data[0].access_until,
                    "plan": subscription_response.data[0].plan
                }
        except Exception as sub_error:
            # Không thể lấy thông tin subscription, bỏ qua
            pass
        
        return {
            "valid": True,
            "message": "API key hợp lệ và đang hoạt động",
            "details": {
                "response_time_ms": response_time,
                "available_models": available_models,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "subscription_info": subscription_info
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