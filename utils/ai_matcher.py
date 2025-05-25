# utils/ai_matcher.py
from openai import OpenAI
from config.config import FORM_HISTORY_PATH
from utils.api_key_manager import get_api_key_manager
from collections import defaultdict, Counter
import re
import json
import logging
from typing import Dict, List, Optional, Any
from .field_matcher import EnhancedFieldMatcher
import hashlib
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class AIFieldMatcher:
    def __init__(self, form_history_path: str = FORM_HISTORY_PATH):
        self.field_matcher = EnhancedFieldMatcher(form_history_path)
        self.context_cache = {}
        self.suggestion_cache = {}
        self._client = None
        self.form_context_analysis = {}
        self.field_relationships = defaultdict(list)
        self.field_name_mapping = {}
        self.similar_fields_cache = {}
        self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        self._initialize()

    def _initialize(self):
        """Initialize all components"""
        self.field_matcher._build_models()
        self.field_matcher._load_user_preferences()
        self._analyze_field_relationships()
        self._build_field_name_mapping()

    def _build_field_name_mapping(self):
        """Build mapping between field name variants"""
        try:
            field_variants = defaultdict(set)
            
            for form in self.field_matcher.form_history:
                if isinstance(form, dict) and 'form_data' in form:
                    for field_name in form['form_data'].keys():
                        normalized_name = self._normalize_field_name(field_name)
                        if normalized_name:
                            field_variants[normalized_name].add(field_name)
            
            for norm_name, variants in field_variants.items():
                for variant in variants:
                    self.field_name_mapping[variant] = list(variants)
            
            logger.info(f"Built field name mapping with {len(self.field_name_mapping)} entries")
        except Exception as e:
            logger.error(f"Error building field name mapping: {e}")

    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field name for comparison"""
        if not field_name or not isinstance(field_name, str):
            return ""
        
        normalized = re.sub(r'[^\w\s]', '', field_name.lower())
        normalized = re.sub(r'\b(field|input|text|form|data)\b', '', normalized)
        return re.sub(r'\s+', ' ', normalized).strip()

    def _analyze_field_relationships(self):
        """Analyze relationships between fields based on co-occurrence"""
        try:
            field_co_occurrence = defaultdict(lambda: defaultdict(int))
            
            for form in self.field_matcher.form_history:
                if isinstance(form, dict) and 'form_data' in form:
                    fields = [f for f in form['form_data'].keys() 
                             if f not in ['form_id', 'document_name', 'form_type']]
                    
                    for i, field1 in enumerate(fields):
                        for field2 in fields[i+1:]:
                            field_co_occurrence[field1][field2] += 1
                            field_co_occurrence[field2][field1] += 1
            
            for field, related_fields in field_co_occurrence.items():
                sorted_related = sorted(related_fields.items(), key=lambda x: x[1], reverse=True)
                self.field_relationships[field] = [f[0] for f in sorted_related[:5]]
                
            logger.info(f"Analyzed relationships between {len(self.field_relationships)} fields")
        except Exception as e:
            logger.error(f"Error analyzing field relationships: {e}")

    @property
    def client(self):
        if self._client is None:
            api_key_manager = get_api_key_manager()
            self._client = api_key_manager.get_client()
            if self._client is None:
                raise RuntimeError("Failed to initialize OpenAI client. Check API key configuration.")
        return self._client
    def _generate_cache_key(self, text: str) -> str:
            return hashlib.sha256(text.encode('utf-8')).hexdigest()
    def extract_context_from_form_text(self, form_text: str) -> str:
        """Extract context from form text with caching"""
        cache_key = self._generate_cache_key(form_text)
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
            
        key_fields = self._extract_key_fields(form_text)
        
        prompt = (
            "Analyze this form and provide:\n\n"
            f"{form_text}\n\n"
            "Key fields:\n"
            f"{key_fields}\n\n"
            "Provide:\n"
            "1. Main purpose\n"
            "2. Target users\n"
            "3. Usage context\n"
            "4. Typical values\n"
            "5. Form classification\n\n"
            "Return concise Vietnamese summary."
        )
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "You're an AI form analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=300
            )

            context = response.choices[0].message.content.strip() if response and response.choices else ""
           # self.context_cache[cache_key] = context
            self._enhance_context_analysis(form_text, context)
            return context
        except Exception as e:
            logger.error(f"Error extracting context: {str(e)}")
            return ""

    def _enhance_context_analysis(self, form_text: str, context: str) -> Dict:
        """Phân tích ngữ cảnh nâng cao với mô hình embedding"""
        cache_key = hashlib.sha256(form_text.encode()).hexdigest()
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        # Sử dụng embedding để phân tích ngữ cảnh
        embeddings = self.sbert_model.encode([form_text, context])
        form_embedding, context_embedding = embeddings[0], embeddings[1]
        
        # Phân tích cấu trúc form
        structure_prompt = f"""Phân tích cấu trúc form sau và phản hồi bằng JSON:
{form_text[:2000]}

