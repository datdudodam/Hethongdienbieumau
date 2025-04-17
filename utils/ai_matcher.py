from openai import OpenAI
from config.config import OPENAI_API_KEY, FORM_HISTORY_PATH
from collections import defaultdict, Counter
import re
import json
import os
from typing import Dict, List, Optional, Union, Any
from .field_matcher import EnhancedFieldMatcher

client = OpenAI(api_key=OPENAI_API_KEY)

class AIFieldMatcher:
    def __init__(self, form_history_path: str = FORM_HISTORY_PATH):
        self.field_matcher = EnhancedFieldMatcher(form_history_path)
        self.context_cache = {}
        self.suggestion_cache = {}
        
    def extract_context_from_form_text(self, form_text: str) -> str:
        """Extract context from form text with caching"""
        cache_key = hash(form_text)
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
            
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

        context = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message.content else ""
        self.context_cache[cache_key] = context
        return context
    
    def call_gpt_for_suggestions(self, field_name: str, historical_values: List[str], 
                               context: Optional[str] = None, recent_values: Optional[List[str]] = None,
                               frequency_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Get AI suggestions with caching"""
        cache_key = f"{field_name}_{hash(str(historical_values))}_{hash(context) if context else ''}"
        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key]
            
        try:
            prompt = (
                f"Bạn là một hệ thống gợi ý biểu mẫu tự động, thông minh và thân thiện.\n"
                f"Trường cần gợi ý: '{field_name}'.\n"
            )
            
            # Add historical values
            if historical_values:
                if len(historical_values) > 10:
                    prompt += f"Lịch sử người dùng từng nhập (top 10): {', '.join(historical_values[:10])}.\n"
                else:
                    prompt += f"Lịch sử người dùng từng nhập: {', '.join(historical_values)}.\n"
            
            # Add recent values with higher priority
            if recent_values:
                prompt += f"Gần đây người dùng hay chọn (theo thứ tự mới nhất): {', '.join(recent_values)}.\n"
                prompt += f"Hãy ưu tiên các giá trị gần đây nhất khi đưa ra gợi ý.\n"
            
            # Add frequency data if available
            if frequency_data:
                prompt += f"Tần suất sử dụng: {frequency_data}\n"
            
            # Add form context
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

            # Extract suggestions and default value
            suggestions = []
            default_value = ""

            suggestions_match = re.search(r"Gợi ý:\s*\[(.*?)\]", content, re.DOTALL)
            if suggestions_match:
                suggestions_raw = suggestions_match.group(1)
                suggestions = [s.strip() for s in suggestions_raw.split(",") if s.strip()]

            default_match = re.search(r"Mặc định:\s*(.+)", content)
            if default_match:
                default_value = default_match.group(1).strip()

            result = {
                "suggestions": suggestions[:5],
                "default": default_value
            }
            
            self.suggestion_cache[cache_key] = result
            return result

        except Exception as e:
            print(f"Lỗi khi gọi GPT: {e}")
            return {"suggestions": [], "default": ""}
    
    def rewrite_user_input_for_suggestion(self, field_name: str, user_input: str, 
                                       context: Optional[str] = None) -> str:
        """Rewrite user input to be more professional"""
        try:
            prompt = (
                f"Người dùng đã từng nhập cho trường '{field_name}': \"{user_input}\"\n"
            )
            if context:
                prompt += f"Ngữ cảnh: {context}\n"
            prompt += (
                "Hãy viết lại nội dung trên theo cách chuyên nghiệp, rõ ràng, thuyết phục và tự nhiên hơn.\n"
                "Chỉ trả về nội dung đã viết lại, không thêm gì khác."
            )

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Bạn là một trợ lý AI giúp viết lại nội dung biểu mẫu chuyên nghiệp."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=150
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Lỗi khi rewrite: {e}")
            return user_input
    
    def generate_personalized_suggestions(self, db_data: List[Dict], user_id: str, 
                                        field_code: Optional[str] = None, 
                                        context: Optional[str] = None) -> Dict[str, Any]:
        """Generate personalized suggestions combining field matching and AI"""
        # First get field matches using the enhanced matcher
        if field_code:
            # Tìm field_name tương ứng với field_code trong dữ liệu lịch sử
            field_name = None
            for entry in db_data:
                form_data = entry.get("form_data", {})
                for key in form_data.keys():
                    if key == field_code:
                        field_name = key
                        break
                if field_name:
                    break
            
            # Nếu không tìm thấy, sử dụng field_code làm field_name
            if not field_name:
                field_name = field_code
                
            matched_fields = self.field_matcher.match_fields([field_name], user_id=user_id)
        else:
            # If no specific field, get all unique field names from db_data
            all_fields = set()
            for entry in db_data:
                if entry.get("user_id") == user_id:
                    all_fields.update(entry.get("form_data", {}).keys())
            matched_fields = self.field_matcher.match_fields(list(all_fields), user_id=user_id)
        
        suggestions = defaultdict(Counter)
        recent_data = defaultdict(list)
        entry_timestamps = defaultdict(list)

        # Sort data by time (newest first)
        # Chuyển đổi user_id thành chuỗi để đảm bảo so sánh chính xác
        str_user_id = str(user_id) if user_id is not None else ""
        sorted_entries = sorted(
            [entry for entry in db_data if str(entry.get("user_id")) == str_user_id],
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )

        # Process data with time-based weights
        for idx, entry in enumerate(sorted_entries):
            recency_weight = max(1, 5 - idx // 2)  # Decreasing weight over time
            
            for key, value in entry["form_data"].items():
                if field_code is None or key == field_code:
                    # Check if this field has matches from our field matcher
                    if key in matched_fields:
                        # Use matched field values to enhance suggestions
                        matched_values = [match["value"] for match in matched_fields[key]]
                        if matched_values:
                            value = matched_values[0]  # Use the best matched value

                    # Rewrite if content is long, otherwise keep as is
                    cleaned_value = value.strip()
                    if len(cleaned_value.split()) >= 5:
                        rewritten_value = self.rewrite_user_input_for_suggestion(key, cleaned_value, context)
                    else:
                        rewritten_value = cleaned_value

                    suggestions[key][rewritten_value] += recency_weight
                    recent_data[key].append(rewritten_value)
                    entry_timestamps[key].append((rewritten_value, entry.get("timestamp", ""), recency_weight))

        result = {}

        for key, counter in suggestions.items():
            all_values = list(counter.keys())
            
            # Get 3 most recent values based on timestamp
            recent_entries = sorted(entry_timestamps[key], key=lambda x: x[1], reverse=True)[:3]
            recent_values = [entry[0] for entry in recent_entries]
            
            # Get field-specific historical values from field matcher
            field_specific_values = self.field_matcher.get_suggested_values(key, limit=10, user_id=int(user_id) if user_id else None)
            
            # Combine with our collected values
            combined_values = list(set(all_values + field_specific_values))
            
            # Get AI suggestions
            gpt_response = self.call_gpt_for_suggestions(
                field_name=key,
                historical_values=combined_values,
                context=context,
                recent_values=recent_values
            )
            
            # Get most common values with weights
            most_common_values = [val for val, _ in counter.most_common(3)]
            
            # Prioritize recent values
            prioritized_values = recent_values.copy()
            
            # Add common values if not already in priority list
            for val in most_common_values:
                if val not in prioritized_values:
                    prioritized_values.append(val)
            
            # Combine with AI suggestions
            combined = []
            # First add prioritized values
            for val in prioritized_values:
                if val not in combined and len(combined) < 3:
                    combined.append(val)
            
            # Then add AI suggestions
            for val in gpt_response["suggestions"]:
                if val not in combined and len(combined) < 5:
                    combined.append(val)
            
            # Choose default value - prefer AI suggestion, then recent, then common
            default_value = gpt_response["default"]
            if not default_value and recent_values:
                default_value = recent_values[0]
            elif not default_value and most_common_values:
                default_value = most_common_values[0]
            
            result[key] = {
                "suggestions": combined,
                "default": default_value,
                "confidence": 0.9,
                "details": {
                    "source_name": "Enhanced Field Matching + AI",
                    "method": "Combined historical matching and AI suggestions",
                    "confidence": 0.9
                }
            }

        return result if field_code is None else result.get(field_code, {"suggestions": [], "default": ""})
    
    # def update_form_history(self, new_form_data: Dict, user_id: Optional[str] = None) -> None:
    #     """Update form history in both the field matcher and our local storage"""
    #     # Update the field matcher's history
    #     self.field_matcher.update_form_history(new_form_data, user_id)
        
    #     # Also update our local JSON file
    #     try:
    #         if os.path.exists(FORM_HISTORY_PATH):
    #             with open(FORM_HISTORY_PATH, 'r', encoding='utf-8') as f:
    #                 history = json.load(f)
    #         else:
    #             history = []
                
    #         # Add timestamp to new entry
    #         new_entry = {
    #             "user_id": user_id,
    #             "form_data": new_form_data,
    #             "timestamp": datetime.datetime.now().isoformat()
    #         }
    #         history.append(new_entry)
            
    #         with open(FORM_HISTORY_PATH, 'w', encoding='utf-8') as f:
    #             json.dump(history, f, ensure_ascii=False, indent=2)
                
    #     except Exception as e:
    #         print(f"Error updating form history file: {e}")