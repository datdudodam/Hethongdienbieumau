import json
import os
import openai
import re
from datetime import datetime
from flask import current_app
import logging
from utils.api_key_manager import get_api_key_manager
logger = logging.getLogger(__name__)

class AIFormSuggester:
    """
    Lớp xử lý gợi ý thông minh dựa trên form_type và lịch sử biểu mẫu
    """
    def __init__(self, form_history_path="form_history.json", api_key=None):
        self.form_history_path = form_history_path
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("Không tìm thấy OPENAI_API_KEY")
        self._client = None
    @property
    def client(self):
        if self._client is None:
            api_key_manager = get_api_key_manager()
            self._client = api_key_manager.get_client()
            
            if self._client is None:
                raise RuntimeError("OpenAI client could not be initialized. Please check your API key configuration.")
        return self._client
    def load_form_history(self):
        """Tải lịch sử biểu mẫu từ file"""
        try:
            if os.path.exists(self.form_history_path):
                with open(self.form_history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Lỗi khi tải lịch sử biểu mẫu: {str(e)}")
            return []
    
    def get_forms_by_type(self, form_type, user_id=None, limit=3):
        """Lấy các biểu mẫu cùng loại từ lịch sử"""
        forms = self.load_form_history()
        
        # Lọc theo form_type và user_id (nếu có)
        filtered_forms = []
        
        # Chuẩn hóa form_type đầu vào
        normalized_form_type = form_type.lower().strip()
        form_type_keywords = normalized_form_type.split()
        
        # Tạo danh sách các từ khóa quan trọng để tìm kiếm
        important_keywords = []
        common_words = ['đơn', 'mẫu', 'biểu', 'form', 'báo', 'cáo', 'giấy', 'tờ']
        
        for keyword in form_type_keywords:
            if len(keyword) > 3 or keyword in common_words:  # Chỉ lấy từ có ý nghĩa
                important_keywords.append(keyword)
        
        if not important_keywords and form_type_keywords:  # Nếu không có từ khóa quan trọng, sử dụng tất cả
            important_keywords = form_type_keywords
        
        for form in forms:
            if 'form_data' not in form:
                continue
                
            form_data = form.get('form_data', {})
            current_form_type = form_data.get('form_type', '')
            
            # Bỏ qua nếu không có form_type
            if not current_form_type:
                continue
            
            # Chuẩn hóa form_type hiện tại
            normalized_current_form_type = current_form_type.lower().strip()
            
            # Kiểm tra form_type - chính xác hoặc tương đối
            is_matching_form = False
            
            # Kiểm tra chính xác
            if normalized_current_form_type == normalized_form_type:
                is_matching_form = True
                match_score = 1.0  # Điểm cao nhất cho khớp chính xác
            else:
                # Kiểm tra tương đối (nếu chứa các từ khóa)
                match_count = 0
                for keyword in important_keywords:
                    if keyword in normalized_current_form_type:
                        match_count += 1
                
                # Tính điểm tương đồng
                if important_keywords:
                    match_score = match_count / len(important_keywords)
                    # Nếu có ít nhất 50% từ khóa khớp
                    if match_score >= 0.5:
                        is_matching_form = True
                else:
                    match_score = 0
            
            if is_matching_form:
                # Kiểm tra user_id nếu được chỉ định
                if user_id is not None:
                    if form.get('user_id') == user_id:
                        form['match_score'] = match_score  # Lưu điểm để sắp xếp
                        filtered_forms.append(form)
                    else:
                        form['match_score'] = match_score  # Lưu điểm để sắp xếp
                        filtered_forms.append(form)
        
        # Sắp xếp theo điểm tương đồng (cao đến thấp) và thời gian (mới đến cũ)
        filtered_forms.sort(key=lambda x: (-x.get('match_score', 0), x.get('timestamp', '')), reverse=True)
        
        # Giới hạn số lượng form trả về
        return filtered_forms[:limit]
    
    def generate_suggestions(self, form_type, current_fields=None, user_id=None):
        """
        Tạo gợi ý cho biểu mẫu mới dựa trên các biểu mẫu cùng loại đã điền trước đó
        """
        if not self.api_key:
            return {"error": "Không tìm thấy API key cho OpenAI"}
            
        # Lấy các biểu mẫu cùng loại
        similar_forms = self.get_forms_by_type(form_type, user_id)
        
        if not similar_forms:
            return {"message": "Không tìm thấy biểu mẫu tương tự"}
        
        # Chuẩn bị dữ liệu để gửi đến OpenAI
        form_data_examples = []
        for form in similar_forms:
            if 'form_data' in form:
                form_data_examples.append(form['form_data'])
        
        # Tạo prompt cho OpenAI
        prompt = self._create_prompt(form_type, form_data_examples, current_fields)
        
        try:
            # Gọi API OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý AI chuyên phân tích và hiểu ngữ cảnh biểu mẫu để cung cấp gợi ý chính xác."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Xử lý kết quả từ OpenAI
            suggestion_text = response.choices[0].message.content
            
            # Chuyển đổi kết quả thành JSON
            try:
                # Tìm phần JSON trong phản hồi
                import re
                json_match = re.search(r'```json\n(.*?)\n```', suggestion_text, re.DOTALL)
                if json_match:
                    suggestion_json = json.loads(json_match.group(1))
                else:
                    # Thử phân tích toàn bộ phản hồi như JSON
                    suggestion_json = json.loads(suggestion_text) if suggestion_text else {}
                
                return {
                    "success": True,
                    "suggestions": suggestion_json,
                    "form_type": form_type,
                    "based_on": len(similar_forms)
                }
            except json.JSONDecodeError:
                # Nếu không phải JSON, trả về dạng văn bản
                return {
                    "success": True,
                    "text_suggestion": suggestion_text,
                    "form_type": form_type,
                    "based_on": len(similar_forms)
                }
                
        except Exception as e:
            logger.error(f"Lỗi khi gọi OpenAI API: {str(e)}")
            return {"error": f"Lỗi khi tạo gợi ý: {str(e)}"}
    
    def _create_prompt(self, form_type, form_examples, current_fields=None):
        """Tạo prompt cho OpenAI dựa trên các biểu mẫu đã có"""
        prompt = f"""
Tôi cần điền một biểu mẫu loại "{form_type}". Dưới đây là {len(form_examples)} biểu mẫu cùng loại đã được điền trước đó:

"""
        
        # Thêm các ví dụ biểu mẫu đã điền
        for i, example in enumerate(form_examples):
            prompt += f"\nBiểu mẫu {i+1}:\n"
            for field, value in example.items():
                if field != "form_id" and field != "document_name" and field != "form_type":
                    prompt += f"- {field}: {value}\n"
        
        # Thêm thông tin về các trường hiện tại (nếu có)
        if current_fields:
            prompt += "\nCác trường đã điền trong biểu mẫu hiện tại:\n"
            for field, value in current_fields.items():
                if value and field != "form_id" and field != "document_name" and field != "form_type":
                    prompt += f"- {field}: {value}\n"
        
        # Yêu cầu gợi ý
        prompt += f"""
Dựa trên các biểu mẫu trên, hãy gợi ý nội dung cho một biểu mẫu "{form_type}" mới.
Trả về kết quả dưới dạng JSON với tên trường là key và giá trị gợi ý là value.
Chỉ trả về các trường có trong ví dụ, không thêm trường mới.
Đảm bảo gợi ý phù hợp với ngữ cảnh và mẫu đã có, nhưng không sao chép hoàn toàn.
"""
        
        return prompt