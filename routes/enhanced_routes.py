from flask import request, jsonify
from flask_login import current_user
from utils.field_matcher import EnhancedFieldMatcher
from utils.document_utils import get_doc_path, load_document, extract_fields
import json

def get_field_name_from_code(fields, field_code: str) -> str:
    """
    Trả về field_name dựa trên field_code từ danh sách fields.
    Nếu không tìm thấy thì trả lại chính field_code.
    """
    for field in fields:
        if field.get('field_code') == field_code:
            return field.get('field_name', field_code)
    return field_code

def register_enhanced_routes(app):
    """
    Đăng ký các route cho tính năng nâng cao
    """

    @app.route('/auto_fill_field', methods=['POST'])
    def auto_fill_field():
        try:
            data = request.get_json()
            field_code = data.get("field_name")

            if not field_code:
                return jsonify({"error": "Field code is required"}), 400

            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400

            text = load_document(doc_path)
            fields = extract_fields(text)

            field_name = get_field_name_from_code(fields, field_code)
            partial_form = data.get('partial_form', {})
            user_id = current_user.id if current_user.is_authenticated else None
            matcher = EnhancedFieldMatcher(form_history_path="form_history.json")

            suggestions = matcher.match_fields(field_name, user_id=user_id)

            if suggestions:
                suggestionn = suggestions.get(field_name, [])
                # Duyệt qua tất cả các gợi ý trong suggestionn
                suggestion_list = [{
                    'matched_field': suggestion.get('matched_field'),
                    'value': suggestion.get('value'),
                    'similarity': suggestion.get('similarity', 0)
                } for suggestion in suggestionn]
                    
                return jsonify({
                    'field_name': field_name,
                    'all_suggestions': suggestion_list  # Trả về tất cả các gợi ý
                })
            else:
                return jsonify({'message': 'No suggestion found'})

        except Exception as e:
            return jsonify({'error': str(e)}), 500


    @app.route('/auto_fill_all_fields', methods=['POST'])
    def auto_fill_all_fields():
        try:
            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400

            text = load_document(doc_path)
            fields = extract_fields(text)

            user_id = current_user.id if current_user.is_authenticated else None
            
            # Sử dụng singleton pattern để tránh khởi tạo lại matcher
            if not hasattr(auto_fill_all_fields, 'matcher'):
                auto_fill_all_fields.matcher = EnhancedFieldMatcher(form_history_path="form_history.json")
            matcher = auto_fill_all_fields.matcher

            filled_fields = {}
            
            # Tối ưu: Xử lý tất cả các trường cùng một lúc
            field_names = [field.get("field_name", field.get("field_code")) for field in fields]
            
            # Sử dụng fast_mode=True để tối ưu hiệu suất
            all_suggestions = {}
            for field_name in field_names:
                suggestions = matcher.match_fields(field_name, user_id=user_id, fast_mode=True)
                if suggestions:
                    all_suggestions.update(suggestions)

            # Áp dụng kết quả vào filled_fields
            for field in fields:
                field_code = field.get("field_code")
                field_name = field.get("field_name", field_code)
                
                value = None
                if field_name in all_suggestions:
                    value = all_suggestions[field_name].get('value')
                
                if value:  # Chỉ thêm các trường có giá trị
                    filled_fields[field_code] = value

            return jsonify({"fields": filled_fields})

        except Exception as e:
            return jsonify({'error': str(e)}), 500

