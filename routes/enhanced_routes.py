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

            user_id = current_user.id if current_user.is_authenticated else None
            matcher = EnhancedFieldMatcher(form_history_path="form_history.json")

            suggestions = matcher.get_suggested_values(field_name, user_id=user_id)

            if suggestions:
                return jsonify({
                    "value": suggestions[0],
                    "suggestions": suggestions,
                    "confidence": 0.9,  # Có thể thay đổi theo logic tin cậy
                    "field_name": field_name,
                    "field_code": field_code
                })

            return jsonify({
                "error": "Không tìm thấy giá trị phù hợp",
                "field_name": field_name,
                "field_code": field_code
            }), 404

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
            matcher = EnhancedFieldMatcher(form_history_path="form_history.json")

            filled_fields = {}

            for field in fields:
                field_code = field.get("field_code")
                field_name = field.get("field_name", field_code)

                suggestions = matcher.get_suggested_values(field_name, user_id=user_id)

                filled_fields[field_code] = suggestions[0] if suggestions else None

            return jsonify({"fields": filled_fields})

        except Exception as e:
            return jsonify({'error': str(e)}), 500
