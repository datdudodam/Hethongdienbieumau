from flask import request, jsonify, session
from typing import Dict, Any, Optional
from utils.ai_matcher import AIFieldMatcher
import json
from models.data_model import load_db, save_db, load_form_history, save_form_history
import logging
from flask_login import current_user
from utils.document_utils import get_doc_path, load_document, extract_all_fields, extract_fields
logger = logging.getLogger(__name__)

def GOI_Y_AI(app):
    """
    Đăng ký các route cho tính năng gợi ý AI nâng cao
    """
    # Initialize components once at startup
    form_history_path = "form_history.json"
    ai_matcher = AIFieldMatcher(form_history_path=form_history_path)
    
    @app.route('/AI_FILL', methods=['POST'])
    def AI_FILL():
        try:
            data = request.get_json()
            
            # Get required fields from request
            field_code = data.get("field_code") or data.get("field_name")  # Handle both field_code and field_name
            if not field_code:
                return jsonify({"error": "Field code is required"}), 400
            
            # Get current document
            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400
                
            # Extract fields from document
            text = load_document(doc_path)
            fields = extract_all_fields(doc_path)
            
            # Find matching field name - cải thiện cách tìm field_name
            field_name = None
            for field in fields:
                if field.get('field_code') == field_code:
                    field_name = field['field_name']
                    break
                    
            # Nếu không tìm thấy, sử dụng field_code làm field_name
            if not field_name:
                field_name = field_code
            
            # Get form type and user info
            form_type = data.get('form_type') or data.get('form_data', {}).get('form_type')
            user_id = str(current_user.id) if current_user.is_authenticated else "anonymous"
            
            # Lấy thêm dữ liệu đã điền từ form hiện tại để cung cấp ngữ cảnh tốt hơn
            partial_form_data = data.get('partial_form', {}) or data.get('form_data', {})
            
            # Load form history data
            form_history_data = load_form_history()
            
            try:
                # Extract context from form text
                form_context = ai_matcher.extract_context_from_form_text(text)
                
                # Get personalized suggestions
                suggestions_result = ai_matcher.generate_personalized_suggestions(
                    db_data=form_history_data,
                    field_code=field_code,
                    user_id=user_id,
                    context=form_context,
                    form_type=form_type,
                    field_name=field_name 
                )
                
                # Prepare response data
                response_data = {
                    "value": suggestions_result.get("default_value", ""),
                    "suggestions": suggestions_result.get("ai_suggestion", {}).get("suggestions", []),
                    "confidence": 0.95,  # Tăng độ tin cậy
                    "field_name": suggestions_result.get("field_name", field_name),
                    "field_code": field_code,
                    "recent_values": suggestions_result.get("recent_values", []),
                    "reason": suggestions_result.get("reason", "") or suggestions_result.get("ai_suggestion", {}).get("reason", "")
                }
                
                # If no suggestions, try to get from recent values
                if not response_data["suggestions"] and response_data["recent_values"]:
                    response_data["suggestions"] = response_data["recent_values"][:5]
                    response_data["value"] = response_data["recent_values"][0] if response_data["recent_values"] else ""
                
                return jsonify(response_data)
                
            except Exception as inner_e:
                logger.error(f"Error in suggestion generation: {str(inner_e)}", exc_info=True)
                return jsonify({
                    "value": "",
                    "suggestions": [],
                    "confidence": 0.5,
                    "field_name": suggestions_result.get("field_name", field_name),

                    "field_code": field_code
                })

        except Exception as e:
            logger.error(f"Error in AI_FILL endpoint: {str(e)}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/AI_REWRITE', methods=['POST'])
    def AI_REWRITE():
        try:
            data = request.get_json()
            field_code = data.get("field_code")
            user_input = data.get("user_input")
            
            if not all([field_code, user_input]):
                return jsonify({"error": "Field code and user input are required"}), 400
                
            # Get document context if available
            doc_path = get_doc_path()
            form_context = ""
            if doc_path:
                text = load_document(doc_path)
                form_context = ai_matcher.extract_context_from_form_text(text)
            
            # Get field name
            field_name = field_code  # Default to field_code if we can't find the name
            if doc_path:
                fields = extract_fields(text)
                field_info = next((f for f in fields if f['field_code'] == field_code), None)
                if field_info:
                    field_name = field_info['field_name']
            
            # Get improved text
            improved_text = ai_matcher.rewrite_user_input(
                field_name=field_name,
                user_input=user_input,
                context=form_context
            )
            
            return jsonify({
                "original": user_input,
                "improved": improved_text,
                "field_code": field_code,
                "field_name": field_name
            })
            
        except Exception as e:
            logger.error(f"Error in AI_REWRITE: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500
            
    @app.route('/AI_ANALYZE_FORM', methods=['POST'])
    def AI_ANALYZE_FORM():
        """Phân tích biểu mẫu để hiểu ngữ cảnh và đưa ra gợi ý tổng thể"""
        try:
            # Get current document
            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "No document loaded"}), 400
                
            # Extract fields from document
            text = load_document(doc_path)
            fields = extract_all_fields(doc_path)
            
            # Extract context from form text
            form_context = ai_matcher.extract_context_from_form_text(text)
            
            # Lấy thông tin phân tích ngữ cảnh biểu mẫu
            form_analysis = ai_matcher.form_context_analysis.get(hash(text), {})
            
            return jsonify({
                "form_context": form_context,
                "form_type": form_analysis.get("form_type", ""),
                "important_fields": form_analysis.get("important_fields", []),
                "field_relationships": form_analysis.get("field_relationships", {}),
                "user_characteristics": form_analysis.get("user_characteristics", ""),
                "field_count": len(fields)
            })
            
        except Exception as e:
            logger.error(f"Error in AI_ANALYZE_FORM: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500