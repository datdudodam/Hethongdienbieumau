from flask import request, jsonify, current_app, session
from flask_login import current_user
from utils.ai_form_suggester import AIFormSuggester
from utils.document_utils import get_doc_path, extract_all_fields
from models.data_model import load_form_history
import logging
import os

logger = logging.getLogger(__name__)

def register_goiy_openai_routes(app):
    """
    Đăng ký các route cho tính năng gợi ý thông minh dựa trên OpenAI
    """
    
    @app.route('/api/smart-suggestions', methods=['POST'])
    def get_smart_suggestions():
        """
        API lấy gợi ý thông minh dựa trên form_type và lịch sử biểu mẫu
        """
        try:
            data = request.get_json()
            
            # Lấy form_type từ request
            form_type = data.get('form_type')
            if not form_type:
                return jsonify({"error": "Thiếu thông tin form_type"}), 400
            
            # Lấy các trường đã điền (nếu có)
            current_fields = data.get('current_fields', {})
            
            # Lấy API key từ config hoặc environment
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                api_key = app.config.get("OPENAI_API_KEY")
            
            # Khởi tạo AI suggester
            suggester = AIFormSuggester(api_key=api_key)
            
            # Lấy user_id nếu đã đăng nhập
            user_id = current_user.id if current_user.is_authenticated else None
            
            # Tạo gợi ý
            result = suggester.generate_suggestions(
                form_type=form_type,
                current_fields=current_fields,
                user_id=user_id
            )
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo gợi ý thông minh: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/form-types', methods=['GET'])
    def get_form_types():
        """
        API lấy danh sách các loại biểu mẫu có trong hệ thống
        """
        try:
            # Lấy tất cả biểu mẫu từ lịch sử
            forms = load_form_history()
            
            # Lấy danh sách các form_type duy nhất
            form_types = set()
            for form in forms:
                if 'form_data' in form and 'form_type' in form['form_data']:
                    form_types.add(form['form_data']['form_type'])
            
            # Đếm số lượng biểu mẫu cho mỗi loại
            form_type_counts = {}
            for form_type in form_types:
                count = 0
                for form in forms:
                    if 'form_data' in form and form['form_data'].get('form_type') == form_type:
                        count += 1
                form_type_counts[form_type] = count
            
            return jsonify({
                "form_types": list(form_types),
                "counts": form_type_counts
            })
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách loại biểu mẫu: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/AI_FILL', methods=['POST'])
    def AI_FILL():
        """
        API tự động điền biểu mẫu dựa trên form_type
        """
        try:
            data = request.get_json()
            
            # Lấy form_type từ request
            form_type = data.get('form_data', {}).get('form_type') or data.get('form_type')
            
            # Nếu không có form_type trong request, thử lấy từ tài liệu hiện tại
            if not form_type:
                doc_path = get_doc_path()
                if doc_path:
                    from utils.form_type_detector import FormTypeDetector
                    detector = FormTypeDetector()
                    form_type = detector.detect_form_type(doc_path)
                
            if not form_type:
                return jsonify({"error": "Không thể xác định loại biểu mẫu"}), 400
            
            # Kiểm tra xem form_type có tồn tại trong form_history.json không
            from models.data_model import load_form_history
            form_history = load_form_history()
            form_types_in_history = set()
            for form in form_history:
                if 'form_data' in form and 'form_type' in form['form_data']:
                    form_types_in_history.add(form['form_data']['form_type'])
            
            # Nếu form_type không tồn tại chính xác, thử tìm kiếm tương đối
            if form_type not in form_types_in_history:
                # Tìm form_type tương tự nhất
                best_match = None
                best_match_score = 0
                form_type_keywords = form_type.lower().split()
                
                for history_form_type in form_types_in_history:
                    match_count = 0
                    for keyword in form_type_keywords:
                        if keyword in history_form_type.lower():
                            match_count += 1
                
                # Tính điểm tương đồng
                if form_type_keywords:
                    match_score = match_count / len(form_type_keywords)
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match = history_form_type
                
                # Nếu tìm thấy form_type tương tự với điểm > 0.3, sử dụng nó
                if best_match and best_match_score > 0.3:
                    logger.info(f"Đã tìm thấy form_type tương tự: {best_match} (điểm: {best_match_score})")
                    form_type = best_match
            
            # Lấy API key từ config hoặc environment
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                api_key = app.config.get("OPENAI_API_KEY")
            
            # Khởi tạo AI suggester
            suggester = AIFormSuggester(api_key=api_key)
            
            # Lấy user_id nếu đã đăng nhập
            user_id = current_user.id if current_user.is_authenticated else None
            
            # Lấy các trường đã điền (nếu có)
            current_fields = data.get('current_fields', {})
            
            # Tạo gợi ý
            result = suggester.generate_suggestions(
                form_type=form_type,
                current_fields=current_fields,
                user_id=user_id
            )
            
            # Lấy danh sách các trường trong biểu mẫu hiện tại
            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "Không tìm thấy tài liệu"}), 400
                
            fields = extract_all_fields(doc_path)
            
            # Ánh xạ gợi ý vào các trường
            field_suggestions = {}
            
            if 'suggestions' in result and isinstance(result['suggestions'], dict):
                suggestions = result['suggestions']
                
                # Tạo một từ điển ánh xạ tên trường với mã trường
                field_name_to_code = {}
                for field in fields:
                    field_name = field.get('field_name')
            
                    field_code = field.get('field_code')
                   
                    if field_name and field_code:
                        # Chuẩn hóa tên trường để so sánh tốt hơn
                        normalized_name = field_name.lower().strip()
                        field_name_to_code[normalized_name] = field_code
                        # Thêm cả tên gốc để đảm bảo tương thích ngược
                        field_name_to_code[field_name] = field_code
                
                # Ánh xạ gợi ý vào các trường dựa trên tên trường
                for field_name, value in suggestions.items():
                    # Chuẩn hóa tên trường từ gợi ý
                    normalized_suggestion_name = field_name.lower().strip()
                    
                    # Thử tìm trực tiếp
                    if normalized_suggestion_name in field_name_to_code:
                        field_suggestions[field_name_to_code[normalized_suggestion_name]] = value
                    elif field_name in field_name_to_code:
                        field_suggestions[field_name_to_code[field_name]] = value
                    else:
                        # Tìm kiếm tương đối nếu không có kết quả chính xác
                        best_match = None
                        best_match_score = 0
                        
                        for doc_field_name in field_name_to_code.keys():
                            # Kiểm tra nếu một chuỗi là substring của chuỗi kia
                            if normalized_suggestion_name in doc_field_name.lower() or doc_field_name.lower() in normalized_suggestion_name:
                                # Tính điểm tương đồng dựa trên độ dài chuỗi chung
                                common_length = min(len(normalized_suggestion_name), len(doc_field_name.lower()))
                                max_length = max(len(normalized_suggestion_name), len(doc_field_name.lower()))
                                match_score = common_length / max_length if max_length > 0 else 0
                                
                                if match_score > best_match_score:
                                    best_match_score = match_score
                                    best_match = doc_field_name
                        
                        # Nếu tìm thấy trường tương tự với điểm > 0.5, sử dụng nó
                        if best_match and best_match_score > 0.5:
                            field_suggestions[field_name_to_code[best_match]] = value
                return jsonify({
                    "success": True,
                    "fields": field_suggestions,
                    "form_type": form_type,
                    "based_on": result.get('based_on', 0)
                })
            
        except Exception as e:
            logger.error(f"Lỗi khi tự động điền biểu mẫu: {str(e)}")
            return jsonify({"error": str(e)}), 500