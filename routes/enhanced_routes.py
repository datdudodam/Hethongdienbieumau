from flask import request, jsonify,session
from flask_login import current_user
from utils.field_matcher import EnhancedFieldMatcher
from utils.document_utils import get_doc_path, load_document, extract_all_fields,extract_fields
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
            
            # Log để debug
            print(f"Received auto_fill_field request with data: {data}")

            if not field_code:
                return jsonify({"error": "Field code is required"}), 400

            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400

            text = load_document(doc_path)
            fields = extract_all_fields(doc_path)

            field_name = get_field_name_from_code(fields, field_code)
            partial_form = data.get('partial_form', {})
            user_id = current_user.id if current_user.is_authenticated else None
            # Sử dụng đường dẫn từ config thay vì hardcode
            from config.config import FORM_HISTORY_PATH
            matcher = EnhancedFieldMatcher(form_history_path=FORM_HISTORY_PATH)

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
            fields = extract_all_fields(doc_path)

            user_id = current_user.id if current_user.is_authenticated else None
            # Sử dụng đường dẫn từ config thay vì hardcode
            from config.config import FORM_HISTORY_PATH
            matcher = EnhancedFieldMatcher(form_history_path=FORM_HISTORY_PATH)

            filled_fields = {}

            for field in fields:
                field_code = field.get("field_code")
                field_name = field.get("field_name", field_code)

                suggestions = matcher.match_fields(field_name, user_id=user_id)

                # 🟢 Chỉ lấy giá trị value
                value = None
                if suggestions and field_name in suggestions:
                    value = suggestions[field_name][0].get('value') if suggestions[field_name] else None

                filled_fields[field_code] = value  # Gán trực tiếp value đơn giản

            return jsonify({"fields": filled_fields})  # ✅ frontend sẽ hiểu được

        except Exception as e:
            return jsonify({'error': str(e)}), 500


    @app.route('/update_field_name', methods=['POST'])
    def update_field_name():
        try:
            data = request.get_json()
            field_code = data.get("field_code")
            new_field_name = data.get("new_field_name")
            
            if not field_code or not new_field_name:
                return jsonify({"error": "Field code and new field name are required"}), 400

            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400

            # Lấy danh sách fields hiện tại
            fields = extract_all_fields(doc_path)
            
            # Tìm và cập nhật field name
            updated = False
            for field in fields:
                if field.get('field_code') == field_code:
                    field['field_name'] = new_field_name
                    updated = True
                    break
            
            if not updated:
                return jsonify({"error": "Field not found"}), 404
                
            # Lưu danh sách fields đã cập nhật vào session
            session['updated_fields'] = fields
            
            return jsonify({
                "success": True,
                "message": "Field name updated successfully",
                "field_code": field_code,
                "new_field_name": new_field_name
            })

        except Exception as e:
            return jsonify({'error': str(e)}), 500