# utils/ai_matcher.py
from openai import OpenAI
from config.config import FORM_HISTORY_PATH
from utils.api_key_manager import get_api_key_manager
from collections import defaultdict, Counter
import re
import json
import logging
import datetime
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
        self._current_provider = None  # Thêm thuộc tính này
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
            
            # Ưu tiên sử dụng OpenAI nếu có
            preferred_provider = 'openai'
            
            # Kiểm tra provider nào khả dụng
            available_provider = api_key_manager.get_available_provider(preferred_provider)
            
            if available_provider:
                self._client = api_key_manager.get_client(available_provider)
                self._current_provider = available_provider
                logger.info(f"Using {available_provider} client for suggestions")
            else:
                # Kiểm tra cụ thể Gemini nếu OpenAI không khả dụng
                available_provider = api_key_manager.get_available_provider('gemini')
                if available_provider:
                    self._client = api_key_manager.get_client(available_provider)
                    self._current_provider = available_provider
                    logger.info(f"Using {available_provider} client for suggestions (fallback)")
                else:
                    # More detailed error message
                    openai_status = "available" if api_key_manager._get_active_api_key('openai') else "unavailable"
                    gemini_status = "available" if api_key_manager._get_active_api_key('gemini') else "unavailable"
                    raise RuntimeError(
                        f"No available AI provider. Status - OpenAI: {openai_status}, Gemini: {gemini_status}. "
                        "Please check API key configuration."
                    )
                    
        return self._client
    def _build_openai_context_prompt(self, form_text: str, key_fields: str) -> str:
        """Build context extraction prompt for OpenAI"""
        prompt = f"""Phân tích ngữ cảnh của biểu mẫu sau và xác định:
1. Loại biểu mẫu (đơn xin việc, đơn đăng ký, khảo sát...)
2. Các trường quan trọng và mục đích của chúng
3. Mối quan hệ giữa các trường dữ liệu
4. Ngữ cảnh tổng thể của biểu mẫu

Nội dung biểu mẫu:
{form_text[:3000]}

Các trường đã xác định:
{key_fields}

Hãy tóm tắt ngữ cảnh trong 3-5 câu, tập trung vào mục đích và cấu trúc của biểu mẫu.
"""
        return prompt

    def _build_openai_suggestion_prompt(
        self,
        field_name: str,
        similar_fields: List[str],
        historical_values: List[str],
        context: Optional[str],
        related_fields: str
    ) -> str:
        """Construct suggestion prompt optimized for OpenAI"""
        if self._is_date_field(field_name):
            return self._format_date_suggestion(field_name)  # Sử dụng phương thức mới
            
        prompt_parts = [
            "You are a smart form suggestion assistant.",
            f"Field: '{field_name}'",
            f"Similar fields: {', '.join(similar_fields) if similar_fields else 'None'}",
            "IMPORTANT: If this field appears to be a date field (day, month, year, date), ALWAYS use the current date instead of historical values.",
        ]

        prompt_parts = [
            "You are a smart form suggestion assistant.",
            f"Field: '{field_name}'",
            f"Similar fields: {', '.join(similar_fields) if similar_fields else 'None'}",
        ]
        
        if historical_values:
            prompt_parts.append(f"\nHistorical values:\n- " + "\n- ".join(historical_values[:10]))
        
        if context:
            prompt_parts.append(f"\nContext:\n{context}")
        
        if related_fields:
            prompt_parts.append(related_fields)
        
        prompt_parts.extend([
            "\nGenerate 3 different suggestions in JSON format:",
            "```json",
            "{\"suggestions\": [{\"text\": \"suggestion1\", \"reason\": \"...\"}, ...],",
            "\"default\": \"best default value\",",
            "\"reason\": \"explanation of default choice\"}",
            "```",
            "\nReturn only valid JSON, no other content."
        ])
        
        return "\n".join(prompt_parts)

    def _build_openai_rewrite_prompt(
        self,
        field_name: str,
        similar_fields: List[str],
        user_input: str,
        context: Optional[str]
    ) -> str:
        """Build rewrite prompt for OpenAI"""
        prompt = [
            "Improve form input with requirements:",
            "1. Grammatically correct",
            "2. Appropriate for the field",
            "3. Professionally presented",
            "4. Preserves original meaning",
            "",
            f"Field: '{field_name}'",
            f"Similar fields: {', '.join(similar_fields) if similar_fields else 'None'}",
            f"Input: \"{user_input}\""
        ]
        
        if context:
            prompt.append(f"\nContext:\n{context}")
        
        prompt.append("\nReturn only the improved text, no other content.")
        
        return "\n".join(prompt)

    def clear_caches(self):
        """Clear all caches"""
        self.context_cache.clear()
        self.suggestion_cache.clear()
        self.similar_fields_cache.clear()
        logger.info("Cleared all AI matcher caches")

    def get_field_statistics(self, field_name: str) -> Dict[str, Any]:
        """Get statistics about a field"""
        stats = {
            "field_name": field_name,
            "similar_fields": self.find_similar_fields(field_name),
            "related_fields": self.field_relationships.get(field_name, []),
            "name_variants": self.field_name_mapping.get(field_name, []),
            "cache_status": {
                "context_cache": field_name in [k.split('_')[0] for k in self.context_cache.keys()],
                "suggestion_cache": field_name in [k.split('_')[0] for k in self.suggestion_cache.keys()],
                "similar_fields_cache": field_name in self.similar_fields_cache
            }
        }
        return stats
    def _format_date_suggestion(self, field_name: str, form_type: Optional[str] = None) -> Dict[str, Any]:
            """Định dạng gợi ý ngày tháng năm dựa trên tên trường và loại biểu mẫu"""
            today = datetime.datetime.now()
            name_lower = field_name.lower()
            
            # Xác định định dạng phù hợp dựa trên loại biểu mẫu
            date_format = "%d/%m/%Y"  # Định dạng mặc định
            
            # Điều chỉnh định dạng dựa trên loại biểu mẫu
            if form_type:
                form_type_lower = form_type.lower()
                if "quốc tế" in form_type_lower or "international" in form_type_lower:
                    date_format = "%Y-%m-%d"
                elif "hợp đồng" in form_type_lower or "contract" in form_type_lower:
                    date_format = "ngày %d tháng %m năm %Y"
            
            # Kiểm tra nếu là trường ngày sinh, tháng sinh, năm sinh
            if any(birth_kw in name_lower for birth_kw in ["sinh", "birth", "dob"]):
                # Trả về kết quả trống để sử dụng dữ liệu lịch sử hoặc gợi ý AI
                return {
                    "suggestions": [],
                    "default": "",
                    "reason": "Trường ngày sinh nên sử dụng dữ liệu cá nhân"
                }
            
            # Xác định loại trường ngày tháng
            if "ngày" in name_lower and not any(kw in name_lower for kw in ["tháng", "năm"]):
                return {
                    "suggestions": [
                        {"text": today.strftime("%d"), "reason": "Ngày hiện tại"},
                        {"text": today.strftime("%d/%m"), "reason": "Ngày/tháng hiện tại"},
                        {"text": today.strftime(date_format), "reason": "Ngày đầy đủ theo định dạng phù hợp"}
                    ],
                    "default": today.strftime("%d"),
                    "reason": "Tự động điền ngày hiện tại"
                }
            elif "tháng" in name_lower and not any(kw in name_lower for kw in ["ngày", "năm"]):
                return {
                    "suggestions": [
                        {"text": today.strftime("%m"), "reason": "Tháng hiện tại"},
                        {"text": f"Tháng {today.strftime('%m')}", "reason": "Tháng hiện tại (có tiền tố)"},
                        {"text": today.strftime("%B"), "reason": "Tháng hiện tại (chữ)"}
                    ],
                    "default": today.strftime("%m"),
                    "reason": "Tự động điền tháng hiện tại"
                }
            elif "năm" in name_lower and not any(kw in name_lower for kw in ["ngày", "tháng"]):
                return {
                    "suggestions": [
                        {"text": today.strftime("%Y"), "reason": "Năm hiện tại"},
                        {"text": today.strftime("%y"), "reason": "Năm hiện tại (2 chữ số)"},
                        {"text": f"Năm {today.strftime('%Y')}", "reason": "Năm hiện tại (có tiền tố)"}
                    ],
                    "default": today.strftime("%Y"),
                    "reason": "Tự động điền năm hiện tại"
                }
            else:
                # Trường hợp ngày tháng năm đầy đủ
                return {
                    "suggestions": [
                        {"text": today.strftime(date_format), "reason": "Ngày hiện tại theo định dạng phù hợp"},
                        {"text": today.strftime("%d/%m/%Y"), "reason": "Ngày hiện tại (DD/MM/YYYY)"},
                        {"text": today.strftime("%Y-%m-%d"), "reason": "Ngày hiện tại (YYYY-MM-DD)"}
                    ],
                    "default": today.strftime(date_format),
                    "reason": "Tự động điền ngày hiện tại theo định dạng phù hợp"
                }
    def batch_generate_suggestions(
        self,
        fields: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Generate suggestions for multiple fields at once"""
        results = {}
        for field in fields:
            field_name = field.get("field_name", "")
            if not field_name:
                continue
                
            suggestions = self.generate_suggestions(
                field_name=field_name,
                historical_values=field.get("historical_values", []),
                context=context,
                form_type=field.get("form_type"),
                related_fields_data=field.get("related_fields_data")
            )
            results[field_name] = suggestions
            
        return results

    def export_field_mappings(self) -> Dict[str, Any]:
        """Export field mappings and relationships"""
        return {
            "field_name_mapping": dict(self.field_name_mapping),
            "field_relationships": dict(self.field_relationships),
            "similar_fields_cache": {
                k: v for k, v in self.similar_fields_cache.items() 
                if isinstance(v, list)
            }
        }

    def import_field_mappings(self, data: Dict[str, Any]):
        """Import field mappings and relationships"""
        try:
            if "field_name_mapping" in data:
                self.field_name_mapping.update(data["field_name_mapping"])
                
            if "field_relationships" in data:
                self.field_relationships.update(data["field_relationships"])
                
            if "similar_fields_cache" in data:
                self.similar_fields_cache.update(data["similar_fields_cache"])
                
            logger.info("Imported field mappings successfully")
        except Exception as e:
            logger.error(f"Error importing field mappings: {e}")
    def _generate_cache_key(self, text: str) -> str:
            return hashlib.sha256(text.encode('utf-8')).hexdigest()
    def _build_gemini_context_prompt(self, form_text: str, key_fields: str) -> str:
        """Build context extraction prompt for Gemini"""
        prompt = f"""Bạn là một trợ lý AI chuyên phân tích biểu mẫu.

    Hãy phân tích biểu mẫu dưới đây và xác định:
    1. Loại biểu mẫu (ví dụ: đơn xin việc, đơn đăng ký, khảo sát, hợp đồng, phản hồi khách hàng, v.v.)
    2. Các trường quan trọng và mục đích sử dụng của từng trường
    3. Mối liên hệ giữa các trường dữ liệu
    4. Ngữ cảnh tổng thể và mục đích sử dụng biểu mẫu

    Biểu mẫu:
    {form_text[:3000]}

    Các trường dữ liệu đã được phát hiện:
    {key_fields}

    Vui lòng tóm tắt ngữ cảnh trong 3–5 câu, tập trung vào mục đích và cấu trúc của biểu mẫu.
    """
        return prompt

    def extract_context_from_form_text(self, form_text: str) -> str:
        """Extract context from form text with provider fallback"""
        cache_key = self._generate_cache_key(form_text)
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]

        # Ensure client is initialized
        if self._client is None:
            _ = self.client  # This will initialize the provider

        key_fields = self._extract_key_fields(form_text)

        try:
            if self._current_provider == 'openai':
                prompt = self._build_openai_context_prompt(form_text, key_fields)
                model_name = "gpt-4-1106-preview"

                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Bạn là trợ lý phân tích biểu mẫu."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.6,
                    max_tokens=300
                )
                context = response.choices[0].message.content.strip()

            elif self._current_provider == 'gemini':
                prompt = self._build_gemini_context_prompt(form_text, key_fields)

                # Tạo lại model Gemini nếu chưa có
                from google.generativeai import GenerativeModel

                if not isinstance(self.client, GenerativeModel):
                    self._client = GenerativeModel("gemini-2.0-flash")

                response = self.client.generate_content(
                    contents=[{"role": "user", "parts": [{"text": prompt}]}],
                    generation_config={
                        "temperature": 0.6,
                        "max_output_tokens": 300,
                    }
                )
                context = response.candidates[0].content.parts[0].text.strip()

            else:
                raise ValueError(f"Unknown provider: {self._current_provider}")

            self.context_cache[cache_key] = context
            self._enhance_context_analysis(form_text, context)
            return context

        except Exception as e:
            logger.error(f"Error extracting context with {self._current_provider}: {str(e)}")
            # Attempt provider fallback
            if self._current_provider == 'openai':
                try:
                    self._client = None  # Reset client to force reinitialization
                    _ = self.client  # Reinitialize
                    if self._current_provider == 'gemini':
                        return self.extract_context_from_form_text(form_text)
                except Exception as e2:
                    logger.error(f"Fallback to Gemini failed: {str(e2)}")
            return ""


    def _enhance_context_analysis(self, form_text: str, context: str,tried_fallback: bool = False) -> Dict:
        """Phân tích ngữ cảnh nâng cao với kiểm tra provider hiện tại"""
        context_lower = context.lower()
        today = datetime.datetime.now()
        
        # Cải tiến phát hiện trường ngày tháng năm trong ngữ cảnh
        date_patterns = {
            "ngày": {"value": today.strftime("%d"), "format": "DD"},
            "tháng": {"value": today.strftime("%m"), "format": "MM"},
            "năm": {"value": today.strftime("%Y"), "format": "YYYY"},
            "date": {"value": today.strftime("%d/%m/%Y"), "format": "DD/MM/YYYY"},
            "day": {"value": today.strftime("%d"), "format": "DD"},
            "month": {"value": today.strftime("%m"), "format": "MM"},
            "year": {"value": today.strftime("%Y"), "format": "YYYY"},
            "thời gian": {"value": today.strftime("%H:%M"), "format": "HH:MM"},
            "time": {"value": today.strftime("%H:%M"), "format": "HH:MM"}
        }
        
        # Kiểm tra từng mẫu ngày tháng trong ngữ cảnh
        for pattern, data in date_patterns.items():
            if pattern in context_lower and "sinh" not in context_lower and "birth" not in context_lower:
                return {
                    "contains_date_fields": True,
                    "suggested_value": data["value"],
                    "suggested_format": data["format"],
                    "date_type": pattern
                }
        cache_key = hashlib.sha256(form_text.encode()).hexdigest()
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        # Sử dụng embedding để phân tích ngữ cảnh
        embeddings = self.sbert_model.encode([form_text, context])
        form_embedding, context_embedding = embeddings[0], embeddings[1]
        
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

        try:
            if self._current_provider == 'openai':
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
            elif self._current_provider == 'gemini':
                from google.generativeai import GenerativeModel

                if not isinstance(self.client, GenerativeModel):
                    self._client = GenerativeModel("gemini-2.0-flash")
                response = self.client.generate_content(
                    contents=[{"parts": [{"text": structure_prompt}]}],
                    generation_config={"temperature": 0.3, "max_output_tokens": 512}
                )
                raw_text = response.candidates[0].content.parts[0].text
                analysis = json.loads(raw_text)

            else:
                raise ValueError(f"Unknown provider: {self._current_provider}")

            analysis.update({
                "form_embedding": form_embedding.tolist(),
                "context_embedding": context_embedding.tolist(),
                "provider": self._current_provider
            })
            self.context_cache[cache_key] = analysis
            return analysis

        except Exception as e:
            logger.error(f"Lỗi phân tích ngữ cảnh với {self._current_provider}: {e}")

            if not tried_fallback and self._current_provider == 'openai':
                try:
                    api_key_manager = get_api_key_manager()
                    fallback_provider = api_key_manager.get_available_provider('gemini')
                    if fallback_provider:
                        self._current_provider = fallback_provider
                        self._client = api_key_manager.get_client(fallback_provider)
                        return self._enhance_context_analysis(form_text, context, tried_fallback=True)
                except Exception as e2:
                    logger.error(f"Failed to switch to Gemini: {e2}")

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
    def _build_enhanced_context_for_gemini(
    self,
    field_name: str,
    historical_values: List[str],
    context: Optional[str],
    form_type: Optional[str],
    related_fields_data: Optional[Dict]
) -> str:
        """Build enhanced context for Gemini with historical patterns and field relationships"""
        context_parts = []
        
        if context:
            context_parts.append(f"## Ngữ cảnh chính:\n{context}")
        
        if form_type:
            context_parts.append(f"## Loại biểu mẫu:\n{form_type}")
        
        # Analyze historical value patterns
        if historical_values:
            value_patterns = self._analyze_value_patterns(historical_values)
            context_parts.append(f"## Mẫu giá trị lịch sử:\n{value_patterns}")
        
        # Add related fields information
        if related_fields_data:
            related_info = "\n".join([f"- {k}: {v}" for k, v in related_fields_data.items()])
            context_parts.append(f"## Trường liên quan:\n{related_info}")
        
        # Add field name analysis
        name_analysis = self._analyze_field_name(field_name)
        if name_analysis:
            context_parts.append(f"## Phân tích tên trường:\n{name_analysis}")
        
        return "\n\n".join(context_parts)

    def _analyze_value_patterns(self, values: List[str]) -> str:
        """Analyze patterns in historical values"""
        
        try:
            date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YY hoặc DD-MM-YYYY
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',     # YYYY/MM/DD
            r'\d{1,2}\s+[Tháng|tháng]\s+\d{4}'  # 15 Tháng 5 2023
            ]
            
            date_count = sum(
                1 for v in values 
                if any(re.match(p, v) for p in date_patterns)
            )
            # Simple pattern detection
            
            email_count = sum(1 for v in values if '@' in v)
            numeric_count = sum(1 for v in values if v.isdigit())
            
            patterns = []
            if date_count > len(values)/2:
                patterns.append("Giá trị chủ yếu là ngày tháng")
            if email_count > len(values)/2:
                patterns.append("Giá trị chủ yếu là email")
            if numeric_count > len(values)/2:
                patterns.append("Giá trị chủ yếu là số")
            
            if not patterns:
                unique_ratio = len(set(values))/len(values)
                if unique_ratio < 0.5:
                    patterns.append("Nhiều giá trị trùng lặp")
                else:
                    patterns.append("Giá trị đa dạng, không có mẫu rõ ràng")
            
            return "; ".join(patterns)
        except:
            return "Không thể phân tích mẫu giá trị"

    def _analyze_field_name(self, field_name: str) -> str:
        """Analyze field name for semantic meaning"""
        name_lower = field_name.lower()
        
        # Common field types detection
        field_types = {
            'tên': 'Họ tên cá nhân',
            'email': 'Địa chỉ email',
            'ngày': 'Ngày tháng',
            'điện thoại': 'Số điện thoại',
            'địa chỉ': 'Địa chỉ nhà',
            'thành phố': 'Tên thành phố',
            'công ty': 'Tên công ty'
        }
        
        for keyword, description in field_types.items():
            if keyword in name_lower:
                return description
        
        return ""
    def _build_advanced_gemini_suggestion_prompt(
    self,
    field_name: str,
    similar_fields: List[str],
    historical_values: List[str],
    context: Optional[str],
    related_fields: str
) -> str:
        """Construct advanced suggestion prompt optimized for Gemini"""
        prompt_parts = [
            "Bạn là trợ lý thông minh đề xuất giá trị cho biểu mẫu. Hãy phân tích kỹ các thông tin sau:",
            f"### TRƯỜNG CẦN ĐỀ XUẤT: '{field_name}'",
        ]
        
        if similar_fields:
            prompt_parts.append(f"### CÁC TRƯỜNG TƯƠNG TỰ:\n{', '.join(similar_fields)}")
        
        if historical_values:
            prompt_parts.append(
                f"### GIÁ TRỊ LỊCH SỬ (10 mẫu gần nhất):\n" + 
                "\n".join([f"- {v}" for v in historical_values[:10]])
            )
        
        if context:
            prompt_parts.append(f"### NGỮ CẢNH PHÂN TÍCH:\n{context}")
        
        if related_fields:
            prompt_parts.append(f"### TRƯỜNG LIÊN QUAN VÀ GIÁ TRỊ:\n{related_fields}")
        
        prompt_parts.extend([
            "\n### YÊU CẦU:",
            "1. Tạo 3 đề xuất giá trị phù hợp nhất cho trường này",
            "2. Chọn 1 giá trị mặc định tốt nhất",
            "3. Giải thích ngắn gọn lý do cho các đề xuất",
            "",
            "### ĐỊNH DẠNG ĐẦU RA (JSON):",
            '''{
                "suggestions": [
                    {
                        "text": "giá trị 1",
                        "reason": "lý do phù hợp với ngữ cảnh và lịch sử"
                    },
                    ...
                ],
                "default": "giá trị mặc định tốt nhất",
                "reason": "giải thích lựa chọn"
            }''',
            "",
            "Chỉ trả về JSON hợp lệ, không có nội dung nào khác."
        ])
        
        return "\n".join(prompt_parts)

    def _parse_gemini_suggestion_response(self, content: str) -> Dict[str, Any]:
        """Parse Gemini suggestion response with enhanced error handling"""
        try:
            # Try direct JSON parse first
            result = json.loads(content)
        except json.JSONDecodeError:
            try:
                # Handle cases where response might have markdown code block
                json_match = re.search(r'```json\s*({.*?})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # Fallback to extracting just the JSON part
                    json_match = re.search(r'{.*}', content, re.DOTALL)
                    result = json.loads(json_match.group(0)) if json_match else {}
            except Exception as e:
                logger.error(f"Error parsing Gemini response: {e}")
                result = {}
        
        # Validate and normalize the response
        if not isinstance(result, dict):
            result = {}
        
        suggestions = result.get("suggestions", [])
        if not isinstance(suggestions, list):
            suggestions = []
        
        return {
            "suggestions": suggestions[:3],
            "default": result.get("default", suggestions[0]["text"] if suggestions else ""),
            "reason": result.get("reason", "")
        }
    def generate_suggestions(
    self,
    field_name: str,
    historical_values: List[str],
    context: Optional[str] = None,
    form_type: Optional[str] = None,
    related_fields_data: Optional[Dict] = None
) -> Dict[str, Any]:
        """Generate smart suggestions for form field with enhanced Gemini integration"""
        name_lower = field_name.lower()
        if self._is_date_field(field_name):
            today = datetime.datetime.now()

            # Tránh nhầm với ngày sinh, tháng sinh, năm sinh
            if "sinh" not in name_lower:
                if "ngày" in name_lower:
                    suggestion = today.strftime("%d")
                    return {
                        "suggestions": [{"text": suggestion, "reason": "Ngày hiện tại"}],
                        "default": suggestion,
                        "reason": "Tự động điền ngày hiện tại"
                    }
                elif "tháng" in name_lower:
                    suggestion = today.strftime("%m")
                    return {
                        "suggestions": [{"text": suggestion, "reason": "Tháng hiện tại"}],
                        "default": suggestion,
                        "reason": "Tự động điền tháng hiện tại"
                    }
                elif "năm" in name_lower:
                    suggestion = today.strftime("%Y")
                    return {
                        "suggestions": [{"text": suggestion, "reason": "Năm hiện tại"}],
                        "default": suggestion,
                        "reason": "Tự động điền năm hiện tại"
                    }

        cache_key = f"{field_name}_{hash(str(historical_values))}_{hash(context) if context else ''}"
        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key]

        try:
            if self._client is None or self._current_provider is None:
                api_key_manager = get_api_key_manager()
                self._current_provider = api_key_manager.get_available_provider('gemini') or api_key_manager.get_available_provider('openai')
                if self._current_provider is None:
                    raise RuntimeError("No available AI provider")
                self._client = api_key_manager.get_client(self._current_provider)

            similar_fields = self.find_similar_fields(field_name)
            related_fields = self._get_related_fields(field_name, similar_fields, related_fields_data)

            enhanced_context = self._build_enhanced_context_for_gemini(
                field_name,
                historical_values,
                context,
                form_type,
                related_fields_data
            )

            if self._current_provider == 'gemini':
                prompt = self._build_advanced_gemini_suggestion_prompt(
                    field_name,
                    similar_fields,
                    historical_values,
                    enhanced_context,
                    related_fields
                )

                if not hasattr(self._client, 'generate_content'):
                    from google.generativeai import GenerativeModel
                    self._client = GenerativeModel("gemini-1.5-pro")

                response = self._client.generate_content(
                    contents=[{"role": "user", "parts": [prompt]}],
                    generation_config={
                        "temperature": 0.5,
                        "max_output_tokens": 500,
                        "top_p": 0.9
                    }
                )
                content = response.candidates[0].content.parts[0].text.strip()
                suggestions = self._parse_gemini_suggestion_response(content)
            else:
                prompt = self._build_openai_suggestion_prompt(
                    field_name,
                    similar_fields,
                    historical_values,
                    enhanced_context,
                    related_fields
                )
                response = self._client.chat.completions.create(
                    model="gpt-4-1106-preview",
                    messages=[
                        {"role": "system", "content": "Smart form suggestion assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=400,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content.strip()
                suggestions = self._parse_suggestion_response(content)

            self.suggestion_cache[cache_key] = suggestions
            return suggestions

        except Exception as e:
            logger.error(f"Error generating suggestions with {self._current_provider}: {e}")
            return {"suggestions": [], "default": "", "reason": str(e)}

    

    def _is_date_field(self, field_name: str) -> bool:
            """Kiểm tra tên trường có thể là ngày/tháng/năm hiện tại (nhưng không phải ngày sinh, tháng sinh, năm sinh)"""
            if not field_name or not isinstance(field_name, str):
                return False

            name_lower = field_name.lower()
            # Mở rộng danh sách từ khóa để nhận diện tốt hơn
            date_keywords = ["ngày", "tháng", "năm", "date", "day", "month", "year", "thời gian", "time"]
            birth_keywords = ["sinh", "birth", "dob", "tuổi", "age"]
            
            # Từ khóa chỉ ngày hiện tại
            current_date_keywords = ["hiện tại", "hôm nay", "hiện nay", "today", "current", "lập", "ký", "viết", "làm"]
            
            contains_date_part = any(kw in name_lower for kw in date_keywords)
            contains_birth_info = any(kw in name_lower for kw in birth_keywords)
            contains_current_date = any(kw in name_lower for kw in current_date_keywords)
            
            # Thêm nhận diện mẫu như "dd/mm/yyyy", "mm/dd/yyyy", v.v.
            contains_date_pattern = bool(re.search(r'dd|mm|yyyy|yy', name_lower))
            
            # Nếu chứa từ khóa ngày hiện tại, ưu tiên xác định là trường ngày hiện tại
            if contains_current_date and contains_date_part:
                return True
                
            # Nếu chứa từ khóa ngày tháng nhưng không chứa từ khóa sinh
            return (contains_date_part or contains_date_pattern) and not contains_birth_info


    def _build_gemini_suggestion_prompt(
        self,
        field_name: str,
        similar_fields: List[str],
        historical_values: List[str],
        context: Optional[str],
        related_fields: str
    ) -> str:
        """Construct suggestion prompt optimized for Gemini"""
        if self._is_date_field(field_name):
            today_str = datetime.datetime.now().strftime("%d/%m/%Y")
            return json.dumps({
                "suggestions": [
                    {"text": today_str, "reason": "Ngày hiện tại theo định dạng DD/MM/YYYY"},
                    {"text": today_str.replace("/", "-"), "reason": "Ngày hiện tại theo định dạng DD-MM-YYYY"},
                    {"text": datetime.datetime.now().strftime("%Y-%m-%d"), "reason": "Ngày hiện tại theo định dạng quốc tế"}
                ],
                "default": today_str,
                "reason": "Tự động điền ngày hiện tại cho trường ngày tháng"
            }, ensure_ascii=False)
        prompt_parts = [
            "Bạn là trợ lý đề xuất thông minh cho biểu mẫu.",
            f"Trường: '{field_name}'",
            f"Các trường tương tự: {', '.join(similar_fields) if similar_fields else 'Không có'}",
        ]
        
        if historical_values:
            prompt_parts.append(f"\nLịch sử giá trị:\n- " + "\n- ".join(historical_values[:10]))
        
        if context:
            prompt_parts.append(f"\nNgữ cảnh:\n{context}")
        
        if related_fields:
            prompt_parts.append(related_fields)
        if self._is_date_field(field_name):
            today_str = datetime.datetime.today().strftime("%d/%m/%Y")
            return json.dumps({
                "suggestions": [
                    {"text": today_str, "reason": "Đây là ngày hiện tại."},
                    {"text": today_str, "reason": "Tự động điền theo ngày hôm nay."},
                    {"text": today_str, "reason": "Gợi ý mặc định cho trường ngày."}
                ],
                "default": today_str
            }, ensure_ascii=False)
        prompt_parts.extend([
            "\nHãy tạo 3 đề xuất khác nhau ở định dạng JSON:",
            "```json",
            "{\"suggestions\": [{\"text\": \"đề xuất 1\", \"reason\": \"...\"}, ...],",
            "\"default\": \"giá trị mặc định tốt nhất\"}",
            "```",
            "\nChỉ trả về JSON, không có nội dung nào khác."
        ])
        
        return "\n".join(prompt_parts)
    
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
    def _build_gemini_rewrite_prompt(
    self,
    field_name: str,
    similar_fields: List[str],
    user_input: str,
    context: Optional[str]
) -> str:
        """Build rewrite prompt for Gemini"""
        prompt = [
            "Cải thiện đầu vào biểu mẫu với các yêu cầu:",
            "1. Đúng ngữ pháp",
            "2. Phù hợp với trường dữ liệu",
            "3. Trình bày chuyên nghiệp",
            "4. Giữ nguyên ý nghĩa gốc",
            "",
            f"Trường: '{field_name}'",
            f"Các trường tương tự: {', '.join(similar_fields) if similar_fields else 'Không có'}",
            f"Đầu vào: \"{user_input}\""
        ]
        
        if context:
            prompt.append(f"\nNgữ cảnh:\n{context}")
        
        prompt.append("\nChỉ trả về văn bản đã được cải thiện, không có nội dung nào khác.")
        
        return "\n".join(prompt)
    def rewrite_user_input(self, field_name: str, user_input: str, context: Optional[str] = None) -> str:
        """Improve user input for form field with proper provider fallback"""
        if not user_input:
            return ""
        
        try:
            similar_fields = self.find_similar_fields(field_name)
            
            # Xác định provider hiện tại hoặc khởi tạo mới
            if self._client is None or self._current_provider is None:
                api_key_manager = get_api_key_manager()
                self._current_provider = api_key_manager.get_available_provider('openai')
                if self._current_provider is None:
                    raise RuntimeError("No available AI provider")
                self._client = api_key_manager.get_client(self._current_provider)
            
            if self._current_provider == 'openai':
                prompt = self._build_openai_rewrite_prompt(field_name, similar_fields, user_input, context)
                model_name = "gpt-4-1106-preview"
                
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Form input improvement assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                improved_text = response.choices[0].message.content.strip()
            else:  # Gemini
                prompt = self._build_gemini_rewrite_prompt(field_name, similar_fields, user_input, context)
                from google.generativeai import GenerativeModel

                if not isinstance(self.client, GenerativeModel):
                    self._client = GenerativeModel("gemini-2.0-flash")  # Đảm bảo sử dụng gemini-2.0-flash
                
                response = self.client.generate_content(
                    model=model_name,
                    contents=[
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ],
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 200,
                    }
                )
                improved_text = response.text.strip()
            
            return improved_text.strip('"')
            
        except Exception as e:
            logger.error(f"Error rewriting input with {self._current_provider}: {e}")
            
            # Thử chuyển đổi provider nếu có lỗi
            if self._current_provider == 'openai':
                try:
                    api_key_manager = get_api_key_manager()
                    if api_key_manager.get_available_provider('gemini'):
                        self._client = None  # Reset client
                        self._current_provider = None  # Reset provider
                        logger.info("Attempting to switch to Gemini provider")
                        return self.rewrite_user_input(field_name, user_input, context)
                except Exception as e2:
                    logger.error(f"Failed to switch to Gemini: {e2}")
            
            return user_input  # Trả về input gốc nếu không thể cải thiện
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
    def _determine_best_default(
        self,
        sorted_entries: List[Dict],
        matched_fields: List[str],
        ai_suggestion: Dict[str, Any]
    ) -> str:
        """Determine the best default value from history or AI suggestion"""
        # First try to get from most recent form
        if sorted_entries and matched_fields:
            latest_form = sorted_entries[0].get("form_data", {})
            for field in matched_fields:
                if field in latest_form:
                    val = str(latest_form[field]).strip()
                    if val:
                        return val
        
        # Fallback to AI suggestion
        ai_default = ai_suggestion.get("default", "")
        if ai_default:
            return ai_default
        
        # Fallback to most common historical value
        if ai_suggestion.get("suggestions", []):
            return ai_suggestion["suggestions"][0]["text"]
        
        return ""
    def generate_personalized_suggestions(
    self,
    db_data: List[Dict],
    user_id: str,
    field_code: Optional[str] = None,
    field_name: Optional[str] = None,
    context: Optional[str] = None,
    form_type: Optional[str] = None
) -> Dict[str, Any]:
        """Generate personalized suggestions with enhanced context understanding"""
        # Kiểm tra nếu là trường ngày tháng năm hiện tại
        target_field = field_name or field_code or ""
        
        # Nếu là trường ngày tháng năm (không phải ngày sinh), ưu tiên sử dụng ngày hiện tại
        if self._is_date_field(target_field):
            today = datetime.datetime.now()
            name_lower = target_field.lower()
            
            # Xác định định dạng phù hợp dựa trên loại biểu mẫu
            date_format = "%d/%m/%Y"  # Định dạng mặc định
            
            # Điều chỉnh định dạng dựa trên loại biểu mẫu
            if form_type:
                form_type_lower = form_type.lower()
                if "quốc tế" in form_type_lower or "international" in form_type_lower:
                    date_format = "%Y-%m-%d"
                elif "hợp đồng" in form_type_lower or "contract" in form_type_lower:
                    date_format = "ngày %d tháng %m năm %Y"
            
            # Xác định loại trường ngày tháng
            if "ngày" in name_lower and not any(kw in name_lower for kw in ["tháng", "năm"]):
                default_value = today.strftime("%d")
                reason = "Tự động điền ngày hiện tại"
            elif "tháng" in name_lower and not any(kw in name_lower for kw in ["ngày", "năm"]):
                default_value = today.strftime("%m")
                reason = "Tự động điền tháng hiện tại"
            elif "năm" in name_lower and not any(kw in name_lower for kw in ["ngày", "tháng"]):
                default_value = today.strftime("%Y")
                reason = "Tự động điền năm hiện tại"
            else:
                # Trường hợp ngày tháng năm đầy đủ
                default_value = today.strftime(date_format)
                reason = "Tự động điền ngày hiện tại theo định dạng phù hợp"
            
            # Tạo các gợi ý khác nhau cho trường ngày tháng
            suggestions = [
                {"text": default_value, "reason": reason}
            ]
            
            # Thêm các định dạng khác nhau
            if "ngày" in name_lower and "tháng" in name_lower and "năm" in name_lower:
                suggestions.extend([
                    {"text": today.strftime("%d/%m/%Y"), "reason": "Ngày hiện tại (DD/MM/YYYY)"},
                    {"text": today.strftime("%Y-%m-%d"), "reason": "Ngày hiện tại (YYYY-MM-DD)"}
                ])
            
            return {
                "ai_suggestion": {
                    "suggestions": suggestions,
                    "default": default_value,
                    "reason": reason
                },
                "recent_values": [default_value],
                "default_value": default_value,
                "matched_fields": [target_field],
                "related_fields_data": {},
                "reason": reason,
                "field_mapping": {
                    "requested_field_code": field_code,
                    "matched_field_name": target_field,
                    "similarity_score": 1.0,
                    "similar_fields": [],
                    "is_exact_match": True
                },
                "context_used": f"Trường ngày tháng năm hiện tại: {target_field}"
            }
        
        # Xử lý các trường không phải ngày tháng năm như bình thường
        # Filter and sort user's historical entries
        filtered_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id) and
            (form_type is None or entry.get("form_data", {}).get("form_type") == form_type)
        ]
        sorted_entries = sorted(filtered_entries, key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Enhanced context extraction
        enhanced_context = self._build_personalized_context(
            sorted_entries, 
            field_code, 
            field_name, 
            context, 
            form_type
        )
        
        # Field matching with similarity scoring
        field_mapping = self._match_field_with_history(
            sorted_entries, 
            field_code, 
            field_name
        )
        
        # Collect historical values and related data
        value_collection = self._collect_historical_values(
            sorted_entries,
            field_mapping['matched_field_name'],
            field_mapping['similar_fields']
        )
        
        # Generate AI suggestions with enhanced context
        ai_suggestion = self.generate_suggestions(
            field_name=field_mapping['matched_field_name'],
            historical_values=value_collection['recent_values'],
            context=enhanced_context,
            form_type=form_type,
            related_fields_data=value_collection['related_fields_data']
        )
        
        # Determine default value
        default_value = self._determine_best_default(
            sorted_entries,
            value_collection['matched_fields'],
            ai_suggestion
        )
        
        return {
            "ai_suggestion": ai_suggestion,
            "recent_values": value_collection['recent_values'],
            "default_value": default_value,
            "matched_fields": value_collection['matched_fields'],
            "related_fields_data": value_collection['related_fields_data'],
            "reason": ai_suggestion.get("reason", ""),
            "field_mapping": field_mapping,
            "context_used": enhanced_context[:500] + "..." if len(enhanced_context) > 500 else enhanced_context
        }

    def _build_personalized_context(
        self,
        sorted_entries: List[Dict],
        field_code: str,
        field_name: str,
        context: str,
        form_type: str
    ) -> str:
        """Build personalized context from user's form history"""
        context_parts = []
        
        if context:
            context_parts.append(f"## Ngữ cảnh chính:\n{context}")
        
        if form_type:
            context_parts.append(f"## Loại biểu mẫu:\n{form_type}")
        
        # Add recent form data patterns
        if sorted_entries:
            recent_forms_text = "\n".join([
                json.dumps(entry.get("form_data", {}), ensure_ascii=False)
                for entry in sorted_entries[:3]  # Use last 3 forms
            ])
            context_parts.append(f"## Mẫu biểu mẫu gần đây:\n{recent_forms_text[:2000]}...")
        
        # Add field-specific context
        if field_code or field_name:
            target_field = field_name or field_code
            context_parts.append(f"## Phân tích trường '{target_field}':")
            
            # Get field statistics
            stats = self.get_field_statistics(target_field)
            if stats['similar_fields']:
                context_parts.append(f"- Các trường tương tự: {', '.join(stats['similar_fields'])}")
            if stats['related_fields']:
                context_parts.append(f"- Các trường liên quan: {', '.join(stats['related_fields'])}")
        
        return "\n\n".join(context_parts)

    def _match_field_with_history(
        self,
        sorted_entries: List[Dict],
        field_code: str,
        field_name: str
    ) -> Dict[str, Any]:
        """Match field with user's historical data"""
        best_similarity = 0
        best_field_name = field_name or field_code or "unknown"
        matched_fields = set()
        
        if field_code and not field_name:
            # Find best matching field name from history
            for entry in sorted_entries:
                form_data = entry.get("form_data", {})
                
                # Check for exact match first
                if field_code in form_data:
                    best_field_name = field_code
                    best_similarity = 1.0
                    matched_fields.add(field_code)
                    break
                
                # Find similar fields
                for key in form_data.keys():
                    similarity = self._calculate_field_similarity(field_code, key)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_field_name = key
                        matched_fields.add(key)
                    
                    if best_similarity >= 0.8:  # Good enough match
                        break
                
                if best_similarity >= 0.8:
                    break
        
        elif field_name:
            # Calculate similarity with provided field name
            if field_code:
                best_similarity = self._calculate_field_similarity(field_code, field_name)
            matched_fields.add(field_name)
        
        # Get similar fields for the best match
        similar_fields = self.find_similar_fields(best_field_name)
        
        return {
            "requested_field_code": field_code,
            "matched_field_name": best_field_name,
            "similarity_score": round(best_similarity, 3),
            "similar_fields": similar_fields,
            "is_exact_match": best_similarity == 1.0
        }

    def _collect_historical_values(
        self,
        sorted_entries: List[Dict],
        field_name: str,
        similar_fields: List[str]
    ) -> Dict[str, Any]:
        """Collect historical values and related data"""
        recent_values = []
        matched_fields = set()
        related_fields_data = {}
        
        # Get related fields
        related_fields = self._get_related_field_names(field_name, similar_fields)
        
        for entry in sorted_entries:
            form_data = entry.get("form_data", {})
            
            # Collect values from main field and similar fields
            for f in [field_name] + similar_fields:
                if f in form_data and form_data[f]:
                    val = str(form_data[f]).strip()
                    if val and val not in recent_values:
                        recent_values.append(val)
                        matched_fields.add(f)
            
            # Collect related fields data
            for rel_field in related_fields:
                if rel_field in form_data and form_data[rel_field]:
                    related_fields_data[rel_field] = form_data[rel_field]
            
            if len(recent_values) >= 10:  # Limit to 10 most recent values
                break
        
        return {
            "recent_values": recent_values,
            "matched_fields": list(matched_fields),
            "related_fields_data": related_fields_data
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