from flask import request, jsonify, session
from typing import Dict, Any
from utils.field_matcher import EnhancedFieldMatcher
import json
from models.data_model import load_db, save_db, load_form_history, save_form_history
from utils.ai_utils import generate_personalized_suggestions,extract_context_from_form_text
def GOI_Y_AI(app):
    """
    Đăng ký các route cho tính năng nâng cao
    """
   

    @app.route('/AI_FILL', methods=['POST'])
    def AI_FILL():
        try:
            data = request.get_json()
            # Truy xuất field_code từ request
            field_code = data.get("field_name")  # Frontend đang gửi field_code với key là field_name
            
            if not field_code:
                return jsonify({"error": "Field code is required"}), 400
            
            # Lấy document path hiện tại để trích xuất field_name
            from utils.document_utils import get_doc_path, load_document, extract_fields
            doc_path = get_doc_path()
            
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400
                
            # Trích xuất tất cả các trường từ tài liệu
            text = load_document(doc_path)
            fields = extract_fields(text)
            
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
            
            # Sử dụng file form_history.json thực tế
            form_history_path = "form_history.json"
            
            # Tạo đối tượng EnhancedFieldMatcher với dữ liệu lịch sử thực tế
            matcher = EnhancedFieldMatcher(form_history_path=form_history_path)
            
            # Lấy các gợi ý dựa trên field_name và user_id
            suggestions = matcher.generate_personalized_suggestions(field_name, user_id, context=extract_context_from_form_text(text))

            if suggestions:
                return jsonify({
                    "value": suggestions,
                    "suggestions": suggestions,
                    "confidence": 0.9,
                    "field_name": field_name,
                    "field_code": field_code
                })

            return jsonify({"error": "Không tìm thấy giá trị phù hợp", "field_name": field_name}), 404

        except Exception as e:
            return jsonify({'error': str(e)}), 500