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
import numpy as np

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

    def _build_openai_rewrite_prompt(
    self,
    field_name: str,
    similar_fields: List[str],
    user_input: str,
    context: Optional[str],
    is_selected_value: bool = False,
    form_type: Optional[str] = None
) -> str:
        """Build OpenAI rewrite prompt for concise, professional Vietnamese output"""
        prompt = [
            "Bạn là một trợ lý chuyên nghiệp giúp cải thiện nội dung nhập liệu cho biểu mẫu bằng tiếng Việt.",
            "Hãy viết lại nội dung nhập liệu với các yêu cầu sau:",
            "- Đúng ngữ pháp và chuẩn tiếng Việt.",
            "- Phù hợp với trường dữ liệu, ngắn gọn và chuyên nghiệp.",
            "- Giữ ý nghĩa gốc, cải thiện sự rõ ràng và trang trọng.",
            "- Chỉ trả về nội dung đã cải thiện, không bao gồm tên trường hoặc metadata.",
            "- Tránh lặp lại thông tin không cần thiết, tập trung vào giá trị chính.",
            "- Đảm bảo kết quả bằng tiếng Việt."
        ]

        if is_selected_value:
            prompt.append("- Giá trị lịch sử đã chọn cần được tối ưu hóa để rõ ràng, chuyên nghiệp hơn, giữ nguyên ý nghĩa.")

        if form_type:
            prompt.append(f"- Loại biểu mẫu: {form_type} (Điều chỉnh phong cách viết cho phù hợp).")

        prompt.extend([
            "",
            f"Tên trường: '{field_name}' (chỉ dùng để hiểu ngữ cảnh, không đưa vào kết quả).",
            f"Các trường liên quan: {', '.join(similar_fields) if similar_fields else 'Không có'}.",
            f"Nội dung nhập liệu: \"{user_input}\""
        ])

        if context:
            prompt.append(f"Ngữ cảnh biểu mẫu: {context}")

        prompt.append("\nChỉ trả về văn bản đã cải thiện, không thêm giải thích hoặc ghi chú.")

        return "\n".join(prompt)
    
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
        
        # Thêm phân tích ngữ nghĩa biểu mẫu để xác định loại biểu mẫu chính xác hơn
        form_keywords = {
            "đơn xin việc": "job_application",
            "sơ yếu lý lịch": "resume",
            "hợp đồng": "contract",
            "đăng ký": "registration",
            "khảo sát": "survey",
            "đơn hàng": "order",
            "thanh toán": "payment",
            "bảo hiểm": "insurance",
            "khai báo": "declaration",
            "giấy phép": "license"
        }
        
        form_type = None
        for keyword, form_code in form_keywords.items():
            if keyword in context_lower or keyword in form_text.lower():
                form_type = form_code
                break
        
        cache_key = hashlib.sha256(form_text.encode()).hexdigest()
        if cache_key in self.context_cache:
            cached_analysis = self.context_cache[cache_key]
            if form_type and 'form_type' not in cached_analysis:
                cached_analysis['form_type'] = form_type
            return cached_analysis
        
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

    def _build_gemini_rewrite_prompt(
    self,
    field_name: str,
    similar_fields: List[str],
    user_input: str,
    context: Optional[str],
    is_selected_value: bool = False,
    form_type: Optional[str] = None
) -> str:
        """Build Gemini rewrite prompt for concise, professional Vietnamese output"""
        prompt = [
            "Bạn là một trợ lý chuyên nghiệp giúp cải thiện nội dung nhập liệu cho biểu mẫu bằng tiếng Việt.",
            "Hãy viết lại nội dung nhập liệu với các yêu cầu sau:",
            "- Đúng ngữ pháp và chuẩn tiếng Việt.",
            "- Phù hợp với trường dữ liệu, ngắn gọn và chuyên nghiệp.",
            "- Giữ ý nghĩa gốc, cải thiện sự rõ ràng và trang trọng.",
            "- Chỉ trả về nội dung đã cải thiện, không bao gồm tên trường hoặc metadata.",
            "- Tránh lặp lại thông tin không cần thiết, tập trung vào giá trị chính.",
            "- Đảm bảo kết quả bằng tiếng Việt."
            "- Làm cho nó tự nhiên và phù hợp với ngữ cảnh",
            "- Có thể thêm thông tin liên quan nếu cần thiết"
        ]

        if is_selected_value:
            prompt.append("- Giá trị lịch sử đã chọn cần được tối ưu hóa để rõ ràng, chuyên nghiệp hơn, giữ nguyên ý nghĩa.")

        if form_type:
            prompt.append(f"- Loại biểu mẫu: {form_type} (Điều chỉnh phong cách viết cho phù hợp).")

        prompt.extend([
            "",
            f"Tên trường: '{field_name}' (chỉ dùng để hiểu ngữ cảnh, không đưa vào kết quả).",
            f"Các trường liên quan: {', '.join(similar_fields) if similar_fields else 'Không có'}.",
            f"Nội dung nhập liệu: \"{user_input}\""
        ])

        if context:
            prompt.append(f"Ngữ cảnh biểu mẫu: {context}")

        prompt.append("\nChỉ trả về văn bản đã cải thiện, không thêm giải thích hoặc ghi chú.")

        return "\n".join(prompt)
    def _analyze_personal_info(self, field_name: str, historical_values: List[str]) -> Dict[str, Any]:
            """Phân tích và nhận diện thông tin cá nhân nâng cao"""
            name_lower = field_name.lower()
            
            # Danh sách các trường thông tin cá nhân phổ biến
            personal_fields = {
                "họ tên": ["họ và tên", "họ tên", "tên", "name", "full name"],
                "địa chỉ": ["địa chỉ", "address", "nơi ở", "chỗ ở", "địa chỉ thường trú", "địa chỉ tạm trú"],
                "email": ["email", "thư điện tử", "mail", "e-mail", "địa chỉ email"],
                "số điện thoại": ["điện thoại", "phone", "số điện thoại", "di động", "mobile", "tel", "số di động"],
                "cmnd": ["cmnd", "cccd", "căn cước", "chứng minh", "id card", "identity", "số cmnd", "số căn cước"],
                "ngày sinh": ["ngày sinh", "sinh ngày", "birthday", "date of birth", "dob", "ngày tháng năm sinh"],
                "giới tính": ["giới tính", "gender", "sex", "nam/nữ", "nam nữ"],
                "quốc tịch": ["quốc tịch", "nationality", "quốc gia", "công dân"],
                "nghề nghiệp": ["nghề nghiệp", "nghề", "công việc", "occupation", "job", "profession", "chức vụ", "vị trí"],
                "học vấn": ["học vấn", "trình độ", "bằng cấp", "education", "degree", "trình độ học vấn"],
                "tôn giáo": ["tôn giáo", "religion", "đạo"],
                "dân tộc": ["dân tộc", "ethnicity", "ethnic"],
                "mã số thuế": ["mã số thuế", "tax", "tax code", "tax id", "mst"],
                "số tài khoản": ["số tài khoản", "tài khoản", "account", "account number", "stk", "bank account"],
                "ngân hàng": ["ngân hàng", "bank", "tên ngân hàng", "chi nhánh"],
                "hộ chiếu": ["hộ chiếu", "passport", "số hộ chiếu"],
                "bảo hiểm": ["bảo hiểm", "bhyt", "bhxh", "insurance", "số bảo hiểm"]
            }
            
            # Kiểm tra trường có phải là thông tin cá nhân không
            for category, keywords in personal_fields.items():
                if any(keyword in name_lower for keyword in keywords):
                    # Phân tích giá trị lịch sử
                    value_analysis = {}
                    if historical_values:
                        value_analysis = {
                            "latest_value": historical_values[0],
                            "consistent": len(set(historical_values)) == 1,  # Kiểm tra tính nhất quán
                            "variations": list(set(historical_values)),
                            "frequency": Counter(historical_values).most_common()
                        }
                    
                    # Xác định mức độ nhạy cảm của thông tin
                    sensitivity = "medium"  # Mặc định
                    if category in ["cmnd", "số tài khoản", "email", "số điện thoại", "ngày sinh"]:
                        sensitivity = "high"
                    elif category in ["họ tên", "địa chỉ"]:
                        sensitivity = "medium"
                    else:
                        sensitivity = "low"
                    
                    return {
                        "is_personal": True,
                        "category": category,
                        "should_preserve": True,
                        "sensitivity": sensitivity,
                        "value_analysis": value_analysis,
                        "latest_value": historical_values[0] if historical_values else ""
                    }
            
            # Nếu không phải thông tin cá nhân đã biết
            return {
                "is_personal": False,
                "category": "other",
                "should_preserve": False,
                "latest_value": ""
            }
    def rewrite_user_input(
    self, 
    field_name: str, 
    user_input: str, 
    context: Optional[str] = None,
    form_type: Optional[str] = None,  # Added form_type parameter
    selected_value: Optional[str] = None
) -> str:
        """Improve user input with special handling for selected historical values"""
        if not user_input and not selected_value:
            return ""
            
        # Use selected_value if provided and user_input is empty
        input_to_improve = selected_value if (selected_value and not user_input) else user_input
        
        # Analyze field for specific handling
        personal_info = self._analyze_personal_info(field_name, [input_to_improve])
        
        try:
            similar_fields = self.find_similar_fields(field_name)
            
            # Initialize client if needed
            if self._client is None or self._current_provider is None:
                api_key_manager = get_api_key_manager()
                self._current_provider = api_key_manager.get_available_provider('openai') or api_key_manager.get_available_provider('gemini')
                if self._current_provider is None:
                    raise RuntimeError("Không có nhà cung cấp AI nào khả dụng")
                self._client = api_key_manager.get_client(self._current_provider)
            
            if self._current_provider == 'openai':
                prompt = self._build_openai_rewrite_prompt(
                    field_name, 
                    similar_fields, 
                    input_to_improve, 
                    context,
                    is_selected_value=(selected_value is not None),
                    form_type=form_type
                )
                
                response = self.client.chat.completions.create(
                    model="gpt-4-1106-preview",
                    messages=[
                        {"role": "system", "content": "Trợ lý cải thiện nội dung biểu mẫu bằng tiếng Việt."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                improved_text = response.choices[0].message.content.strip()
            else:  # Gemini
                prompt = self._build_gemini_rewrite_prompt(
                    field_name, 
                    similar_fields, 
                    input_to_improve, 
                    context,
                    is_selected_value=(selected_value is not None),
                    form_type=form_type
                )
                
                if not hasattr(self._client, 'generate_content'):
                    from google.generativeai import GenerativeModel
                    self._client = GenerativeModel("gemini-1.5-pro")
                
                response = self.client.generate_content(
                    contents=[{"role": "user", "parts": [{"text": prompt}]}],
                    generation_config={
                        "temperature": 0.3,
                        "max_output_tokens": 200,
                    }
                )
                improved_text = response.candidates[0].content.parts[0].text.strip()
            
            # Post-process to ensure no metadata
            improved_text = improved_text.strip('"')
            if personal_info.get("is_personal") and personal_info.get("category") == "học vấn":
                # Special handling for education fields
                improved_text = re.sub(r'^Bằng\s*', '', improved_text, flags=re.IGNORECASE).strip()
                improved_text = improved_text.replace("ngành", "").strip()
            
            return improved_text
        
        except Exception as e:
            logger.error(f"Lỗi khi viết lại nội dung: {e}")
            return input_to_improve  # Return original if improvement fails
    
    
    