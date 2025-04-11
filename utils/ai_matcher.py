from utils.field_matcher import EnhancedFieldMatcher
from openai import OpenAI
from config.config import OPENAI_API_KEY
import re
from typing import Dict, List, Any, Optional

client = OpenAI(api_key=OPENAI_API_KEY)

class AIFieldMatcher:
    def __init__(self, form_history_path: str = "form_history.json"):
        self.field_matcher = EnhancedFieldMatcher(form_history_path=form_history_path)
        self.form_history_path = form_history_path
    
    def extract_context_from_form_text(self, form_text: str) -> str:
        """Trích xuất ngữ cảnh từ nội dung biểu mẫu"""
        prompt = (
            "Đây là nội dung một biểu mẫu do người dùng cung cấp:\n\n"
            f"{form_text}\n\n"
            "Hãy phân tích biểu mẫu này và cung cấp thông tin sau:\n"
            "1. Mục đích chính của biểu mẫu này là gì?\n"
            "2. Đối tượng sử dụng biểu mẫu này là ai?\n"
            "3. Các trường thông tin chính trong biểu mẫu gồm những gì?\n"
            "4. Ngữ cảnh sử dụng của biểu mẫu (ví dụ: hành chính, pháp lý, kinh doanh, giáo dục, y tế, v.v.)\n"
            "5. Các giá trị thường được điền vào biểu mẫu này có đặc điểm gì?\n\n"
            "Hãy tổng hợp thành một đoạn văn ngắn gọn, súc tích để hệ thống gợi ý AI hiểu đúng ngữ cảnh và mục đích của biểu mẫu."
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Bạn là trợ lý AI chuyên phân tích và hiểu ngữ cảnh biểu mẫu để cung cấp gợi ý chính xác."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )

        if response and response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        return ""
    
    def find_similar_field(self, field_code: str) -> str:
        """Tìm tên trường tương tự dựa trên field_code"""
        # Sử dụng _find_similar_fields từ EnhancedFieldMatcher
        similar_fields = self.field_matcher._find_similar_fields(field_code)
        if similar_fields:
            # Trả về trường tương tự nhất
            return similar_fields[0][0]
        return field_code
    
    def get_field_suggestions(self, field_name: str, user_id: Optional[int] = None, limit: int = 5) -> List[str]:
        """Lấy gợi ý giá trị cho trường dựa trên lịch sử"""
        # Sử dụng get_suggested_values từ EnhancedFieldMatcher
        return self.field_matcher.get_suggested_values(field_name, limit=limit, user_id=str(user_id) if user_id else None)
    
    def call_gpt_for_suggestions(self, field_name: str, historical_values: List[str], context: str = None, recent_values: List[str] = None):
        """Gọi GPT để lấy gợi ý thông minh"""
        try:
            prompt = (
                f"Bạn là một hệ thống gợi ý biểu mẫu tự động, thông minh và thân thiện.\n"
                f"Trường cần gợi ý: '{field_name}'.\n"
            )
            
            # Thêm thông tin về lịch sử người dùng
            if historical_values:
                if len(historical_values) > 10:
                    prompt += f"Lịch sử người dùng từng nhập (top 10): {', '.join(historical_values[:10])}.\n"
                else:
                    prompt += f"Lịch sử người dùng từng nhập: {', '.join(historical_values)}.\n"
            
            # Nhấn mạnh các giá trị gần đây
            if recent_values:
                prompt += f"Gần đây người dùng hay chọn (theo thứ tự mới nhất): {', '.join(recent_values)}.\n"
                prompt += f"Hãy ưu tiên các giá trị gần đây nhất khi đưa ra gợi ý.\n"
            
            # Thêm ngữ cảnh biểu mẫu
            if context:
                prompt += f"Biểu mẫu này thuộc ngữ cảnh: {context}.\n"
                prompt += f"Hãy đảm bảo gợi ý phù hợp với ngữ cảnh biểu mẫu.\n"

            prompt += (
                "Hãy gợi ý 5 giá trị phù hợp nhất cho trường này, cách nhau bằng dấu phẩy.\n"
                "Ngoài ra, hãy chọn ra 1 giá trị mặc định hợp lý nhất để điền sẵn.\n"
                "Trả kết quả theo định dạng: \n"
                "Gợi ý: [giá trị1, giá trị2, ...]\n"
                "Mặc định: giá trị"
            )

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a smart and contextual form assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=200
            )

            content = response.choices[0].message.content

            # Trích xuất danh sách gợi ý và mặc định
            suggestions = []
            default_value = ""

            # Xử lý text
            suggestions_match = re.search(r"Gợi ý:\s*\[(.*?)\]", content, re.DOTALL)
            if suggestions_match:
                suggestions_raw = suggestions_match.group(1)
                suggestions = [s.strip() for s in suggestions_raw.split(",") if s.strip()]

            default_match = re.search(r"Mặc định:\s*(.+)", content)
            if default_match:
                default_value = default_match.group(1).strip()

            return {
                "suggestions": suggestions[:5],
                "default": default_value
            }

        except Exception as e:
            print(f"Lỗi khi gọi GPT: {e}")
            return {"suggestions": [], "default": ""}
    
    def generate_personalized_suggestions(self, field_code: str, user_id: Optional[int] = None, context: str = None) -> Dict[str, Any]:
        """Tạo gợi ý cá nhân hóa cho trường dựa trên field_code"""
        # Tìm tên trường tương tự dựa trên field_code
        field_name = self.find_similar_field(field_code)
        
        # Lấy gợi ý từ lịch sử
        historical_suggestions = self.get_field_suggestions(field_name, user_id=user_id)
        
        # Lấy gợi ý từ GPT
        gpt_suggestions = self.call_gpt_for_suggestions(
            field_name=field_name,
            historical_values=historical_suggestions,
            context=context
        )
        
        # Kết hợp gợi ý
        combined_suggestions = []
        
        # Ưu tiên gợi ý từ lịch sử
        for val in historical_suggestions:
            if val not in combined_suggestions and len(combined_suggestions) < 3:
                combined_suggestions.append(val)
        
        # Bổ sung gợi ý từ GPT
        for val in gpt_suggestions["suggestions"]:
            if val not in combined_suggestions and len(combined_suggestions) < 5:
                combined_suggestions.append(val)
        
        # Chọn giá trị mặc định
        default_value = gpt_suggestions["default"]
        if not default_value and historical_suggestions:
            default_value = historical_suggestions[0]
        
        return {
            "suggestions": combined_suggestions,
            "default": default_value,
            "confidence": 0.9,
            "field_name": field_name,
            "field_code": field_code
        }
    
    def update_field_value(self, field_name: str, field_value: str, user_id: Optional[int] = None):
        """Cập nhật giá trị trường vào lịch sử"""
        # Sử dụng update_field_value từ EnhancedFieldMatcher
        self.field_matcher.update_field_value(
            field_name=field_name, 
            field_value=field_value, 
            user_id=str(user_id) if user_id else None
        )