Yêu cầu phản hồi JSON với định dạng:
{{
  "form_type": "Đơn xin việc",
  "sections": ["Thông tin cá nhân", "Kinh nghiệm làm việc", "Học vấn"],
  "field_relationships": "‘Vị trí’ nằm trong phần Kinh nghiệm, liên quan đến công ty và thời gian làm việc.",
  "field_importance": {{
    "Họ tên": "Cao",
    "Vị trí": "Cao",
    "Công ty": "Trung bình",
    "Thời gian": "Trung bình"
  }},
  "field_extraction": {{
    "Công ty": "Công ty một thành viên Hữu Phước",
    "Vị trí": "Văn phòng",
    "Địa điểm": "Thương mại",
    "Thời gian bắt đầu": "27/09/2003"
  }}
}}

Phản hồi JSON này phải đầy đủ và đúng định dạng.
"""
        
        # Gọi API phân tích
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia phân tích biểu mẫu."},
                    {"role": "user", "content": structure_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            analysis.update({
                "form_embedding": form_embedding.tolist(),
                "context_embedding": context_embedding.tolist()
            })
            logger.info("Phân tích trường: %s", analysis.get("field_extraction", {}))
            self.context_cache[cache_key] = analysis
            return analysis
        except Exception as e:
            logger.error(f"Lỗi phân tích ngữ cảnh: {e}")
            return {}

    def _extract_key_fields(self, form_text: str) -> str:
        """Extract key fields using field matcher"""
        fields = self.field_matcher.find_most_similar_field(form_text, top_n=5)
        return "\n".join([f"- {field[0]} (confidence: {field[1]:.2f})" for field in fields])

    def find_similar_fields(self, field_name: str, threshold: float = 0.6, max_results: int = 5) -> List[str]:
        """Find similar fields with caching"""
        cache_key = f"{field_name}_{threshold}_{max_results}"
        if cache_key in self.similar_fields_cache:
            return self.similar_fields_cache[cache_key]
        
        if field_name in self.field_name_mapping:
            similar_fields = self.field_name_mapping[field_name]
            if similar_fields:
                self.similar_fields_cache[cache_key] = similar_fields[:max_results]
                return similar_fields[:max_results]
        
        similar_fields = [f[0] for f in 
                         self.field_matcher.find_most_similar_field(field_name, top_n=max_results) 
                         if f[1] >= threshold]
        
        self.similar_fields_cache[cache_key] = similar_fields
        return similar_fields

    def generate_suggestions(
        self,
        field_name: str,
        historical_values: List[str],
        context: Optional[str] = None,
        form_type: Optional[str] = None,
        related_fields_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate smart suggestions for form field"""
        cache_key = f"{field_name}_{hash(str(historical_values))}_{hash(context) if context else ''}"
        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key]
        
        try:
            similar_fields = self.find_similar_fields(field_name)
            related_fields = self._get_related_fields(field_name, similar_fields, related_fields_data)
            
            prompt = self._build_suggestion_prompt(
                field_name,
                similar_fields,
                historical_values,
                context,
                related_fields
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "Smart form suggestion assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            return self._parse_suggestion_response(response.choices[0].message.content)
        
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return {"suggestions": [], "default": "", "reason": ""}

    def _get_related_fields(self, field_name: str, similar_fields: List[str], related_data: Optional[Dict]) -> str:
        """Get information about related fields"""
        related_fields = self.field_relationships.get(field_name, [])
        if not related_fields and similar_fields:
            for similar_field in similar_fields:
                if similar_field in self.field_relationships:
                    related_fields = self.field_relationships[similar_field]
                    break
        
        if not related_fields or not related_data:
            return ""
            
        related_info = []
        for rel_field in related_fields[:3]:
            if rel_field in related_data:
                related_info.append(f"{rel_field}: {related_data[rel_field]}")
        
        return "\nRelated fields:\n- " + "\n- ".join(related_info) if related_info else ""

    def _build_suggestion_prompt(
        self,
        field_name: str,
        similar_fields: List[str],
        historical_values: List[str],
        context: Optional[str],
        related_fields: str
    ) -> str:
        """Construct suggestion prompt"""
        prompt_parts = [
            f"Field: '{field_name}'",
            f"Similar fields: {', '.join(similar_fields) if similar_fields else 'None'}",
        ]
        
        if historical_values:
            prompt_parts.append(f"\nHistory:\n- " + "\n- ".join(historical_values[:10]))
        
        if context:
            prompt_parts.append(f"\nContext:\n{context}")
        
        if related_fields:
            prompt_parts.append(related_fields)
        
        prompt_parts.extend([
            "\nGenerate 3 different suggestions in JSON format:",
            "{\"suggestions\": [{\"text\": \"suggestion1\", \"reason\": \"...\"}, ...],",
            "\"default\": \"best default value\"}"
        ])
        
        return "\n".join(prompt_parts)

    def _parse_suggestion_response(self, content: str) -> Dict[str, Any]:
        """Parse AI suggestion response"""
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            result = json.loads(json_match.group(1)) if json_match else {
                "suggestions": [],
                "default": "",
                "reason": "Failed to parse response"
            }
        
        if not isinstance(result, dict):
            result = {"suggestions": [], "default": "", "reason": "Invalid response format"}
        
        return {
            "suggestions": result.get("suggestions", [])[:3],
            "default": result.get("default", ""),
            "reason": result.get("reason", "")
        }

    def rewrite_user_input(self, field_name: str, user_input: str, context: Optional[str] = None) -> str:
        """Improve user input for form field"""
        if not user_input:
            return ""
            
        try:
            similar_fields = self.find_similar_fields(field_name)
            
            prompt = (
                f"Improve this form input for field '{field_name}':\n"
                f"Similar fields: {', '.join(similar_fields) if similar_fields else 'None'}\n"
                f"User input: \"{user_input}\"\n"
            )
            
            if context:
                prompt += f"\nContext:\n{context}\n"
                
            prompt += (
                "\nImprove to be:\n"
                "1. Grammatically correct\n"
                "2. Field-appropriate\n"
                "3. Professional\n"
                "4. Preserve original meaning\n\n"
                "Return only improved text."
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "Form input improvement assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            improved_text = response.choices[0].message.content.strip() if response and response.choices else user_input
            return improved_text.strip('"')
            
        except Exception as e:
            logger.error(f"Error rewriting input: {e}")
            return user_input
    def _get_enhanced_context(
        self,
        context: Optional[str],
        db_data: List[Dict],
        user_id: str,
        form_type: Optional[str] = None
    ) -> str:
        """
        Tăng cường ngữ cảnh dựa trên lịch sử người dùng, loại form và các thông tin liên quan
        """
        # Khởi tạo context nếu chưa có
        enhanced_context = context or ""

        # Lấy các form gần đây của người dùng cùng loại (nếu có)
        recent_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id)
            and (not form_type or entry.get("form_data", {}).get("form_type") == form_type)
        ]
        
        # Chọn tối đa 3 mẫu gần nhất để rút trích ngữ cảnh
        recent_entries = sorted(
            recent_entries,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:3]
        
        # Trích xuất một số trường phổ biến để bổ sung vào context
        for entry in recent_entries:
            form_data = entry.get("form_data", {})
            context_snippet = "; ".join(
                f"{k}: {v}" for k, v in form_data.items() if v and k != "form_type"
            )
            if context_snippet:
                if not isinstance(enhanced_context, str):
                    enhanced_context = str(enhanced_context)

                enhanced_context += f"\nNgữ cảnh từ mẫu trước: {context_snippet}"
        
        return enhanced_context.strip()

    def generate_personalized_suggestions(
        self,
        db_data: List[Dict],
        user_id: str,
        field_code: Optional[str] = None,
        field_name: Optional[str] = None,
        context: Optional[str] = None,
        form_type: Optional[str] = None
        ) -> Dict[str, Any]:
        """Generate personalized suggestions with context"""
        filtered_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id) and
            (form_type is None or entry.get("form_data", {}).get("form_type") == form_type)
        ]
        sorted_entries = sorted(filtered_entries, key=lambda x: x.get("timestamp", ""), reverse=True)

        # Nếu chưa có context thì trích xuất từ lịch sử biểu mẫu gần đây
        if not context and sorted_entries:
            recent_forms_text = "\n".join([
                json.dumps(entry.get("form_data", {}), ensure_ascii=False)
                for entry in sorted_entries[:3]
            ])
        context = self._get_enhanced_context(context, db_data, user_id, form_type)

        recent_values = []
        matched_fields = set()
        related_fields_data = {}
        best_similarity = 0
        best_field_name = field_name or None

        if field_code:
            similar_fields_cache = {}

            # Nếu chưa có field_name, tìm field_name tốt nhất từ lịch sử
            if not field_name:
                for entry in sorted_entries:
                    form_data = entry.get("form_data", {})

                    # Ưu tiên exact match
                    if field_code in form_data:
                        best_field_name = field_code
                        best_similarity = 1.0
                        break

                    # Tìm trường gần giống
                    for key in form_data.keys():
                        if key not in similar_fields_cache:
                            similar_fields_cache[key] = self._calculate_field_similarity(field_code, key)

                        similarity = similar_fields_cache[key]
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_field_name = key

                    if best_similarity >= 0.7:
                        break

                # Nếu không tìm được tên tốt hơn, dùng field_code làm tên
                field_name = best_field_name if best_similarity >= 0.5 else field_code
            else:
                # Nếu field_name đã được cung cấp → vẫn kiểm tra độ tương đồng để log lại
                best_field_name = field_name
                best_similarity = self._calculate_field_similarity(field_code, field_name)

            # Xác định các trường liên quan
            similar_fields = self.find_similar_fields(field_name)
            related_fields = self._get_related_field_names(field_name, similar_fields)

            # Thu thập dữ liệu
            for entry in sorted_entries:
                form_data = entry.get("form_data", {})

                # Dữ liệu từ trường chính
                if field_name in form_data:
                    value = form_data[field_name]
                    if value and str(value).strip():
                        recent_values.append(str(value).strip())
                        matched_fields.add(field_name)

                # Dữ liệu từ các trường liên quan
                self._collect_related_data(form_data, related_fields, related_fields_data)

                if len(recent_values) >= 10:
                    break

        frequency_data = Counter(recent_values)
    
        # Sinh đề xuất từ AI
        ai_suggestion = self.generate_suggestions(
            field_name=field_name or field_code or "unknown",
            historical_values=recent_values,
            context=context,
            form_type=form_type,
            related_fields_data=related_fields_data
        )

        # Tính toán giá trị mặc định
        default_value = self._get_default_value(sorted_entries, matched_fields, ai_suggestion)
      
        return {
            "ai_suggestion": ai_suggestion,
            "recent_values": recent_values,
            "default_value": default_value,
            "matched_fields": list(matched_fields),
            "related_fields_data": related_fields_data,
            "reason": ai_suggestion.get("reason", ""),
            "field_matching_info": {
                "requested_field_code": field_code,
                "matched_field_name": field_name,
                "similarity_score": round(best_similarity, 3)
            }
        }



    def _calculate_field_similarity(self, field1: str, field2: str) -> float:
        """Calculate similarity between two field names (0-1)"""
        # Simple implementation - can be enhanced with more sophisticated algorithms
        field1 = field1.lower().strip()
        field2 = field2.lower().strip()
        
        if field1 == field2:
            return 1.0
        
        # Check for partial matches
        if field1 in field2 or field2 in field1:
            return 0.8
            
        # Check for common prefixes/suffixes
        if field1.split('_')[0] == field2.split('_')[0]:
            return 0.6
            
        if field1.split('_')[-1] == field2.split('_')[-1]:
            return 0.5
            
        # Very basic token set similarity
        set1 = set(field1.split('_'))
        set2 = set(field2.split('_'))
        intersection = set1 & set2
        union = set1 | set2
        
        if union:
            return len(intersection) / len(union)
            
        return 0.0

    def _get_related_field_names(self, field_name: str, similar_fields: List[str]) -> List[str]:
        """Get names of related fields"""
        related_fields = self.field_relationships.get(field_name, [])
        if not related_fields and similar_fields:
            for similar_field in similar_fields:
                if similar_field in self.field_relationships:
                    related_fields = self.field_relationships[similar_field]
                    break
        return related_fields[:3] if related_fields else []

    def _collect_related_data(self, form_data: Dict, related_fields: List[str], related_data: Dict):
        """Collect data from related fields"""
        for related_field in related_fields:
            if related_field in form_data and form_data[related_field]:
                related_data[related_field] = form_data[related_field]

    def _collect_field_values(self, form_data: Dict, field_name: str, similar_fields: List[str], 
                            values: List[str], matched_fields: set):
        """Collect field values from form data"""
        for similar_field in similar_fields:
            if similar_field in form_data and form_data[similar_field]:
                val = str(form_data[similar_field]).strip()
                if val and val not in values:
                    values.append(val)
                    matched_fields.add(similar_field)
        
        if field_name in form_data and form_data[field_name]:
            val = str(form_data[field_name]).strip()
            if val and val not in values:
                values.append(val)
                matched_fields.add(field_name)

    def _get_default_value(self, entries: List[Dict], matched_fields: set, ai_suggestion: Dict) -> str:
        """Get default value from most recent entry or AI suggestion"""
        if entries and matched_fields:
            latest_form = entries[0].get("form_data", {})
            for field in matched_fields:
                if field in latest_form:
                    return str(latest_form[field]).strip()
        return ai_suggestion.get("default", "")

    def update_field_value(self, field_name: str, field_value: str, user_id: Optional[str] = None):
        """Update field value and clear related caches"""
        try:
            self.field_matcher.update_field_value(field_name, field_value, user_id)
            
            # Clear relevant caches
            for key in list(self.suggestion_cache.keys()):
                if field_name in key:
                    del self.suggestion_cache[key]
            
            # Update field name mapping
            similar_fields = self.find_similar_fields(field_name)
            if similar_fields:
                if field_name not in self.field_name_mapping:
                    self.field_name_mapping[field_name] = similar_fields
                
                for similar_field in similar_fields:
                    if similar_field not in self.field_name_mapping:
                        self.field_name_mapping[similar_field] = []
                    if field_name not in self.field_name_mapping[similar_field]:
                        self.field_name_mapping[similar_field].append(field_name)
            
            logger.info(f"Updated field {field_name} for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating field: {e}")