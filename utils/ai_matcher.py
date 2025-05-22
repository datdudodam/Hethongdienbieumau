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

    def extract_context_from_form_text(self, form_text: str) -> str:
        """Extract context from form text with caching"""
        cache_key = hashlib.sha256(form_text.encode('utf-8')).hexdigest()
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
            self.context_cache[cache_key] = context
            self._analyze_form_context(form_text, context)
            return context
        except Exception as e:
            logger.error(f"Error extracting context: {str(e)}")
            return ""

    def _analyze_form_context(self, form_text: str, context: str):
        """Deep analyze form context"""
        try:
            cache_key = hash(form_text)
            if cache_key in self.form_context_analysis:
                return
                
            prompt = (
                "Based on form content and context:\n\n"
                f"Form:\n{form_text[:500]}...\n\n"
                f"Context:\n{context}\n\n"
                "Return JSON with:\n"
                "1. form_type\n"
                "2. important_fields\n"
                "3. field_relationships\n"
                "4. user_characteristics"
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": "Professional form analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                result = json.loads(json_match.group(1)) if json_match else {
                    "form_type": "unknown",
                    "important_fields": [],
                    "field_relationships": {},
                    "user_characteristics": "Unknown"
                }
            
            self.form_context_analysis[cache_key] = result
            logger.info(f"Form context analysis completed: {result.get('form_type')}")
        except Exception as e:
            logger.error(f"Error analyzing form context: {e}")

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

    def rewrite_user_input(
        self,
        field_name: str,
        user_input: str,
        context: Optional[str] = None,
        expected_length: Optional[int] = None
    ) -> str:
        """
        Phiên bản nâng cao của phương thức cải thiện đầu vào người dùng
        """
        if not user_input:
            return ""
        
        try:
            # Phân tích loại trường
            field_type = self._determine_field_type(field_name, user_input)
            
            prompt_parts = [
                f"Cải thiện đầu vào cho trường '{field_name}':",
                f"Loại trường: {field_type}",
                f"Đầu vào gốc: \"{user_input}\"",
            ]
            
            if context:
                prompt_parts.append(f"Ngữ cảnh: {context}")
            
            if expected_length:
                prompt_parts.append(f"Độ dài mong muốn: ~{expected_length} ký tự")
            
            prompt_parts.extend([
                "Yêu cầu cải thiện:",
                "1. Giữ nguyên ý chính",
                "2. Sửa lỗi ngữ pháp/chính tả",
                "3. Làm rõ nghĩa nếu cần",
                "4. Phù hợp với loại trường",
                "5. Giữ nguyên giọng văn của người dùng",
                "Chỉ trả về văn bản đã cải thiện, không thêm chú thích"
            ])
            
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
                temperature=0.4,
                max_tokens=500
            )
            
            improved = response.choices[0].message.content.strip()
            
            # Xử lý hậu kỳ
            return self._post_process_improved_text(
                improved, 
                field_type,
                expected_length
            )
            
        except Exception as e:
            logger.error(f"Error in advanced input rewriting: {e}")
            return user_input

    def _determine_field_type(self, field_name: str, example: str) -> str:
        """
        Xác định loại trường dựa trên tên và ví dụ
        """
        normalized_name = self._normalize_field_name(field_name)
        
        # Kiểm tra các từ khóa quan trọng
        if any(kw in normalized_name for kw in ["name", "ho ten", "ten"]):
            return "name"
        elif any(kw in normalized_name for kw in ["date", "ngay", "thoi gian"]):
            return "date"
        elif any(kw in normalized_name for kw in ["address", "dia chi"]):
            return "address"
        elif any(kw in normalized_name for kw in ["description", "mo ta", "content"]):
            return "free_text"
        elif len(example.split()) > 10 or len(example) > 100:
            return "free_text"
        elif re.match(r"\d{1,2}/\d{1,2}/\d{4}", example):
            return "date"
        else:
            return "short_text"
    def _get_enhanced_context(
        self,
        current_context: Optional[str],
        db_data: List[Dict],
        user_id: str,
        form_type: Optional[str]
    ) -> str:
        """
        Tăng cường ngữ cảnh hiện tại bằng cách kết hợp lịch sử người dùng và loại biểu mẫu
        """
        if current_context:
            return current_context

        recent_entries = [
            entry for entry in db_data
            if str(entry.get("user_id")) == str(user_id)
        ]

        if form_type:
            recent_entries = [
                e for e in recent_entries
                if e.get("form_data", {}).get("form_type") == form_type
            ]

        context_fragments = []
        for entry in recent_entries[-3:]:  # Lấy 3 biểu mẫu gần nhất
            form_data = entry.get("form_data", {})
            summary = "; ".join(
                f"{k}: {v}" for k, v in form_data.items()
                if k != "form_type" and v
            )
            if summary:
                context_fragments.append(f"Gần đây bạn đã điền: {summary}")

        return "\n".join(context_fragments) if context_fragments else "Không có ngữ cảnh rõ ràng từ lịch sử."

    def _find_best_matching_field(
        self,
        db_data: List[Dict],
        user_id: str,
        field_code: Optional[str],
        field_name: Optional[str],
        form_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tìm trường phù hợp nhất từ tên hoặc mã đã cho
        """
        field_candidates = set()
        
        for entry in db_data:
            if form_type and entry.get("form_data", {}).get("form_type") != form_type:
                continue
            for k in entry.get("form_data", {}).keys():
                field_candidates.add(k)

        def normalize(text: str) -> str:
            return text.lower().replace("_", "").replace(" ", "")

        target = normalize(field_code or field_name or "")
        best_field = None
        highest_score = -1

        for field in field_candidates:
            score = self._similarity_score(normalize(field), target)
            if score > highest_score:
                best_field = field
                highest_score = score

        similar_fields = [
            f for f in field_candidates if f != best_field and self._similarity_score(normalize(f), normalize(best_field)) > 0.8
        ]

        return {
            "best_field_name": best_field,
            "similar_fields": similar_fields,
            "match_score": highest_score
        }

    def _similarity_score(self, a: str, b: str) -> float:
        """
        Tính điểm tương đồng đơn giản giữa hai chuỗi
        """
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()
    def _analyze_data_patterns(self, values: List[str]) -> Dict:
        """
        Phân tích danh sách giá trị để tìm ra mẫu dữ liệu chung
        """
        if not values:
            return {}

        samples = values[:10] if len(values) > 10 else values
        prompt = (
            "Phân tích các giá trị sau và xác định mẫu dữ liệu chung (nếu có):\n"
            f"{samples}\n\n"
            "Trả về JSON với các trường:\n"
            "- pattern_type (enum: ['list', 'date', 'name', 'address', 'free_text', 'other'])\n"
            "- common_format (ví dụ: 'DD/MM/YYYY')\n"
            "- likely_purpose\n"
            "- sample_template"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"pattern_type": "other"}
    def _collect_relevant_data(
        self,
        db_data: List[Dict],
        user_id: str,
        field_name: str,
        similar_fields: List[str],
        form_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Thu thập dữ liệu liên quan cho trường đang xét, dựa trên lịch sử người dùng
        và các trường có tên tương đồng trong cùng loại form.
        """
        values = []
        matched_fields = set()

        for entry in db_data:
            if str(entry.get("user_id")) != str(user_id):
                continue

            form_data = entry.get("form_data", {})
            entry_form_type = form_data.get("form_type")
            if form_type and form_type != entry_form_type:
                continue

            for field, value in form_data.items():
                if not value:
                    continue
                norm_field = self._normalize_field_name(field)
                if norm_field == self._normalize_field_name(field_name) or norm_field in similar_fields:
                    values.append(str(value).strip())
                    matched_fields.add(field)

        return {
            "values": values,
            "matched_fields": list(matched_fields)
        }
    def _get_ai_suggestions(
    self,
    field_name: str,
    relevant_values: List[str],
    form_type: Optional[str] = None
) -> str:
            """
            Gửi prompt đến AI để gợi ý dữ liệu phù hợp dựa trên các giá trị lịch sử liên quan.
            """
            if not relevant_values:
                return ""

            context_text = "\n".join(f"- {v}" for v in relevant_values)
            form_type_text = f" thuộc loại biểu mẫu '{form_type}'" if form_type else ""

            prompt = (
                f"Dựa vào các giá trị sau đây đã từng được nhập cho trường '{field_name}'{form_type_text}:\n"
                f"{context_text}\n\n"
                f"Hãy đề xuất một giá trị phù hợp cho trường '{field_name}' để điền vào biểu mẫu."
            )

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Bạn là một trợ lý điền biểu mẫu thông minh."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                suggestion = response.choices[0].message.content.strip()
                return suggestion
            except Exception as e:
                print(f"Lỗi khi gọi AI: {e}")
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
        """
        Phiên bản nâng cao của phương thức gợi ý cá nhân hóa
        """
        # Phân tích lịch sử người dùng
        user_history = self._analyze_user_history(db_data, user_id)
        
        # Xác định ngữ cảnh nâng cao
        context = self._get_enhanced_context(context, db_data, user_id, form_type)
        
        # Tìm trường phù hợp nhất
        field_info = self._find_best_matching_field(
            db_data, user_id, field_code, field_name, form_type
        )
        field_name = field_info["best_field_name"]
        
        # Thu thập dữ liệu liên quan
        data_collection = self._collect_relevant_data(
            db_data, user_id, field_name, 
            field_info["similar_fields"], form_type
        )
        
        # Phân tích kiểu dữ liệu và mẫu
        data_patterns = self._analyze_data_patterns(data_collection["values"])
        
        # Tạo prompt thông minh
        prompt = self._build_intelligent_prompt(
            field_name,
            data_collection,
            context,
            form_type,
            user_history,
            data_patterns
        )
        
        # Gọi AI để nhận gợi ý
        ai_response = self._get_ai_suggestions(prompt, field_name)
        
        # Xử lý và tối ưu hóa kết quả
        return self._process_ai_response(
            ai_response,
            data_collection,
            field_info,
            user_history
        )

    def _analyze_user_history(self, db_data: List[Dict], user_id: str) -> Dict:
        """
        Phân tích sâu hành vi điền form của người dùng
        """
        user_entries = [e for e in db_data if str(e.get("user_id")) == str(user_id)]
        
        analysis = {
            "frequently_used_values": defaultdict(Counter),
            "common_patterns": {},
            "time_based_patterns": defaultdict(list),
            "form_type_preferences": Counter(),
            "response_length_stats": defaultdict(list)
        }
        
        for entry in user_entries:
            form_data = entry.get("form_data", {})
            timestamp = entry.get("timestamp")
            form_type = form_data.get("form_type")
            
            if form_type:
                analysis["form_type_preferences"][form_type] += 1
            
            for field, value in form_data.items():
                if not value:
                    continue
                
                # Phân tích giá trị thường dùng
                str_value = str(value).strip()
                analysis["frequently_used_values"][field][str_value] += 1
                
                # Phân tích độ dài phản hồi
                analysis["response_length_stats"][field].append(len(str_value))
                
                # Phân tích theo thời gian
                if timestamp:
                    analysis["time_based_patterns"][field].append((timestamp, str_value))
        
        # Xác định các mẫu phổ biến
        for field, counter in analysis["frequently_used_values"].items():
            if len(counter) > 3:
                analysis["common_patterns"][field] = self._detect_value_patterns(counter)
        
        return analysis

    def _detect_value_patterns(self, value_counter: Counter) -> Dict:
        """
        Phát hiện các mẫu trong giá trị trường
        """
        samples = [v for v, _ in value_counter.most_common(10)]
        
        # Phân tích bằng AI
        prompt = (
            "Phân tích các giá trị sau và xác định mẫu chung (nếu có):\n"
            f"{samples}\n\n"
            "Trả về JSON với các trường:\n"
            "- pattern_type (enum: ['list', 'date', 'name', 'address', 'free_text', 'other'])\n"
            "- common_format (ví dụ: 'DD/MM/YYYY' cho ngày tháng)\n"
            "- likely_purpose (dự đoán mục đích của trường)\n"
            "- sample_template (mẫu điển hình)"
        )
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"pattern_type": "other"}

    def _build_intelligent_prompt(
        self,
        field_name: str,
        data_collection: Dict,
        context: str,
        form_type: str,
        user_history: Dict,
        data_patterns: Dict
    ) -> str:
        """
        Xây dựng prompt thông minh cho AI
        """
        # Phân tích lịch sử cá nhân
        freq_values = user_history["frequently_used_values"].get(field_name, Counter())
        common_pattern = user_history["common_patterns"].get(field_name, {})
        
        prompt_parts = [
            f"Yêu cầu: Tạo gợi ý điền trường '{field_name}'",
            f"Loại form: {form_type}" if form_type else "",
            f"Ngữ cảnh: {context}" if context else "",
        ]
        
        # Thêm thông tin giá trị lịch sử
        if data_collection["values"]:
            prompt_parts.append("\nGiá trị lịch sử:")
            for val in data_collection["values"][:10]:
                prompt_parts.append(f"- {val}")
        
        # Thêm thông tin mẫu phát hiện
        if common_pattern:
            prompt_parts.append("\nMẫu phát hiện:")
            prompt_parts.append(f"- Kiểu: {common_pattern.get('pattern_type')}")
            if common_pattern.get("common_format"):
                prompt_parts.append(f"- Định dạng: {common_pattern['common_format']}")
            if common_pattern.get("likely_purpose"):
                prompt_parts.append(f"- Mục đích: {common_pattern['likely_purpose']}")
        
        # Thêm hướng dẫn cụ thể cho từng loại trường
        field_guidance = self._get_field_specific_guidance(field_name, data_patterns)
        prompt_parts.append(f"\nHướng dẫn điền trường:\n{field_guidance}")
        
        # Yêu cầu định dạng đầu ra
        prompt_parts.extend([
            "\nYêu cầu đầu ra:",
            "1. Gợi ý 3 giá trị phù hợp (độ dài khác nhau nếu là văn bản)",
            "2. Giá trị mặc định tốt nhất",
            "3. Giải thích ngắn gọn",
            "Định dạng JSON với các trường: suggestions, default, reason"
        ])
        
        return "\n".join(prompt_parts)

    def _get_field_specific_guidance(self, field_name: str, data_patterns: Dict) -> str:
        """
        Tạo hướng dẫn cụ thể cho từng loại trường
        """
        normalized_name = self._normalize_field_name(field_name)
        
        # Xác định loại trường từ tên và mẫu dữ liệu
        field_type = data_patterns.get("pattern_type", "")
        if not field_type:
            if any(kw in normalized_name for kw in ["name", "ho ten", "ten"]):
                field_type = "name"
            elif any(kw in normalized_name for kw in ["date", "ngay", "thoi gian"]):
                field_type = "date"
            elif any(kw in normalized_name for kw in ["address", "dia chi"]):
                field_type = "address"
            elif any(kw in normalized_name for kw in ["description", "mo ta"]):
                field_type = "free_text"
        
        # Tạo hướng dẫn cụ thể
        guidance = {
            "name": "Điền họ tên đầy đủ, viết hoa chữ cái đầu. Ví dụ: 'Nguyễn Văn A'",
            "date": "Định dạng ngày tháng theo DD/MM/YYYY. Ví dụ: '15/05/2023'",
            "address": "Theo thứ tự: Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành phố",
            "free_text": "Câu trả lời đầy đủ, rõ ràng, tối thiểu 2 câu. Có thể dùng bullet points nếu phù hợp",
            "default": "Điền thông tin chính xác, ngắn gọn, phù hợp với yêu cầu"
        }
        
        return guidance.get(field_type, guidance["default"])

    def _process_ai_response(
        self,
        ai_response: Dict,
        data_collection: Dict,
        field_info: Dict,
        user_history: Dict
    ) -> Dict:
        """
        Xử lý và tối ưu hóa phản hồi từ AI
        """
        # Kiểm tra và làm sạch phản hồi AI
        if not isinstance(ai_response, dict):
            ai_response = {"suggestions": [], "default": "", "reason": ""}
        
        # Bổ sung giá trị phổ biến từ lịch sử nếu cần
        freq_values = user_history["frequently_used_values"].get(field_info["best_field_name"], Counter())
        if freq_values and len(ai_response["suggestions"]) < 3:
            for val, _ in freq_values.most_common(3 - len(ai_response["suggestions"])):
                if val not in [s["text"] for s in ai_response["suggestions"]]:
                    ai_response["suggestions"].append({
                        "text": val,
                        "reason": "Giá trị thường dùng trước đây"
                    })
        
        # Đảm bảo có giá trị mặc định hợp lý
        if not ai_response.get("default") and data_collection["values"]:
            ai_response["default"] = data_collection["values"][0]
        
        return {
            "suggestions": ai_response.get("suggestions", [])[:3],
            "default_value": ai_response.get("default", ""),
            "recent_values": data_collection["values"],
            "matched_fields": data_collection["matched_fields"],
            "field_matching_info": field_info,
            "reason": ai_response.get("reason", "")
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