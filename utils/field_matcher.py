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
    
    def _load_form_history(self):
        """Tải lịch sử biểu mẫu từ file JSON"""
        if os.path.exists(FORM_HISTORY_PATH):
            with open(FORM_HISTORY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def preprocess_text(self, text):
        """Tiền xử lý văn bản cho NLP với hỗ trợ tốt hơn cho tiếng Việt"""
        if not text or not isinstance(text, str):
            return ""
            
        # Chuyển về chữ thường
        text = text.lower()
        
        # Chỉ loại bỏ một số ký tự đặc biệt, giữ lại dấu tiếng Việt
        # Giữ lại các ký tự Unicode cho tiếng Việt
        text = re.sub(r'[!"#$%&\'()*+,-./:;<=>?@\[\]^_`{|}~]', ' ', text)
        
        # Tokenize
        tokens = word_tokenize(text)
        
        # Loại bỏ stopwords nhưng giữ lại các từ có ý nghĩa
        # Chỉ loại bỏ stopwords nếu từ đó thực sự là stopword và không phải từ có nghĩa
        filtered_tokens = []
        for word in tokens:
            # Nếu từ chỉ có 1 ký tự, bỏ qua
            if len(word) <= 1:
                continue
            # Nếu từ không phải stopword hoặc là từ có nghĩa, giữ lại
            if word not in self.stop_words:
                filtered_tokens.append(word)
        
        # Đảm bảo luôn có ít nhất một token để tránh empty vocabulary
        if not filtered_tokens and tokens:
            filtered_tokens = tokens[:1]  # Giữ lại ít nhất một token
            
        return " ".join(filtered_tokens)
    
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
        if not self.word2vec_model and len(all_field_values) > 1:
            try:
                self.word2vec_model = Word2Vec(sentences=all_field_values, vector_size=100, window=5, min_count=1, workers=4)
                print("Đã huấn luyện mô hình Word2Vec thành công")
            except Exception as e:
                print(f"Lỗi khi huấn luyện Word2Vec: {e}")
        
        # Xây dựng vector TF-IDF cho mỗi trường
        for field_code, values in field_values_dict.items():
            if len(values) > 1:  # Cần ít nhất 2 giá trị để tính toán similarity
                try:
                    # Kiểm tra xem các giá trị có chứa từ nào không sau khi tiền xử lý
                    has_tokens = False
                    for value in values:
                        if value.strip():
                            has_tokens = True
                            break
                    
                    if not has_tokens:
                        print(f"Cảnh báo: Trường {field_code} không có từ nào sau khi tiền xử lý, bỏ qua")
                        continue
                    
                    # Cấu hình TfidfVectorizer để xử lý tốt hơn với tiếng Việt
                    # min_df=1: chấp nhận các từ xuất hiện ít nhất 1 lần
                    # ngram_range=(1,2): xem xét cả từ đơn và cụm từ 2 từ
                    vectorizer = TfidfVectorizer(min_df=1, ngram_range=(1,2))
                    tfidf_matrix = vectorizer.fit_transform(values)
                    
                    # Kiểm tra xem vocabulary có rỗng không
                    if len(vectorizer.vocabulary_) > 0:
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
        """Cải tiến so khớp các trường dựa trên tên trường từ database"""
        matches = {}
        
        # Tải dữ liệu form từ database
        form_data = self._load_form_history()
        field_names_db = {}
        field_values_db = {}
        
        # Xây dựng từ điển ánh xạ field_code với field_name và giá trị từ database
        for form in form_data:
            if 'form_data' in form:
                for field_code, value in form['form_data'].items():
                    # Lấy tên trường thực tế từ form_history
                    if field_code not in field_names_db:
                        # Ưu tiên sử dụng tên trường trực tiếp từ form_history nếu có
                        if field_code in form['form_data'] and isinstance(field_code, str):
                            # Loại bỏ dấu hai chấm ở cuối nếu có
                            clean_name = field_code.rstrip(':') if field_code.endswith(':') else field_code
                            field_names_db[field_code] = clean_name
                        else:
                            field_names_db[field_code] = self.extract_field_name(field_code)
                        field_values_db[field_code] = []
                    if isinstance(value, str) and value.strip():
                        field_values_db[field_code].append(value)
        
        # Tạo từ điển ánh xạ tên trường cho source và target
        source_names = {}
        for field in source_fields:
            if field in field_names_db:
                source_names[field] = field_names_db[field]
            else:
                source_names[field] = self.extract_field_name(field)
                
        target_names = {}
        for field in target_fields:
            if field in field_names_db:
                target_names[field] = field_names_db[field]
            else:
                target_names[field] = self.extract_field_name(field)
        
        # So khớp các trường
        for source_field, source_name in source_names.items():
            best_match = None
            best_score = 0
            
            for target_field, target_name in target_names.items():
                # Tính điểm tương đồng dựa trên tên trường thực tế
                name_similarity = 0
                if source_name.lower() == target_name.lower():
                    name_similarity = 1.0  # Tên trường giống nhau hoàn toàn
                else:
                    # Tính độ tương đồng dựa trên từ khóa chung
                    common_keywords = self._get_common_keywords(source_name, target_name)
                    if common_keywords:
                        name_similarity = 0.5 * len(common_keywords) / max(len(source_name.split()), len(target_name.split()))
                
                # Tính điểm tương đồng dựa trên mã trường
                code_similarity = self._calculate_field_similarity(source_field, target_field)
                
                # Kết hợp điểm tương đồng, ưu tiên tên trường hơn
                similarity = name_similarity * 0.7 + code_similarity * 0.3
                
                # Tăng điểm nếu có giá trị tương tự trong database
                if source_field in field_values_db and target_field in field_values_db:
                    source_values = set(field_values_db[source_field])
                    target_values = set(field_values_db[target_field])
                    common_values = source_values.intersection(target_values)
                    if common_values:
                        similarity += 0.2 * (len(common_values) / max(len(source_values), len(target_values)))
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = target_field
            
            # Chỉ lấy các kết quả có độ tương đồng cao
            if best_match and best_score > 0.6:  # Giảm ngưỡng xuống 0.6 để tăng khả năng gợi ý
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
        """Tìm các từ khóa chung giữa hai tên trường với hỗ trợ tốt hơn cho tiếng Việt"""
        # Kiểm tra đầu vào
        if not name1 or not name2 or not isinstance(name1, str) or not isinstance(name2, str):
            return set()
            
        # Tiền xử lý tên trường
        # Loại bỏ dấu hai chấm ở cuối nếu có
        name1 = name1.rstrip(':') if name1.endswith(':') else name1
        name2 = name2.rstrip(':') if name2.endswith(':') else name2
        
        # Tiền xử lý và tách từ
        words1 = set(self.preprocess_text(name1).split())
        words2 = set(self.preprocess_text(name2).split())
        
        # Tìm các từ chung
        common_words = words1.intersection(words2)
        
        # Loại bỏ các từ stop word
        common_keywords = {word for word in common_words if word not in self.stop_words}
        
        # Nếu không có từ khóa chung, thử kiểm tra từng phần của từ (đặc biệt hữu ích cho tiếng Việt)
        if not common_keywords and (len(words1) > 0 and len(words2) > 0):
            # Tạo danh sách các từ đã được tách thành các phần nhỏ hơn
            expanded_words1 = set()
            expanded_words2 = set()
            
            # Tách các từ thành các phần nhỏ hơn (3 ký tự trở lên)
            for word in words1:
                if len(word) >= 3:
                    for i in range(len(word) - 2):
                        expanded_words1.add(word[i:i+3])
            
            for word in words2:
                if len(word) >= 3:
                    for i in range(len(word) - 2):
                        expanded_words2.add(word[i:i+3])
            
            # Tìm các phần chung
            common_parts = expanded_words1.intersection(expanded_words2)
            if common_parts:
                # Nếu có các phần chung, thêm vào common_keywords
                common_keywords = common_parts
        
        return common_keywords
    def auto_fill_form(self, user_id, form_fields):
        """Tự động điền form dựa trên lịch sử và trả về thông tin chi tiết"""
        suggestions = {}
        suggestion_details = {}
        
        # Tải dữ liệu form từ database
        form_data = self._load_form_history()
        if not form_data:
            return {'suggestions': suggestions, 'details': suggestion_details}
        
        # Tạo từ điển để lưu trữ giá trị phổ biến nhất cho mỗi trường và ánh xạ tên trường
        field_values = {}
        field_frequencies = {}
        field_names_map = {}  # Ánh xạ field_code -> field_name
        
        # Phân tích tất cả các form để tìm giá trị phổ biến nhất và xây dựng ánh xạ tên trường
        for form in form_data:
            if 'form_data' in form:
                for field, value in form['form_data'].items():
                    # Lưu tên trường thực tế từ form_history
                    field_name = self.extract_field_name(field)
                    field_names_map[field] = field_name
                    
                    if field not in field_values:
                        field_values[field] = {}
                        field_frequencies[field] = {}
                    
                    if value in field_values[field]:
                        field_frequencies[field][value] += 1
                    else:
                        field_values[field][value] = True
                        field_frequencies[field][value] = 1
        
        # Tìm các trường tương ứng và điền giá trị
        for source_field in form_fields:
            best_match = None
            best_score = 0
            best_value = None
            best_frequency = 0
            source_field_name = self.extract_field_name(source_field)
            
            # So sánh với tất cả các trường trong lịch sử
            for target_field in field_values.keys():
                target_field_name = field_names_map.get(target_field, self.extract_field_name(target_field))
                
                # Tính điểm tương đồng cơ bản dựa trên tên trường thực tế
                name_similarity = 0
                if source_field_name.lower() == target_field_name.lower():
                    name_similarity = 1.0  # Tên trường giống nhau hoàn toàn
                else:
                    # Tính độ tương đồng dựa trên từ khóa chung
                    common_keywords = self._get_common_keywords(source_field_name, target_field_name)
                    if common_keywords:
                        name_similarity = 0.5 * len(common_keywords) / max(len(source_field_name.split()), len(target_field_name.split()))
                
                # Tính điểm tương đồng dựa trên mã trường
                code_similarity = self._calculate_field_similarity(source_field, target_field)
                
                # Kết hợp điểm tương đồng, ưu tiên tên trường hơn
                similarity = name_similarity * 0.7 + code_similarity * 0.3
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = target_field
                    
                    # Tìm giá trị phổ biến nhất cho trường này
                    if target_field in field_frequencies:
                        frequencies = field_frequencies[target_field]
                        max_freq_value = max(frequencies.items(), key=lambda x: x[1])
                        best_value = max_freq_value[0]
                        best_frequency = max_freq_value[1]
            
            # Chỉ sử dụng kết quả có độ tương đồng đủ cao
            if best_match and best_score > 0.6 and best_value:  # Giảm ngưỡng xuống 0.6 để tăng khả năng gợi ý
                suggestions[source_field] = best_value
                suggestion_details[source_field] = {
                    'matched_field': best_match,
                    'matched_field_name': field_names_map.get(best_match, self.extract_field_name(best_match)),
                    'similarity_score': best_score,
                    'frequency': best_frequency,
                    'total_occurrences': sum(field_frequencies[best_match].values())
                }
                
        return {
            'suggestions': suggestions,
            'details': suggestion_details
        }

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
    # Sử dụng user_id để lọc dữ liệu theo người dùng nếu cần
    return matcher.auto_fill_form(user_id, target_fields)