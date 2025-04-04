import numpy as np
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
from config.config import FORM_HISTORY_PATH

# Đảm bảo các tài nguyên NLTK được tải xuống
try:
    nltk.data.find('tokenizers/punkt_tab')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('punkt_tab')
    nltk.download('stopwords')
    nltk.download('wordnet')

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
    
    def _load_form_history(self):
        """Tải lịch sử biểu mẫu từ file JSON"""
        if os.path.exists(FORM_HISTORY_PATH):
            with open(FORM_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def preprocess_text(self, text):
        """Tiền xử lý văn bản cho NLP"""
        if not text or not isinstance(text, str):
            return ""
            
        # Chuyển về chữ thường và loại bỏ ký tự đặc biệt
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        
        # Tokenize và loại bỏ stopwords
        tokens = word_tokenize(text)
        tokens = [self.lemmatizer.lemmatize(word) for word in tokens if word not in self.stop_words]
        
        return " ".join(tokens)
    
    def extract_field_name(self, field_code):
        """Cải tiến trích xuất tên trường từ mã trường"""
        # Kiểm tra cache
        if field_code in self.field_name_cache:
            return self.field_name_cache[field_code]
            
        # Xử lý các trường hợp đặc biệt của mã trường
        if field_code.startswith('[') and field_code.endswith(']'):
            # Tìm tên trường tương ứng trong form_history
            for form in self.form_history:
                if 'form_data' in form:
                    for key in form['form_data'].keys():
                        if key.endswith(':'):  # Trường hợp "Tên tôi là:"
                            clean_key = key.rstrip(':')
                            if self._calculate_field_similarity(field_code, key) > 0.8:
                                self.field_name_cache[field_code] = clean_key
                                return clean_key
        
        # Xử lý thông thường
        name = re.sub(r'[\[\]_0-9]', '', field_code)
        name = name.strip()
        
        # Xử lý trường hợp có dấu hai chấm ở cuối
        if name.endswith(':'):
            name = name[:-1]
            
        # Cache kết quả
        self.field_name_cache[field_code] = name
        return name
    def _calculate_field_similarity(self, field1, field2):
        """Tính toán độ tương đồng giữa hai tên trường"""
        name1 = self.preprocess_text(self.extract_field_name(field1))
        name2 = self.preprocess_text(self.extract_field_name(field2))
        
        # Nếu một trong hai chuỗi rỗng, trả về 0
        if not name1 or not name2:
            return 0
            
        # Tách thành các từ
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        # Tính số từ chung
        common_words = words1.intersection(words2)
        
        # Tính độ tương đồng dựa trên tỷ lệ từ chung
        similarity = len(common_words) / max(len(words1), len(words2))
        
        return similarity
    def build_models(self):
        """Xây dựng các mô hình TF-IDF và Word2Vec"""
        # Thu thập tất cả các giá trị trường để huấn luyện Word2Vec
        all_field_values = []
        field_values_dict = {}
        
        for form in self.form_history:
            if 'form_data' in form:
                form_data = form['form_data']
                for field_code, value in form_data.items():
                    if isinstance(value, str) and value.strip():
                        # Tiền xử lý giá trị
                        processed_value = self.preprocess_text(value)
                        if processed_value:
                            tokens = processed_value.split()
                            all_field_values.append(tokens)
                            
                            # Lưu giá trị cho từng trường
                            if field_code not in field_values_dict:
                                field_values_dict[field_code] = []
                            field_values_dict[field_code].append(processed_value)
        
        # Huấn luyện mô hình Word2Vec nếu có đủ dữ liệu
        if len(all_field_values) > 1:
            try:
                self.word2vec_model = Word2Vec(sentences=all_field_values, vector_size=100, window=5, min_count=1, workers=4)
                print("Đã huấn luyện mô hình Word2Vec thành công")
            except Exception as e:
                print(f"Lỗi khi huấn luyện Word2Vec: {e}")
        
        # Xây dựng vector TF-IDF cho mỗi trường
        for field_code, values in field_values_dict.items():
            if len(values) > 1:  # Cần ít nhất 2 giá trị để tính toán similarity
                vectorizer = TfidfVectorizer()
                try:
                    tfidf_matrix = vectorizer.fit_transform(values)
                    self.field_vectors[field_code] = {
                        'vectorizer': vectorizer,
                        'matrix': tfidf_matrix,
                        'values': values
                    }
                    
                    # Tạo embedding cho tên trường
                    field_name = self.extract_field_name(field_code)
                    if field_name and self.word2vec_model:
                        try:
                            field_tokens = self.preprocess_text(field_name).split()
                            if field_tokens:
                                # Tính trung bình các vector từ
                                field_vector = np.mean([self.word2vec_model.wv[token] 
                                                      for token in field_tokens 
                                                      if token in self.word2vec_model.wv], axis=0)
                                if not np.isnan(field_vector).any():
                                    self.field_embeddings[field_code] = field_vector
                        except Exception as e:
                            print(f"Lỗi khi tạo embedding cho trường {field_code}: {e}")
                            
                except Exception as e:
                    print(f"Lỗi khi xây dựng vector TF-IDF cho trường {field_code}: {e}")
    
     
    def match_fields(self, source_fields, target_fields):
        """Cải tiến so khớp các trường dựa trên tên trường"""
        matches = {}
        
        # Tạo từ điển ánh xạ tên trường cho cả source và target
        source_names = {field: self.extract_field_name(field) for field in source_fields}
        target_names = {field: self.extract_field_name(field) for field in target_fields}
        
        # So khớp các trường
        for source_field, source_name in source_names.items():
            best_match = None
            best_score = 0
            
            for target_field, target_name in target_names.items():
                # Tính điểm tương đồng
                similarity = self._calculate_field_similarity(source_field, target_field)
                
                # Kiểm tra xem tên trường có giống nhau không
                if source_name.lower() == target_name.lower():
                    similarity += 0.5  # Tăng điểm cho trường hợp tên giống nhau
                
                # Kiểm tra từ khóa chung
                common_keywords = self._get_common_keywords(source_name, target_name)
                if common_keywords:
                    similarity += 0.3 * len(common_keywords)  # Tăng điểm dựa trên số từ khóa chung
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = target_field
            
            # Chỉ lấy các kết quả có độ tương đồng cao
            if best_match and best_score > 0.6:  # Giảm ngưỡng xuống 0.6
                matches[source_field] = best_match
        
        return matches
        
        # Sử dụng Word2Vec để so khớp các trường
        for source_field in source_fields:
            if source_field not in self.field_embeddings:
                continue
                
            source_embedding = self.field_embeddings[source_field]
            best_match = None
            best_score = 0
            
            for target_field in target_fields:
                if target_field in self.field_embeddings:
                    target_embedding = self.field_embeddings[target_field]
                    # Tính cosine similarity giữa hai embedding
                    similarity = cosine_similarity(
                        source_embedding.reshape(1, -1),
                        target_embedding.reshape(1, -1)
                    )[0][0]
                    
                    if similarity > best_score:
                        best_score = similarity
                        best_match = target_field
            
            # Chỉ lấy các kết quả có độ tương đồng cao
            if best_match and best_score > 0.7:
                matches[source_field] = best_match
        
        return matches
    def _get_common_keywords(self, name1, name2):
        """Tìm các từ khóa chung giữa hai tên trường"""
        # Tiền xử lý tên trường
        words1 = set(self.preprocess_text(name1).split())
        words2 = set(self.preprocess_text(name2).split())
        
        # Tìm các từ chung
        common_words = words1.intersection(words2)
        
        # Loại bỏ các từ stop word
        common_keywords = {word for word in common_words if word not in self.stop_words}
        
        return common_keywords
    def auto_fill_form(self, user_id, target_fields):
        """Cải tiến tự động điền thông tin vào biểu mẫu mới"""
        # Lấy các biểu mẫu đã điền của người dùng
        user_forms = []
        for form in self.form_history:
            if 'user_id' in form and form['user_id'] == user_id and 'form_data' in form:
                user_forms.append(form['form_data'])
        
        if not user_forms:
            return {}
        
        # Lấy biểu mẫu gần nhất
        latest_form = user_forms[-1]
        source_fields = list(latest_form.keys())
        
        # So khớp các trường
        field_matches = self.match_fields(source_fields, target_fields)
        
        # Tạo dữ liệu điền tự động với thông tin bổ sung
        auto_fill_data = {}
        for source_field, target_field in field_matches.items():
            if source_field in latest_form and latest_form[source_field]:
                value = latest_form[source_field]
                source_name = self.extract_field_name(source_field)
                target_name = self.extract_field_name(target_field)
                
                # Thêm thông tin về độ tương đồng và nguồn gốc
                auto_fill_data[target_field] = {
                    'value': value,
                    'source_field': source_field,
                    'source_name': source_name,
                    'target_name': target_name,
                    'similarity': self._calculate_field_similarity(source_field, target_field)
                }
        
        return auto_fill_data

# Singleton instance
_field_matcher_instance = None

def get_field_matcher():
    """Trả về instance của FieldMatcher (Singleton pattern)"""
    global _field_matcher_instance
    if _field_matcher_instance is None:
        _field_matcher_instance = FieldMatcher()
    return _field_matcher_instance

def auto_fill_form(user_id, target_fields):
    """Hàm tiện ích để tự động điền biểu mẫu"""
    matcher = get_field_matcher()
    return matcher.auto_fill_form(user_id, target_fields)