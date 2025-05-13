import numpy as np
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gensim.models import Word2Vec
import os
import json
from typing import List, Dict, Optional, Tuple, Set,Union,Any
from collections import defaultdict
import difflib
import unicodedata
from sentence_transformers import SentenceTransformer

import re
from config.config import FORM_HISTORY_PATH

# #Đảm bảo các tài nguyên NLTK được tải xuống
# def ensure_nltk_resources():
#     resources = {
#         'punkt_tab': 'tokenizers/punkt_tab', 
#         'stopwords': 'corpora/stopwords', 
#         'omw-1.4': 'corpora/omw-1.4'
#     }
#     for resource, path in resources.items():
#         try:
#             nltk.data.find(path)
#             print(f"Resource {resource} already exists.")
#         except LookupError:
#             try:
#                 print(f"Downloading {resource} resource...")
#                 nltk.download(resource, quiet=True)
#                 print(f"Downloaded {resource} successfully!")
#             except Exception as e:
#                 print(f"Error downloading {resource}: {e}")
#                 print(f"Please manually download {resource} using: nltk.download('{resource}')")

# # Tải các resource cần thiết
# ensure_nltk_resources()

class EnhancedFieldMatcher:
    def __init__(self, form_history_path: str):
        self.form_history_path = form_history_path
        self.user_preferences = defaultdict(dict)
        self.synonym_map = self._build_synonym_map()
        self.stop_words = self._initialize_stopwords()
        self.field_name_cache = {}
        self.field_value_mapping = defaultdict(list)
        self.vectorizer = None
        self.word2vec_model = None
        self.field_vectors = None
        self.field_names = []
        self.field_embeddings = {}
        self.matched_fields = {}
        self.similarity_cache = {}  # Cache for similarity calculations
        self.processed_text_cache = {}  # Cache for preprocessed text
        
        self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Tải dữ liệu lịch sử từ file
        self.form_history = self._load_form_history()
        
        # Xử lý dữ liệu lịch sử
        self._load_user_preferences()  # (user_id, field, value) -> frequency
        self._build_field_value_mapping()
        self._build_models()
    def _load_user_preferences(self):
        """Tải preferences của từng user dựa trên lịch sử"""
        for form in self.form_history:
            if isinstance(form, dict) and 'user_id' in form:
                user_id = form['user_id']
                if 'form_data' in form:
                    for field_name, value in form['form_data'].items():
                        if value and str(value).strip():
                            # Lưu cả tần suất sử dụng và giá trị thường dùng
                            if field_name not in self.user_preferences[user_id]:
                                self.user_preferences[user_id][field_name] = {
                                    'count': 0,
                                    'values': defaultdict(int)
                                }
                            self.user_preferences[user_id][field_name]['count'] += 1
                            self.user_preferences[user_id][field_name]['values'][str(value).strip()] += 1

    def _get_user_field_boost(self, user_id: int, field_name: str) -> float:
        """Tính điểm boost dựa trên tần suất sử dụng của user"""
        if user_id in self.user_preferences and field_name in self.user_preferences[user_id]:
            usage_count = self.user_preferences[user_id][field_name]['count']
            # Boost tối đa 0.2 cho các trường thường dùng
            return min(usage_count * 0.01, 0.2)
        return 0.0
    def _build_synonym_map(self) -> Dict[str, List[str]]:
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
            ]

        }
        return raw_map


    def _calculate_sbert_similarity(self, text1: str, text2: str) -> float:
        # Create a unique cache key
        cache_key = f"sbert_{text1}||{text2}"
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]
            
        # Encode texts and calculate similarity
        vec1 = self.sbert_model.encode([text1])[0]
        vec2 = self.sbert_model.encode([text2])[0]
        similarity = cosine_similarity([vec1], [vec2])[0][0]
        
        # Cache the result
        self.similarity_cache[cache_key] = similarity
        return similarity
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
        try:
            if os.path.exists(self.form_history_path):
                try:
                    with open(self.form_history_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"Loaded form history with {len(data)} entries")
                        return data
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading form history: {e}")
                    return []
            else:
                print(f"Form history file not found at: {self.form_history_path}")
                return []
        except Exception as e:
            print(f"Unexpected error loading form history: {str(e)}")
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
        """Tiền xử lý văn bản nâng cao cho tiếng Việt với caching"""
        if not text:
            return ""
            
        # Check cache first
        if text in self.processed_text_cache:
            return self.processed_text_cache[text]
            
        # Chuẩn hóa Unicode và chuyển đổi về chữ thường
        normalized = unicodedata.normalize('NFC', text.lower())
        
        # Loại bỏ dấu câu và ký tự đặc biệt, giữ lại dấu tiếng Việt
        cleaned = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', normalized)
        
        # Thay thế từ đồng nghĩa phổ biến - sử dụng sorted để tối ưu
        for target, synonyms in sorted(self.synonym_map.items(), key=lambda x: len(x[0]), reverse=True):
            for synonym in sorted(synonyms, key=len, reverse=True):
                cleaned = re.sub(r'\b' + re.escape(synonym) + r'\b', target, cleaned)
        
        # Loại bỏ stopwords
        tokens = cleaned.split()
        filtered_tokens = [token for token in tokens if token not in self.stop_words]
        result = ' '.join(filtered_tokens)
        
        # Cache the result
        self.processed_text_cache[text] = result
        return result
    
    def _normalize_field_name(self, field_name: str) -> str:
        """Chuẩn hóa tên trường nâng cao"""
        if not field_name:
            return ""
        
        # Chuẩn hóa Unicode và chuyển đổi về chữ thường
        text = unicodedata.normalize('NFC', field_name.lower())
        
        # Thay thế từ đồng nghĩa - cải tiến để ưu tiên thay thế cụm từ dài trước
        synonym_items = sorted(self.synonym_map.items(), key=lambda x: max(len(s) for s in x[1]), reverse=True)
        for target, synonyms in synonym_items:
            for synonym in sorted(synonyms, key=len, reverse=True):
                text = re.sub(r'\b' + re.escape(synonym) + r'\b', target, text)
        
        # Loại bỏ ký tự đặc biệt
        text = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', text)
        
        # Loại bỏ stopwords
        tokens = [token for token in text.split() if token not in self.stop_words]
        
        return ' '.join(tokens).strip()
    
    def _build_models(self):
        """Xây dựng các mô hình TF-IDF và Word2Vec"""
        # Thu thập tất cả các tên trường đã được tiền xử lý
        processed_fields = []
        field_names = []
        
        for form in self.form_history_path:
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
        """Tính toán độ tương đồng tổng hợp sử dụng nhiều phương pháp với caching"""
        # Check cache first - create a unique key for the pair
        cache_key = f"{text1}||{text2}"
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]
            
        # Chuẩn hóa văn bản
        norm1 = self._normalize_field_name(text1)
        norm2 = self._normalize_field_name(text2)
        
        # Quick check for exact matches after normalization
        if norm1 == norm2:
            self.similarity_cache[cache_key] = 1.0
            return 1.0
       
        # 1. SequenceMatcher similarity - faster implementation
        seq_sim = difflib.SequenceMatcher(None, norm1, norm2).quick_ratio()
        
        # 2. TF-IDF cosine similarity - only if needed
        tfidf_sim = 0.0
        if seq_sim < 0.8 and self.vectorizer and self.field_vectors is not None:
            try:
                query_vec = self.vectorizer.transform([self._preprocess_text(text1)])
                target_vec = self.vectorizer.transform([self._preprocess_text(text2)])
                tfidf_sim = cosine_similarity(query_vec, target_vec)[0][0]
            except Exception as e:
                print(f"TF-IDF similarity error: {e}")
        
        # 3. Word2Vec similarity - only if needed
        w2v_sim = 0.0
        if seq_sim < 0.8 and tfidf_sim < 0.8 and self.word2vec_model:
            try:
                tokens1 = self._preprocess_text(text1).split()
                tokens2 = self._preprocess_text(text2).split()
                
                if tokens1 and tokens2:
                    # Only check tokens that are actually in the vocabulary
                    valid_tokens1 = [t for t in tokens1 if t in self.word2vec_model.wv]
                    valid_tokens2 = [t for t in tokens2 if t in self.word2vec_model.wv]
                    
                    if valid_tokens1 and valid_tokens2:
                        w2v_sim = self.word2vec_model.wv.n_similarity(valid_tokens1, valid_tokens2)
            except Exception as e:
                print(f"Word2Vec similarity error: {e}")
        
        # 4. SBERT similarity - only if needed
        sbert_sim = 0.0
        if seq_sim < 0.8 and tfidf_sim < 0.8 and w2v_sim < 0.8:
            sbert_sim = self._calculate_sbert_similarity(text1, text2)
        
        # Kết hợp các điểm similarity với trọng số
        combined_sim = 0.25 * seq_sim + 0.25 * tfidf_sim + 0.2 * w2v_sim + 0.3 * sbert_sim
        
        # Cache the result
        self.similarity_cache[cache_key] = combined_sim
        return combined_sim
    def _boost_by_frequency(self, field_name: str, base_score: float) -> float:
        frequency = len(self.field_value_mapping.get(field_name, []))
        boost = min(frequency / 10, 1.0)  # Giới hạn boost không vượt quá 1.0
        return base_score + 0.05 * boost  # Tăng nhẹ điểm


    def match_fields(
            self,
            form_model: Union[str, List[str]],
            threshold: float = 0.65,
            user_id: Optional[str] = None,
            fast_mode: bool = False
        ) -> Dict[str, List[Dict[str, Any]]]:
            """
            Ghép các trường giữa form_model và form_data sử dụng kết hợp nhiều phương pháp.
            Trả về dict gồm tên trường đã khớp, danh sách tối đa 3 kết quả khớp (trường dữ liệu và giá trị).
            """
            if not hasattr(self, '_history_data_cache'):
                try:
                    with open("form_history.json", "r", encoding="utf-8") as f:
                        self._history_data_cache = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._history_data_cache = []

            history_data = self._history_data_cache

            if not history_data:
                if not fast_mode:
                    print("⚠️ Không có dữ liệu trong form_history.json")
                return {}

            if isinstance(form_model, str):
                form_model = [form_model]

            if not fast_mode:
                print(f"\n🧩 Danh sách trường cần ghép: {form_model}")
                if user_id:
                    print(f"🔑 Chỉ xét các bản ghi của user_id: {user_id}")

            cache_key = f"user_records_{user_id}"
            if hasattr(self, cache_key):
                user_records = getattr(self, cache_key)
            else:
                # Chuyển đổi user_id thành chuỗi để đảm bảo so sánh chính xác
                str_user_id = str(user_id) if user_id is not None else None
                user_records = [record for record in history_data if str(record.get("user_id")) == str_user_id]
                user_records = list(reversed(user_records))
                setattr(self, cache_key, user_records)

            if not user_records:
                if not fast_mode:
                    print("⚠️ Không tìm thấy bản ghi nào thuộc user_id này.")
                return {}

            records_to_check = user_records[:3] if fast_mode else user_records

            all_matches = defaultdict(list)
            seen_matches = set()

            for idx, record in enumerate(records_to_check):
                form_data = record.get("form_data", {})

                if not fast_mode:
                    print(f"\n📄 Đang kiểm tra bản ghi thứ {idx + 1}/{len(records_to_check)}: {len(form_data)} trường")

                for model_field in form_model:
                    if len(all_matches[model_field]) >= 4:
                        continue

                    normalized_model = self._normalize_field_name(model_field)

                    potential_matches = []

                    for data_field in form_data.keys():
                        normalized_data = self._normalize_field_name(data_field)
                        value = form_data[data_field]
                        key = (model_field, data_field, value)
                        if key in seen_matches:
                            continue

                        if normalized_model == normalized_data:
                            similarity = 1.0
                        else:
                            similarity = self._calculate_similarity(model_field, data_field)
                            similarity += self._boost_by_frequency(data_field, similarity)
                            similarity += self._exact_token_match_boost(model_field, data_field)

                        if similarity >= threshold:
                            potential_matches.append((similarity, model_field, data_field, value))
                            seen_matches.add(key)

                    potential_matches.sort(reverse=True, key=lambda x: x[0])
                   
                    for sim, m_field, d_field, value in potential_matches:
                        # Kiểm tra nếu chưa đủ 3 kết quả VÀ giá trị chưa bị trùng
                        existing_values = {match["value"] for match in all_matches[m_field]}
                        if len(all_matches[m_field]) < 5 and value not in existing_values:
                            all_matches[m_field].append({
                                "matched_field": d_field,
                                "value": value,
                                "similarity": round(sim, 4)
                            })


            if not fast_mode:
                for model, matches in all_matches.items():
                    print(f"\n🔍 Kết quả cho '{model}':")
                    for match in matches:
                        print(f"   - {match['matched_field']} ({match['similarity']}): {match['value']}")

            self.matched_fields = all_matches
            return all_matches



    def _exact_token_match_boost(self, model_field: str, data_field: str) -> float:
        model_tokens = set(self._preprocess_text(model_field).split())
        data_tokens = set(self._preprocess_text(data_field).split())
        overlap = model_tokens & data_tokens
        return 0.1 * len(overlap)
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
    
    def get_suggested_values(self, field_name: str, limit: int = 3, 
                           user_id: Optional[int] = None) -> List[str]:
        """
        Cải tiến: Ưu tiên giá trị mà user đã từng nhập
        """
        # 1. Lấy giá trị chung
        all_values = []
        direct_values = self.field_value_mapping.get(field_name, [])
        all_values.extend([(v, 1.0) for v in direct_values])  # Weight = 1.0 cho giá trị chung
        
        # 2. Thêm giá trị từ user nếu có
        if user_id is not None and user_id in self.user_preferences:
            if field_name in self.user_preferences[user_id]:
                user_values = self.user_preferences[user_id][field_name]['values']
                for val, count in user_values.items():
                    # Tăng weight cho giá trị của user (count * 2.0 để ưu tiên hơn)
                    all_values.append((val, count * 2.0))
        
        # 3. Thêm giá trị từ các trường tương tự
        similar_fields = self.find_most_similar_field(field_name, top_n=3)
        for similar_field, _ in similar_fields:
            if similar_field != field_name:
                similar_values = self.field_value_mapping.get(similar_field, [])
                all_values.extend([(v, 0.7) for v in similar_values])  # Weight thấp hơn cho giá trị tương tự
        
        # Tính điểm tổng hợp
        value_scores = defaultdict(float)
        for val, weight in all_values:
            value_scores[val] += weight
        
        # Sắp xếp theo điểm và độ dài
        sorted_values = sorted(
            value_scores.items(),
            key=lambda x: (-x[1], len(x[0])),
            reverse=False
        )
        
        return [val[0] for val in sorted_values[:limit]]
    
    def update_form_history(self, new_form_data: Dict, user_id: Optional[int] = None) -> None:
        """
        Cải tiến: Cập nhật cả user preferences khi thêm dữ liệu mới
        """
        try:
            # Thêm thông tin user nếu có
            if user_id is not None:
                new_form_data['user_id'] = user_id
            
            # Thêm vào lịch sử
            self.form_history_path.append({'form_data': new_form_data, 'user_id': user_id})
            
            # Cập nhật field_value_mapping
            for field_name, value in new_form_data.items():
                if value and str(value).strip():
                    val_str = str(value).strip()
                    self.field_value_mapping[field_name].append(val_str)
                    
                    # Cập nhật user preferences
                    if user_id is not None:
                        if field_name not in self.user_preferences[user_id]:
                            self.user_preferences[user_id][field_name] = {
                                'count': 0,
                                'values': defaultdict(int)
                            }
                        self.user_preferences[user_id][field_name]['count'] += 1
                        self.user_preferences[user_id][field_name]['values'][val_str] += 1
            
            # Xây dựng lại models
            self._build_models()
            
            # Lưu vào file
            with open(self.form_history_path, 'w', encoding='utf-8') as f:
                json.dump(self.form_history_path, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating form history: {e}")