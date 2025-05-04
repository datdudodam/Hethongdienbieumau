import numpy as np
import re
import unicodedata
from typing import List, Dict, Optional, Tuple, Set, Union, Any
from collections import defaultdict, Counter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import logging

logger = logging.getLogger(__name__)

class EnhancedFieldMatcher:
    """
    Lớp nâng cao để so khớp tên trường và gợi ý giá trị dựa trên ngữ cảnh và lịch sử
    """
    def __init__(self, form_history_data=None):
        self.form_history_data = form_history_data or []
        self.field_name_cache = {}
        self.similarity_cache = {}  # Cache cho tính toán độ tương đồng
        self.processed_text_cache = {}  # Cache cho văn bản đã xử lý
        self.synonym_map = self._build_synonym_map()
        self.stop_words = self._initialize_stopwords()
        
        # Khởi tạo mô hình Sentence-BERT
        try:
            self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Đã khởi tạo mô hình Sentence-BERT thành công")
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo mô hình Sentence-BERT: {e}")
            self.sbert_model = None
    
    def _build_synonym_map(self) -> Dict[str, List[str]]:
        """
        Xây dựng bản đồ từ đồng nghĩa cho các trường phổ biến
        """
        raw_map = {
            'họ tên': [
                'hovaten', 'ho va ten', 'ho và tên', 'hoten', 'họ_tên', 'tên', 
                'họ và tên', 'fullname', 'full name', 'name', 'your name', 'tên đầy đủ'
            ],
            'địa chỉ': [
                'diachi', 'địa_chỉ', 'địa chỉ', 'address', 'place', 'location', 
                'home address', 'residence', 'chỗ ở', 'nơi ở', 'current address', 'address line'
            ],
            'điện thoại': [
                'sdt', 'so_dien_thoai', 'so dien thoai', 'đt', 'phone', 'tel', 
                'telephone', 'mobile', 'mobile phone', 'phone number', 'số điện thoại', 'contact number'
            ],
            'email': [
                'e-mail', 'mail', 'email address', 'email', 'địa chỉ email', 'thư điện tử'
            ],
            'ngày sinh': [
                "ngày sinh", "dob", "birth date", "birthdate", "date of birth", 
                "d.o.b", "ngay_sinh", "birth"
            ],
            'giới tính': [
                'gender', 'sex', 'gioi_tinh', 'gioi tinh', 'giới tính', 'male/female'
            ],
            'mã số thuế': [
                'tax code', 'mã thuế', 'mst', 'tax id'
            ],
            'quốc tịch': [
                'nationality', 'country'
            ],
            'thành phố': [
                'city', 'tỉnh thành', 'tỉnh/thành phố'
            ],
            'quận huyện': [
                'district', 'huyện', 'quận'
            ],
            'phường xã': [
                'ward', 'xã', 'phường'
            ],
            'chuyên nghành': [
                'học nghành', 'nghành'
            ],
            'chức vụ': [
                'position', 'title', 'job title', 'role', 'vai trò', 'vị trí'
            ],
            'công ty': [
                'company', 'organization', 'tổ chức', 'doanh nghiệp', 'cty', 'nơi làm việc'
            ],
            'lương': [
                'salary', 'income', 'thu nhập', 'mức lương', 'lương tháng', 'tiền lương'
            ],
            'kinh nghiệm': [
                'experience', 'exp', 'năm kinh nghiệm', 'thâm niên', 'số năm làm việc'
            ],
            'học vấn': [
                'education', 'qualification', 'bằng cấp', 'trình độ học vấn', 'trình độ'
            ],
            'ngày ký': [
                'date of signing', 'signing date', 'ngày ký kết', 'ngày ký hợp đồng', 'date'
            ]
        }
        return raw_map

    def _initialize_stopwords(self) -> Set[str]:
        """
        Khởi tạo stopwords cho cả tiếng Anh và tiếng Việt
        """
        vietnamese_stopwords = {
            'của', 'và', 'các', 'có', 'được', 'trong', 'là', 'cho', 'những', 'với',
            'không', 'này', 'đến', 'khi', 'về', 'như', 'từ', 'một', 'người', 'năm',
            'bị', 'đã', 'sẽ', 'cũng', 'vào', 'ra', 'nếu', 'để', 'tại', 'theo',
            'sau', 'trên', 'hoặc', 'tôi', 'bạn', 'anh', 'chị', 'họ', 'của', 'mình'
        }
        english_stopwords = {
            'the', 'and', 'a', 'to', 'of', 'in', 'is', 'that', 'for', 'on',
            'with', 'as', 'by', 'at', 'from', 'be', 'this', 'an', 'are', 'or',
            'was', 'it', 'but', 'not', 'have', 'had', 'has', 'i', 'you', 'he',
            'she', 'they', 'we', 'my', 'your', 'his', 'her', 'their', 'our'
        }
        return vietnamese_stopwords.union(english_stopwords)

    def _preprocess_text(self, text: str) -> str:
        """
        Tiền xử lý văn bản nâng cao cho tiếng Việt với caching
        """
        if not text:
            return ""
            
        # Kiểm tra cache trước
        if text in self.processed_text_cache:
            return self.processed_text_cache[text]
            
        # Chuẩn hóa Unicode và chuyển đổi về chữ thường
        normalized = unicodedata.normalize('NFC', text.lower())
        
        # Loại bỏ dấu câu và ký tự đặc biệt, giữ lại dấu tiếng Việt
        cleaned = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', normalized)
        
        # Thay thế từ đồng nghĩa phổ biến
        for target, synonyms in sorted(self.synonym_map.items(), key=lambda x: len(x[0]), reverse=True):
            for synonym in sorted(synonyms, key=len, reverse=True):
                if synonym in cleaned:
                    cleaned = cleaned.replace(synonym, target)
        
        # Loại bỏ stopwords
        words = cleaned.split()
        filtered_words = [w for w in words if w not in self.stop_words]
        
        # Loại bỏ khoảng trắng thừa
        result = ' '.join(filtered_words).strip()
        
        # Lưu vào cache
        self.processed_text_cache[text] = result
        return result

    def _calculate_sbert_similarity(self, text1: str, text2: str) -> float:
        """
        Tính toán độ tương đồng giữa hai văn bản sử dụng Sentence-BERT
        """
        # Tạo khóa cache duy nhất
        cache_key = f"sbert_{text1}||{text2}"
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]
        
        if not self.sbert_model:
            # Fallback to string similarity if SBERT is not available
            similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
            self.similarity_cache[cache_key] = similarity
            return similarity
            
        try:
            # Mã hóa văn bản và tính toán độ tương đồng
            vec1 = self.sbert_model.encode([text1])[0]
            vec2 = self.sbert_model.encode([text2])[0]
            similarity = cosine_similarity([vec1], [vec2])[0][0]
            
            # Lưu vào cache
            self.similarity_cache[cache_key] = similarity
            return similarity
        except Exception as e:
            logger.error(f"Lỗi khi tính toán độ tương đồng SBERT: {e}")
            # Fallback to string similarity
            similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
            self.similarity_cache[cache_key] = similarity
            return similarity

    def match_field(self, field_name: str, target_fields: List[str], threshold: float = 0.7) -> List[Dict]:
        """
        So khớp một tên trường với danh sách các trường mục tiêu
        """
        if not field_name or not target_fields:
            return []
            
        # Tiền xử lý tên trường
        processed_field = self._preprocess_text(field_name)
        
        # Tính toán độ tương đồng với từng trường mục tiêu
        similarities = []
        for target in target_fields:
            processed_target = self._preprocess_text(target)
            similarity = self._calculate_sbert_similarity(processed_field, processed_target)
            similarities.append((target, similarity))
        
        # Sắp xếp theo độ tương đồng giảm dần và lọc theo ngưỡng
        sorted_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
        matches = []
        for target, score in sorted_similarities:
            if score >= threshold:
                matches.append({
                    "field": target,
                    "score": score,
                    "original": field_name
                })
        
        return matches

    def get_field_values(self, field_name: str, user_id: Optional[int] = None, limit: int = 5) -> List[str]:
        """
        Lấy các giá trị đã điền trước đó cho một trường cụ thể
        """
        if not self.form_history_data:
            return []
            
        values = []
        value_counts = Counter()
        
        # Lọc theo user_id nếu được cung cấp
        filtered_data = self.form_history_data
        if user_id is not None:
            filtered_data = [entry for entry in self.form_history_data 
                            if entry.get("user_id") == user_id]
        
        # Thu thập các giá trị từ lịch sử
        for entry in filtered_data:
            form_data = entry.get("form_data", {})
            for key, value in form_data.items():
                # So khớp tên trường
                if self._calculate_sbert_similarity(self._preprocess_text(key), 
                                                 self._preprocess_text(field_name)) >= 0.8:
                    if value and str(value).strip():
                        value_counts[str(value).strip()] += 1
        
        # Lấy các giá trị phổ biến nhất
        most_common = value_counts.most_common(limit)
        values = [value for value, _ in most_common]
        
        return values

    def match_fields(self, field_names: List[str], user_id: Optional[int] = None) -> Dict[str, List[Dict]]:
        """
        So khớp nhiều tên trường và trả về các giá trị gợi ý cho mỗi trường
        """
        if not field_names or not self.form_history_data:
            return {}
            
        result = {}
        
        # Thu thập tất cả các tên trường từ lịch sử
        all_historical_fields = set()
        for entry in self.form_history_data:
            form_data = entry.get("form_data", {})
            all_historical_fields.update(form_data.keys())
        
        # So khớp từng trường và lấy giá trị
        for field_name in field_names:
            # So khớp tên trường
            matches = self.match_field(field_name, list(all_historical_fields))
            
            if matches:
                # Lấy các giá trị cho mỗi trường phù hợp
                field_values = []
                for match in matches:
                    matched_field = match["field"]
                    values = self.get_field_values(matched_field, user_id)
                    
                    for value in values:
                        field_values.append({
                            "value": value,
                            "confidence": match["score"],
                            "source_field": matched_field
                        })
                
                # Sắp xếp theo độ tin cậy
                field_values.sort(key=lambda x: x["confidence"], reverse=True)
                result[field_name] = field_values
            else:
                result[field_name] = []
        
        return result

    def get_suggested_values(self, field_name: str, limit: int = 5, user_id: Optional[int] = None) -> List[str]:
        """
        Lấy các giá trị gợi ý cho một trường cụ thể
        """
        # Lấy giá trị trực tiếp nếu trường tồn tại trong lịch sử
        direct_values = self.get_field_values(field_name, user_id, limit)
        
        if direct_values:
            return direct_values
            
        # Nếu không có giá trị trực tiếp, thử so khớp với các trường tương tự
        all_historical_fields = set()
        for entry in self.form_history_data:
            form_data = entry.get("form_data", {})
            all_historical_fields.update(form_data.keys())
        
        matches = self.match_field(field_name, list(all_historical_fields))
        
        if not matches:
            return []
            
        # Lấy giá trị từ trường phù hợp nhất
        best_match = matches[0]["field"]
        return self.get_field_values(best_match, user_id, limit)

    def update_form_history(self, new_form_data: Dict, user_id: Optional[int] = None) -> None:
        """
        Cập nhật lịch sử biểu mẫu với dữ liệu mới
        """
        if not new_form_data:
            return
            
        # Tạo entry mới
        import datetime
        entry = {
            "form_data": new_form_data,
            "timestamp": datetime.datetime.now().isoformat(),
            "user_id": user_id
        }
        
        # Thêm vào lịch sử
        self.form_history_data.append(entry)
        
        # Xóa cache để đảm bảo dữ liệu mới được sử dụng
        self.processed_text_cache.clear()
        self.similarity_cache.clear()