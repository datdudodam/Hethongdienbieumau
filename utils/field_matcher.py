import numpy as np
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gensim.models import Word2Vec
import os
import json
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import difflib
import unicodedata
import re
from config.config import FORM_HISTORY_PATH
from nltk.stem import WordNetLemmatizer
# Đảm bảo các tài nguyên NLTK được tải xuống
def ensure_nltk_resources():
    resources = {
        'punkt_tab': 'tokenizers/punkt_tab', 
        'stopwords': 'corpora/stopwords', 
        'wordnet': 'corpora/wordnet',
        'omw-1.4': 'corpora/omw-1.4'
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

# Tải các resource cần thiết
ensure_nltk_resources()

class EnhancedFieldMatcher:
    def __init__(self, form_history_path: str):
        self.form_history_path = form_history_path
        self.stop_words = self._initialize_stopwords()
        self.field_name_cache = {}
        self.field_value_mapping = defaultdict(list)
        self.vectorizer = None
        self.word2vec_model = None
        self.field_vectors = None
        self.field_names = []
        self.field_embeddings = {}
        self.matched_fields = {}
        
        # Tải và xử lý dữ liệu lịch sử
        self.form_history = self._load_form_history()
        self._build_field_value_mapping()
        self._build_models()
    
    def _initialize_stopwords(self) -> Set[str]:
        """Khởi tạo stopwords cho cả tiếng Anh và tiếng Việt"""
        english_stopwords = set(stopwords.words('english'))
        vietnamese_stopwords = {
            'của', 'và', 'các', 'có', 'được', 'trong', 'là', 'cho', 'những', 'với',
            'không', 'này', 'đến', 'khi', 'về', 'như', 'từ', 'một', 'người', 'năm',
            'bị', 'đã', 'sẽ', 'cũng', 'vào', 'ra', 'nếu', 'để', 'tại', 'theo',
            'sau', 'trên', 'hoặc', 'tôi', 'bạn', 'anh', 'chị', 'họ', 'của', 'mình'
        }
        return english_stopwords.union(vietnamese_stopwords)
    
    def _load_form_history(self) -> List[Dict]:
        """Tải lịch sử biểu mẫu từ file JSON"""
        if os.path.exists(self.form_history_path):
            try:
                with open(self.form_history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading form history: {e}")
                return []
        return []
    
    def _build_field_value_mapping(self):
        """Xây dựng ánh xạ giữa tên trường và các giá trị đã điền"""
        for form in self.form_history:
            if isinstance(form, dict) and 'form_data' in form:
                form_data = form['form_data']
                # Bỏ qua các trường đặc biệt
                special_fields = {'form_id', 'document_name'}
                for field_name, value in form_data.items():
                    if field_name not in special_fields and value and (val_str := str(value).strip()):
                        self.field_value_mapping[field_name].append(val_str)
    
    def _preprocess_text(self, text: str) -> str:
        """Tiền xử lý văn bản nâng cao cho tiếng Việt"""
        if not text:
            return ""
            
        # Chuẩn hóa Unicode và chuyển đổi về chữ thường
        text = unicodedata.normalize('NFC', text.lower())
        
        # Loại bỏ dấu câu và ký tự đặc biệt, giữ lại dấu tiếng Việt
        text = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', text)
        
        # Thay thế từ đồng nghĩa phổ biến
        synonyms = {
            'ho_ten': ['hovaten', 'hoten', 'họ_tên', 'tên', 'họ và tên'],
            'dia_chi': ['diachi', 'địa_chỉ', 'noi_o', 'địa chỉ', 'address'],
            'dien_thoai': ['sdt', 'so_dien_thoai', 'đt', 'phone', 'tel']
        }
        
        for key, values in synonyms.items():
            for synonym in values:
                text = re.sub(r'\b' + re.escape(synonym) + r'\b', key, text)
        
        # Loại bỏ stopwords
        tokens = text.split()
        filtered_tokens = [token for token in tokens if token not in self.stop_words]
        
        return ' '.join(filtered_tokens)
    
    def _normalize_field_name(self, field_name: str) -> str:
        """Chuẩn hóa tên trường nâng cao"""
        # Chuẩn hóa Unicode
        field_name = unicodedata.normalize('NFC', field_name)
        
        # Loại bỏ ký tự đặc biệt, giữ lại dấu tiếng Việt
        field_name = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', field_name)
        
        # Thay thế khoảng trắng bằng dấu gạch dưới
        field_name = re.sub(r'\s+', '_', field_name.strip())
        
        return field_name.lower()
    
    def _build_models(self):
        """Xây dựng các mô hình TF-IDF và Word2Vec"""
        # Thu thập tất cả các tên trường đã được tiền xử lý
        processed_fields = []
        field_names = []
        
        for form in self.form_history:
            if isinstance(form, dict) and 'form_data' in form:
                for field_name in form['form_data'].keys():
                    if field_name not in self.field_name_cache:
                        processed = self._preprocess_text(field_name)
                        self.field_name_cache[field_name] = processed
                        processed_fields.append(processed)
                        field_names.append(field_name)
        
        # Xây dựng TF-IDF vectorizer
        if processed_fields:
            self.vectorizer = TfidfVectorizer()
            self.field_vectors = self.vectorizer.fit_transform(processed_fields)
            self.field_names = field_names
            
            # Xây dựng Word2Vec model
            sentences = [field.split() for field in processed_fields if field.split()]
            if sentences:
                self.word2vec_model = Word2Vec(
                    sentences, 
                    vector_size=100, 
                    window=5, 
                    min_count=1, 
                    workers=4,
                    epochs=20
                )
                
                # Tạo embeddings cho mỗi trường
                for field, processed in zip(field_names, processed_fields):
                    tokens = processed.split()
                    if tokens:
                        # Tính trung bình các vector từ (chỉ lấy tokens tồn tại trong vocab)
                        embeddings = []
                        for token in tokens:
                            if token in self.word2vec_model.wv:
                                embeddings.append(self.word2vec_model.wv[token])
                        
                        if embeddings:  # Chỉ gán nếu có ít nhất 1 embedding
                            self.field_embeddings[field] = np.mean(embeddings, axis=0)
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Tính toán độ tương đồng tổng hợp sử dụng nhiều phương pháp"""
        # Chuẩn hóa văn bản
        norm1 = self._normalize_field_name(text1)
        norm2 = self._normalize_field_name(text2)
        
        # 1. SequenceMatcher similarity
        seq_sim = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        
        # 2. TF-IDF cosine similarity
        tfidf_sim = 0.0
        if self.vectorizer and self.field_vectors is not None:
            try:
                query_vec = self.vectorizer.transform([self._preprocess_text(text1)])
                target_vec = self.vectorizer.transform([self._preprocess_text(text2)])
                tfidf_sim = cosine_similarity(query_vec, target_vec)[0][0]
            except Exception as e:
                print(f"TF-IDF similarity error: {e}")
        
        # 3. Word2Vec similarity (nếu có embeddings)
        w2v_sim = 0.0
        if self.word2vec_model:
            try:
                tokens1 = self._preprocess_text(text1).split()
                tokens2 = self._preprocess_text(text2).split()
                
                if tokens1 and tokens2:
                    # Kiểm tra xem tất cả tokens có trong vocab không
                    if all(token in self.word2vec_model.wv for token in tokens1) and \
                       all(token in self.word2vec_model.wv for token in tokens2):
                        w2v_sim = self.word2vec_model.wv.n_similarity(tokens1, tokens2)
            except Exception as e:
                print(f"Word2Vec similarity error: {e}")
        
        # Kết hợp các điểm similarity với trọng số
        combined_sim = 0.4 * seq_sim + 0.3 * tfidf_sim + 0.3 * w2v_sim
        
        return combined_sim
    
    def match_fields(self, form_model: List[str], form_data: Dict[str, str], threshold: float = 0.65) -> Dict[str, str]:
        """
        Ghép các trường giữa form_model và form_data sử dụng kết hợp nhiều phương pháp
        """
        matched_fields = {}
        used_model_fields = set()
        used_data_fields = set()
        
        # Tạo danh sách các cặp tiềm năng
        potential_matches = []
        
        for model_field in form_model:
            for data_field in form_data.keys():
                similarity = self._calculate_similarity(model_field, data_field)
                if similarity >= threshold:
                    potential_matches.append((similarity, model_field, data_field))
        
        # Sắp xếp theo độ tương đồng giảm dần
        potential_matches.sort(reverse=True, key=lambda x: x[0])
        
        # Chọn các cặp tốt nhất không trùng lặp
        for similarity, model_field, data_field in potential_matches:
            if model_field not in used_model_fields and data_field not in used_data_fields:
                matched_fields[model_field] = data_field
                used_model_fields.add(model_field)
                used_data_fields.add(data_field)
        
        self.matched_fields = matched_fields
        return matched_fields
    
    def find_most_similar_field(self, query: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Tìm các trường tương tự nhất với query sử dụng kết hợp TF-IDF và Word2Vec
        """
        if not query or not self.field_names or not self.vectorizer:
            return []
            
        try:
            # Tiền xử lý query
            processed_query = self._preprocess_text(query)
            
            # 1. Tìm kiếm bằng TF-IDF
            tfidf_results = []
            if self.vectorizer and self.field_vectors is not None:
                query_vec = self.vectorizer.transform([processed_query])
                similarities = cosine_similarity(query_vec, self.field_vectors).flatten()
                tfidf_results = [(self.field_names[i], float(similarities[i])) 
                                for i in np.argsort(similarities)[-top_n:][::-1]
                                if similarities[i] > 0]
            
            # 2. Tìm kiếm bằng Word2Vec (nếu có model)
            w2v_results = []
            if self.word2vec_model and self.field_embeddings:
                query_tokens = processed_query.split()
                if query_tokens:
                    # Tính embedding cho query (chỉ lấy tokens tồn tại trong vocab)
                    valid_tokens = [token for token in query_tokens if token in self.word2vec_model.wv]
                    if valid_tokens:
                        query_embedding = np.mean([self.word2vec_model.wv[token] for token in valid_tokens], axis=0)
                        
                        # Tính similarity với các trường đã biết
                        similarities = {}
                        for field, embedding in self.field_embeddings.items():
                            if embedding is not None:  # Chỉ tính similarity nếu có embedding
                                sim = cosine_similarity(
                                    query_embedding.reshape(1, -1), 
                                    embedding.reshape(1, -1)
                                )[0][0]
                                similarities[field] = sim
                        
                        # Lấy top_n kết quả
                        w2v_results = sorted(
                            [(field, sim) for field, sim in similarities.items()], 
                            key=lambda x: x[1], 
                            reverse=True
                        )[:top_n]
            
            # Kết hợp và xếp hạng kết quả
            combined_results = defaultdict(float)
            
            # Thêm điểm từ TF-IDF
            for field, score in tfidf_results:
                combined_results[field] += score * 0.5
                
            # Thêm điểm từ Word2Vec
            for field, score in w2v_results:
                combined_results[field] += score * 0.5
            
            # Sắp xếp và trả về kết quả
            final_results = sorted(
                [(field, score) for field, score in combined_results.items()],
                key=lambda x: x[1],
                reverse=True
            )[:top_n]
            
            return final_results
            
        except Exception as e:
            print(f"Error finding similar fields: {e}")
            return []
    
    def get_suggested_values(self, field_name: str, limit: int = 3) -> List[str]:
        """
        Lấy danh sách giá trị đề xuất cho một trường
        """
        # 1. Tìm kiếm trực tiếp
        direct_values = self.field_value_mapping.get(field_name, [])
        
        # 2. Tìm kiếm từ các trường tương tự
        similar_fields = self.find_most_similar_field(field_name, top_n=3)
        similar_values = []
        for similar_field, _ in similar_fields:
            if similar_field != field_name:
                similar_values.extend(self.field_value_mapping.get(similar_field, []))
        
        # Kết hợp và sắp xếp kết quả
        all_values = direct_values + similar_values
        value_counts = defaultdict(int)
        for val in all_values:
            value_counts[val] += 1
        
        # Sắp xếp theo tần suất và độ dài
        sorted_values = sorted(
            value_counts.items(),
            key=lambda x: (-x[1], len(x[0])),  # Tần suất giảm dần, độ dài tăng dần
            reverse=False
        )
        
        return [val[0] for val in sorted_values[:limit]]
    
    def update_form_history(self, new_form_data: Dict) -> None:
        """
        Cập nhật lịch sử form với dữ liệu mới
        """
        try:
            # Thêm vào lịch sử
            self.form_history.append({'form_data': new_form_data})
            
            # Cập nhật field_value_mapping
            for field_name, value in new_form_data.items():
                if value and str(value).strip():
                    self.field_value_mapping[field_name].append(str(value))
            
            # Xây dựng lại models
            self._build_models()
            
            # Lưu vào file
            with open(self.form_history_path, 'w', encoding='utf-8') as f:
                json.dump(self.form_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating form history: {e}")