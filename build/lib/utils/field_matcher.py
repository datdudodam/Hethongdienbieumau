import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import gensim
from gensim.models import Word2Vec
import os
import json
from collections import defaultdict
from config.config import FORM_HISTORY_PATH
from typing import Dict, List, Optional, Tuple
import numpy as np
nltk.download('punkt_tab')
# Đảm bảo các tài nguyên NLTK được tải xuống
def ensure_nltk_resources():
    resources = {
        'punkt_tab': 'tokenizers/punkt_tab',
        'stopwords': 'corpora/stopwords', 
        'wordnet': 'corpora/wordnet',
        'omw-1.4': 'corpora/omw-1.4'  # Cần thiết cho WordNetLemmatizer
    }
    for resource, path in resources.items():
        try:
            nltk.data.find(path)
            print(f"Resource {resource} already exists.")
        except LookupError:
            try:
                print(f"Downloading {resource} resource...")
                nltk.download(resource, quiet=True)
                print(f"Downloaded {resource} successfully!")
            except Exception as e:
                print(f"Error downloading {resource}: {e}")
                print(f"Please manually download {resource} using: nltk.download('{resource}')")
                # Không dừng vòng lặp nếu tải thất bại, chỉ ghi log lỗi

# Tải các resource cần thiết
ensure_nltk_resources()
class FieldMatcher:
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        # Mở rộng stopwords tiếng Việt
        self.vietnamese_stopwords = {
            'của', 'và', 'các', 'có', 'được', 'trong', 'là', 'cho', 'những', 'với', 
            'không', 'này', 'đến', 'khi', 'về', 'như', 'từ', 'một', 'người', 'năm', 
            'bị', 'đã', 'sẽ', 'cũng', 'vào', 'ra', 'nếu', 'để', 'tại', 'theo', 
            'sau', 'trên', 'hoặc', 'tôi', 'bạn', 'anh', 'chị', 'họ', 'của', 'mình'
        }
        self.stop_words.update(self.vietnamese_stopwords)
        self.form_history = self._load_form_history()
        self.field_vectors = {}
        self.field_embeddings = {}
        self.field_name_cache = {}  # Cache cho tên trường đã xử lý
        self.word2vec_model = None
        self.build_models()
    
    def _load_form_history(self) -> List[Dict]:
        """Tải lịch sử biểu mẫu từ file JSON"""
        if os.path.exists(FORM_HISTORY_PATH):
            with open(FORM_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _build_field_value_mapping(self):
        """Xây dựng ánh xạ giữa tên trường và các giá trị đã điền"""
        for form in self.form_history:
            if 'form_data' in form and isinstance(form['form_data'], dict):
                for field_name, value in form['form_data'].items():
                    if value and str(value).strip():  # Chỉ lưu giá trị không rỗng
                        self.field_value_mapping[field_name].append(str(value))
    
    def preprocess_text(self, text: str) -> str:
        """Tiền xử lý văn bản cho NLP với hỗ trợ tốt hơn cho tiếng Việt"""
        if not text or not isinstance(text, str):
            return ""
            
        # Chuyển về chữ thường
        text = text.lower()
        
        # Chỉ loại bỏ một số ký tự đặc biệt, giữ lại dấu tiếng Việt
        text = re.sub(r'[!"#$%&\'()*+,-./:;<=>?@\[\]^_`{|}~]', ' ', text)
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Loại bỏ stopwords nhưng giữ lại các từ có ý nghĩa
        filtered_tokens = []
        for word in tokens:
            if len(word) <= 1:
                continue
            if word not in self.stop_words:
                filtered_tokens.append(word)
        
        return " ".join(filtered_tokens) if filtered_tokens else text[:50]  # Giữ lại phần đầu nếu không có token
    
    def build_models(self):
        """Xây dựng các mô hình NLP để so khớp trường"""
        # Xây dựng danh sách tên trường đã được tiền xử lý
        processed_fields = []
        field_names = []
        
        # Thu thập tất cả các tên trường từ lịch sử form
        for form in self.form_history:
            if 'form_data' in form and isinstance(form['form_data'], dict):
                for field_name in form['form_data'].keys():
                    if field_name not in self.field_name_cache:
                        processed = self.preprocess_text(field_name)
                        self.field_name_cache[field_name] = processed
                        processed_fields.append(processed)
                        field_names.append(field_name)
        
        # Xây dựng TF-IDF vectorizer
        if processed_fields:
            self.vectorizer = TfidfVectorizer()
            self.field_vectors = self.vectorizer.fit_transform(processed_fields)
            self.field_names = field_names
            
            # Xây dựng Word2Vec model
            sentences = [field.split() for field in processed_fields]
            if any(sentences):
                self.word2vec_model = Word2Vec(sentences, vector_size=100, window=5, min_count=1, workers=4)
    
    def find_most_similar_field(self, query: str, threshold: float = 0.5) -> Optional[Tuple[str, float]]:
        """
        Tìm trường phù hợp nhất với query
        
        Args:
            query: Câu truy vấn cần so khớp
            threshold: Ngưỡng similarity tối thiểu
            
        Returns:
            Tuple (tên trường phù hợp nhất, điểm similarity) hoặc None nếu không tìm thấy
        """
        if not query or not self.field_vectors or not hasattr(self, 'vectorizer'):
            return None
            
        # Tiền xử lý query
        processed_query = self.preprocess_text(query)
        query_vector = self.vectorizer.transform([processed_query])
        
        # Tính toán similarity
        similarities = cosine_similarity(query_vector, self.field_vectors)
        max_index = np.argmax(similarities)
        max_similarity = similarities[0, max_index]
        
        if max_similarity >= threshold:
            return (self.field_names[max_index], max_similarity)
        return None
    
    def get_suggested_values(self, field_name: str, limit: int = 3) -> List[str]:
        """
        Lấy danh sách giá trị đề xuất cho một trường dựa trên lịch sử
        
        Args:
            field_name: Tên trường cần lấy giá trị
            limit: Số lượng giá trị đề xuất tối đa
            
        Returns:
            Danh sách các giá trị đề xuất (có thể rỗng)
        """
        if field_name in self.field_value_mapping:
            values = self.field_value_mapping[field_name]
            # Đếm tần suất và sắp xếp
            value_counts = defaultdict(int)
            for v in values:
                value_counts[v] += 1
            
            # Sắp xếp theo tần suất giảm dần
            sorted_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)
            return [v[0] for v in sorted_values[:limit]]
        return []
    
    def auto_fill_suggestions(self, current_fields: Dict[str, str]) -> Dict[str, List[str]]:
        """
        Đề xuất giá trị điền tự động cho các trường dựa trên:
        1. Tên trường hiện tại
        2. Giá trị của các trường liên quan
        
        Args:
            current_fields: Các trường hiện tại với giá trị đã điền {field_name: value}
            
        Returns:
            Dict chứa danh sách đề xuất cho mỗi trường {field_name: [suggestions]}
        """
        suggestions = {}
        
        # Duyệt qua tất cả các trường đã biết trong hệ thống
        for field_name in self.field_value_mapping.keys():
            # Bỏ qua các trường đã có giá trị
            if field_name in current_fields and current_fields[field_name]:
                continue
                
            # Lấy giá trị đề xuất
            suggested_values = self.get_suggested_values(field_name)
            if suggested_values:
                suggestions[field_name] = suggested_values
        
        # Tìm các trường tương tự cho các trường chưa có trong mapping
        for field_name, value in current_fields.items():
            if not value and field_name not in suggestions:
                # Tìm các trường tương tự
                similar_field = self.find_most_similar_field(field_name)
                if similar_field:
                    similar_field_name, _ = similar_field
                    similar_values = self.get_suggested_values(similar_field_name)
                    if similar_values:
                        suggestions[field_name] = similar_values
        
        return suggestions
    
    def update_form_history(self, new_form_data: Dict):
        """
        Cập nhật lịch sử form với dữ liệu mới
        
        Args:
            new_form_data: Dữ liệu form mới dưới dạng dict {field_name: value}
        """
        # Thêm vào lịch sử
        self.form_history.append({'form_data': new_form_data})
        
        # Cập nhật field_value_mapping
        for field_name, value in new_form_data.items():
            if value and str(value).strip():
                if not hasattr(self, 'field_value_mapping'):
                    self.field_value_mapping = defaultdict(list)
                self.field_value_mapping[field_name].append(str(value))
        
        # Xây dựng lại models
        self.build_models()
        
        # Lưu vào file
        with open(FORM_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.form_history, f, ensure_ascii=False, indent=2)