from flask import request, jsonify, session
from typing import Dict, Any, Optional
from utils.ai_matcher import AIFieldMatcher
import json
from models.data_model import load_db, save_db, load_form_history, save_form_history
import logging
from flask_login import current_user
from utils.document_utils import get_doc_path, load_document, extract_all_fields,extract_fields
logger = logging.getLogger(__name__)

def GOI_Y_AI(app):
    """
    Đăng ký các route cho tính năng gợi ý AI nâng cao
    """
    # Initialize components once at startup
    form_history_path = "form_history.json"
    ai_matcher = AIFieldMatcher(form_history_path=form_history_path)
    
    # Đảm bảo ai_matcher luôn sử dụng client OpenAI mới nhất
    from utils.api_key_manager import get_api_key_manager
    api_key_manager = get_api_key_manager()
    

    @app.route('/AI_FILL', methods=['POST'])
    def AI_FILL():
        try:
            data = request.get_json()
            
            # Truy xuất field_code từ request
            field_code = data.get("field_name")  # Frontend đang gửi field_code với key là field_name
           
            if not field_code:
                return jsonify({"error": "Field code is required"}), 400
            
            # Lấy document path hiện tại để trích xuất field_name
            from utils.document_utils import get_doc_path, load_document, extract_all_fields
            doc_path = get_doc_path()
            
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400
                
            # Trích xuất tất cả các trường từ tài liệu
            text = load_document(doc_path)
            fields = extract_all_fields(doc_path)
            
            # Tìm field_name tương ứng với field_code
            field_name = None
            for field in fields:
                if field['field_code'] == field_code:
                    field_name = field['field_name']
                    break
            
            if not field_name:
                # Nếu không tìm thấy field_name, sử dụng field_code làm field_name
                field_name = field_code
            
            # Lấy user_id từ session nếu người dùng đã đăng nhập
            from flask_login import current_user
            user_id = current_user.id if current_user.is_authenticated else None
            
            # Tải dữ liệu lịch sử biểu mẫu
            form_history_data = load_form_history()
            
            # Thêm xử lý lỗi và kiểm tra dữ liệu
            try:
                # Trích xuất ngữ cảnh từ nội dung biểu mẫu
                form_context = ai_matcher.extract_context_from_form_text(text)
                
                # Gọi hàm generate_personalized_suggestions từ AIFieldMatcher
                suggestions_result = ai_matcher.generate_personalized_suggestions(
                    db_data=load_form_history(),
                    field_code=field_name,
                    user_id=str(user_id) if user_id is not None else "",
                    context=form_context
                )
                
                # Kiểm tra kết quả trả về
                if suggestions_result is None:
                    suggestions_result = {
                        "suggestions": [], 
                        "default": "",
                        "confidence": 0.5,
                        "field_name": field_name,
                        "field_code": field_code
                    }
                    
                # Đảm bảo suggestions_result có key "suggestions"
                if "suggestions" not in suggestions_result:
                    suggestions_result["suggestions"] = []
                    
                suggestions = suggestions_result["suggestions"]
                
                # Xử lý trường hợp suggestions rỗng
                if not suggestions:
                    return jsonify({
                        "value": "",
                        "suggestions": [],
                        "confidence": 0.5,
                        "field_name": field_name,
                        "field_code": field_code
                    })
                    
                # Lấy giá trị mặc định an toàn
                default_value = suggestions_result.get("default", "")
                if not default_value and suggestions:
                    default_value = suggestions[0]
                    
                return jsonify({
                    "value": default_value,
                    "suggestions": suggestions,
                    "confidence": suggestions_result.get("confidence", 0.9),
                    "field_name": field_name,
                    "field_code": field_code
                })
            except Exception as inner_e:
                logger.error(f"Error in generate_personalized_suggestions: {str(inner_e)}", exc_info=True)
                # Trả về kết quả trống nhưng không gây lỗi 500
                return jsonify({
                    "value": "",
                    "suggestions": [],
                    "confidence": 0.5,
                    "field_name": field_name,
                    "field_code": field_name
                })

            return jsonify({"error": "Không tìm thấy giá trị phù hợp", "field_name": field_name}), 404

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # @app.route('/AI_REWRITE', methods=['POST'])
    # def AI_REWRITE():
    #     try:
    #         data = request.get_json()
    #         field_code = data.get("field_code")
    #         user_input = data.get("user_input")
            
    #         if not all([field_code, user_input]):
    #             return jsonify({"error": "Field code and user input are required"}), 400
                
    #         # Get document context if available
    #         doc_path = get_doc_path()
    #         form_context = ""
    #         if doc_path:
    #             text = load_document(doc_path)
    #             form_context = ai_suggester.extract_context_from_form_text(text)
            
    #         # Get field name
    #         field_name = field_code  # Default to field_code if we can't find the name
    #         if doc_path:
    #             fields = extract_fields(text)
    #             field_info = next((f for f in fields if f['field_code'] == field_code), None)
    #             if field_info:
    #                 field_name = field_info['field_name']
            
    #         # Get improved text
    #         improved_text = ai_suggester.rewrite_user_input(
    #             field_name=field_name,
    #             user_input=user_input,
    #             context=form_context
    #         )
            
    #         return jsonify({
    #             "original": user_input,
    #             "improved": improved_text,
    #             "field_code": field_code,
    #             "field_name": field_name
    #         })
            
    #     except Exception as e:
    #         logger.error(f"Error in AI_REWRITE: {str(e)}", exc_info=True)
    #         return jsonify({'error': str(e)}), 500