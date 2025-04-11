from flask import request, jsonify
from flask_login import current_user
from utils.ai_matcher import AIFieldMatcher
import logging

logger = logging.getLogger(__name__)

def register_ai_feedback_routes(app):
    """
    Đăng ký các route cho tính năng phản hồi gợi ý AI
    """
    # Initialize components once at startup
    form_history_path = "form_history.json"
    ai_matcher = AIFieldMatcher(form_history_path=form_history_path)
    
    @app.route('/AI_SAVE_FEEDBACK', methods=['POST'])
    def AI_SAVE_FEEDBACK():
        """
        Lưu phản hồi của người dùng về gợi ý AI để cải thiện độ chính xác trong tương lai
        """
        try:
            data = request.get_json()
            
            # Truy xuất thông tin từ request
            field_code = data.get("field_code")
            field_name = data.get("field_name")
            selected_value = data.get("selected_value")
            
            if not all([field_code, selected_value]):
                return jsonify({"error": "Thiếu thông tin bắt buộc"}), 400
            
            # Nếu không có field_name, sử dụng field_code
            if not field_name:
                field_name = field_code
            
            # Lấy user_id từ session nếu người dùng đã đăng nhập
            user_id = current_user.id if current_user.is_authenticated else None
            
            # Cập nhật giá trị vào lịch sử
            ai_matcher.update_field_value(
                field_name=field_name,
                field_value=selected_value,
                user_id=user_id
            )
            
            return jsonify({
                "success": True,
                "message": "Đã lưu phản hồi thành công",
                "field_code": field_code,
                "field_name": field_name,
                "selected_value": selected_value
            })
            
        except Exception as e:
            logger.error(f"Error in AI_SAVE_FEEDBACK: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500