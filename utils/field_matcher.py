import numpy as np
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gensim.models import Word2Vec
import os
import json
from typing import List, Dict, Optional, Tuple, Set, Union, Any
from collections import defaultdict
import difflib
import unicodedata
from sentence_transformers import SentenceTransformer
from config.config import FORM_HISTORY_PATH

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
        self.similarity_cache = {}
        self.processed_text_cache = {}
        self.field_index = defaultdict(list)
        self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        
        self.form_history = self._load_form_history()
        self._load_user_preferences()
        self._build_field_value_mapping()
        self._build_field_index()
        self._build_models()

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

    def _initialize_stopwords(self) -> Set[str]:
        english_stopwords = set(stopwords.words('english'))
        vietnamese_stopwords = {
            'của', 'và', 'các', 'có', 'được', 'trong', 'là', 'cho', 'những', 'với',
            'không', 'này', 'đến', 'khi', 'về', 'như', 'từ', 'một', 'người', 'năm',
            'bị', 'đã', 'sẽ', 'cũng', 'vào', 'ra', 'nếu', 'để', 'tại', 'theo',
            'sau', 'trên', 'hoặc', 'tôi', 'bạn', 'anh', 'chị', 'họ', 'của', 'mình'
        }
        return english_stopwords.union(vietnamese_stopwords)

    def _load_form_history(self) -> List[Dict]:
        try:
            if os.path.exists(self.form_history_path):
                with open(self.form_history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data
            return []
        except Exception as e:
            print(f"Unexpected error loading form history: {str(e)}")
            return []

    def _build_field_value_mapping(self):
        special_fields = {'form_id', 'document_name'}
        for form in self.form_history:
            if isinstance(form, dict) and 'form_data' in form:
                for field_name, value in form['form_data'].items():
                    if field_name not in special_fields and value and (val_str := str(value).strip()):
                        self.field_value_mapping[field_name].append(val_str)

    def _build_field_index(self):
        for idx, form in enumerate(self.form_history):
            if isinstance(form, dict) and 'form_data' in form:
                for field_name in form['form_data'].keys():
                    normalized_field = self._normalize_field_name(field_name)
                    self.field_index[normalized_field].append((idx, field_name))

    def _load_user_preferences(self):
        for form in self.form_history:
            if isinstance(form, dict) and 'user_id' in form:
                user_id = form['user_id']
                if 'form_data' in form:
                    for field_name, value in form['form_data'].items():
                        if value and str(value).strip():
                            if field_name not in self.user_preferences[user_id]:
                                self.user_preferences[user_id][field_name] = {
                                    'count': 0,
                                    'values': defaultdict(int)
                                }
                            self.user_preferences[user_id][field_name]['count'] += 1
                            self.user_preferences[user_id][field_name]['values'][str(value).strip()] += 1

    def _preprocess_text(self, text: str) -> str:
        if not text:
            return ""
        if text in self.processed_text_cache:
            return self.processed_text_cache[text]
        normalized = unicodedata.normalize('NFC', text.lower())
        cleaned = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', normalized)
        for target, synonyms in sorted(self.synonym_map.items(), key=lambda x: len(x[0]), reverse=True):
            for synonym in sorted(synonyms, key=len, reverse=True):
                cleaned = re.sub(r'\b' + re.escape(synonym) + r'\b', target, cleaned)
        tokens = cleaned.split()
        filtered_tokens = [token for token in tokens if token not in self.stop_words]
        result = ' '.join(filtered_tokens)
        self.processed_text_cache[text] = result
        return result

    def _normalize_field_name(self, text: str) -> str:
        if not text:
            return ""
        text = unicodedata.normalize('NFC', text.lower())
        synonym_items = sorted(self.synonym_map.items(), key=lambda x: max(len(s) for s in x[1]), reverse=True)
        for target, synonyms in synonym_items:
            for synonym in sorted(synonyms, key=len, reverse=True):
                text = re.sub(r'\b' + re.escape(synonym) + r'\b', target, text)
        text = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', text)
        tokens = [token for token in text.split() if token not in self.stop_words]
        return ' '.join(tokens).strip()

    def _build_models(self):
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
        
        if processed_fields:
            self.vectorizer = TfidfVectorizer()
            self.field_vectors = self.vectorizer.fit_transform(processed_fields)
            self.field_names = field_names
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
                for field, processed in zip(field_names, processed_fields):
                    tokens = processed.split()
                    if tokens:
                        embeddings = [self.word2vec_model.wv[token] for token in tokens if token in self.word2vec_model.wv]
                        if embeddings:
                            self.field_embeddings[field] = np.mean(embeddings, axis=0)

    def _calculate_sbert_similarity(self, text1: str, text2: str) -> float:
        cache_key = f"sbert_{text1}||{text2}"
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]
        vec1 = self.sbert_model.encode([text1])[0]
        vec2 = self.sbert_model.encode([text2])[0]
        similarity = cosine_similarity([vec1], [vec2])[0][0]
        self.similarity_cache[cache_key] = similarity
        return similarity

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        cache_key = f"{text1}||{text2}"
        if cache_key in self.similarity_cache:
            return self.similarity_cache[cache_key]
        
        norm1 = self._normalize_field_name(text1)
        norm2 = self._normalize_field_name(text2)
        
        if norm1 == norm2:
            self.similarity_cache[cache_key] = 1.0
            return 1.0
        
        seq_sim = difflib.SequenceMatcher(None, norm1, norm2).quick_ratio()
        tfidf_sim = 0.0
        if seq_sim < 0.8 and self.vectorizer and self.field_vectors is not None:
            query_vec = self.vectorizer.transform([self._preprocess_text(text1)])
            target_vec = self.vectorizer.transform([self._preprocess_text(text2)])
            tfidf_sim = cosine_similarity(query_vec, target_vec)[0][0]
        
        w2v_sim = 0.0
        if seq_sim < 0.8 and tfidf_sim < 0.8 and self.word2vec_model:
            tokens1 = self._preprocess_text(text1).split()
            tokens2 = self._preprocess_text(text2).split()
            if tokens1 and tokens2:
                valid_tokens1 = [t for t in tokens1 if t in self.word2vec_model.wv]
                valid_tokens2 = [t for t in tokens2 if t in self.word2vec_model.wv]
                if valid_tokens1 and valid_tokens2:
                    w2v_sim = self.word2vec_model.wv.n_similarity(valid_tokens1, valid_tokens2)
        
        sbert_sim = 0.0
        if seq_sim < 0.8 and tfidf_sim < 0.8 and w2v_sim < 0.8:
            sbert_sim = self._calculate_sbert_similarity(text1, text2)
        
        combined_sim = 0.25 * seq_sim + 0.25 * tfidf_sim + 0.2 * w2v_sim + 0.3 * sbert_sim
        self.similarity_cache[cache_key] = combined_sim
        return combined_sim

    def _boost_by_frequency(self, field_name: str, base_score: float) -> float:
        frequency = len(self.field_value_mapping.get(field_name, []))
        boost = min(frequency / 10, 1.0)
        return base_score + 0.05 * boost

    def _exact_token_match_boost(self, model_field: str, data_field: str) -> float:
        model_tokens = set(self._preprocess_text(model_field).split())
        data_tokens = set(self._preprocess_text(data_field).split())
        overlap = model_tokens & data_tokens
        return 0.1 * len(overlap)

    def match_fields(
            self,
            form_model: Union[str, List[str]],
            threshold: float = 0.65,
            user_id: Optional[str] = None,
            fast_mode: bool = False
        ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Optimized field matching using indexing and caching for instant UI display.
        Returns a dict of matched fields with up to 3 results per field.
        """
        if isinstance(form_model, str):
            form_model = [form_model]

        all_matches = defaultdict(list)
        seen_matches = set()

        # Cache user records
        cache_key = f"user_records_{user_id}"
        if hasattr(self, cache_key):
            user_records = getattr(self, cache_key)
        else:
            str_user_id = str(user_id) if user_id is not None else None
            user_records = [record for record in self.form_history if str(record.get("user_id")) == str_user_id]
            user_records = list(reversed(user_records))  # Prioritize recent records
            setattr(self, cache_key, user_records)

        if not user_records:
            return {}

        # Limit records to check for performance
        records_to_check = user_records[:5] if fast_mode else user_records[:10]

        for model_field in form_model:
            normalized_model = self._normalize_field_name(model_field)
            potential_matches = []

            # Use field_index for quick lookup
            if normalized_model in self.field_index:
                for record_idx, data_field in self.field_index[normalized_model]:
                    if record_idx >= len(records_to_check):
                        continue
                    form_data = records_to_check[record_idx].get("form_data", {})
                    value = form_data.get(data_field)
                    if not value or not str(value).strip():
                        continue
                    key = (model_field, data_field, value)
                    if key in seen_matches:
                        continue
                    similarity = 1.0  # Exact match via index
                    similarity += self._boost_by_frequency(data_field, similarity)
                    potential_matches.append((similarity, model_field, data_field, value))
                    seen_matches.add(key)

            # Fallback to similarity calculation for non-indexed fields
            for idx, record in enumerate(records_to_check):
                form_data = record.get("form_data", {})
                for data_field in form_data.keys():
                    if len(all_matches[model_field]) >= 3:
                        break
                    value = form_data[data_field]
                    key = (model_field, data_field, value)
                    if key in seen_matches or not value or not str(value).strip():
                        continue
                    similarity = self._calculate_similarity(model_field, data_field)
                    similarity += self._boost_by_frequency(data_field, similarity)
                    similarity += self._exact_token_match_boost(model_field, data_field)
                    if similarity >= threshold:
                        potential_matches.append((similarity, model_field, data_field, value))
                        seen_matches.add(key)

            # Sort and limit matches
            potential_matches.sort(reverse=True, key=lambda x: x[0])
            for sim, m_field, d_field, value in potential_matches[:3]:
                existing_values = {match["value"] for match in all_matches[m_field]}
                if value not in existing_values:
                    all_matches[m_field].append({
                        "matched_field": d_field,
                        "value": value,
                        "similarity": round(sim, 4)
                    })

            # Early termination if enough matches are found
            if len(all_matches[model_field]) >= 3:
                continue

        self.matched_fields = all_matches
        return all_matches

    def find_most_similar_field(self, query: str, top_n: int = 3) -> List[Tuple[str, float]]:
        if not query or not self.field_names or not self.vectorizer:
            return []
        
        try:
            processed_query = self._preprocess_text(query)
            tfidf_results = []
            if self.vectorizer and self.field_vectors is not None:
                query_vec = self.vectorizer.transform([processed_query])
                similarities = cosine_similarity(query_vec, self.field_vectors).flatten()
                tfidf_results = [(self.field_names[i], float(similarities[i])) 
                                for i in np.argsort(similarities)[-top_n:][::-1]
                                if similarities[i] > 0]
            
            w2v_results = []
            if self.word2vec_model and self.field_embeddings:
                query_tokens = processed_query.split()
                if query_tokens:
                    valid_tokens = [token for token in query_tokens if token in self.word2vec_model.wv]
                    if valid_tokens:
                        query_embedding = np.mean([self.word2vec_model.wv[token] for token in valid_tokens], axis=0)
                        similarities = {}
                        for field, embedding in self.field_embeddings.items():
                            if embedding is not None:
                                sim = cosine_similarity(
                                    query_embedding.reshape(1, -1), 
                                    embedding.reshape(1, -1)
                                )[0][0]
                                similarities[field] = sim
                        w2v_results = sorted(
                            [(field, sim) for field, sim in similarities.items()], 
                            key=lambda x: x[1], 
                            reverse=True
                        )[:top_n]
            
            combined_results = defaultdict(float)
            for field, score in tfidf_results:
                combined_results[field] += score * 0.5
            for field, score in w2v_results:
                combined_results[field] += score * 0.5
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
        all_values = []
        direct_values = self.field_value_mapping.get(field_name, [])
        all_values.extend([(v, 1.0) for v in direct_values])
        
        if user_id is not None and user_id in self.user_preferences:
            if field_name in self.user_preferences[user_id]:
                user_values = self.user_preferences[user_id][field_name]['values']
                for val, count in user_values.items():
                    all_values.append((val, count * 2.0))
        
        similar_fields = self.find_most_similar_field(field_name, top_n=3)
        for similar_field, _ in similar_fields:
            if similar_field != field_name:
                similar_values = self.field_value_mapping.get(similar_field, [])
                all_values.extend([(v, 0.7) for v in similar_values])
        
        value_scores = defaultdict(float)
        for val, weight in all_values:
            value_scores[val] += weight
        
        sorted_values = sorted(
            value_scores.items(),
            key=lambda x: (-x[1], len(x[0])),
            reverse=False
        )
        return [val[0] for val in sorted_values[:limit]]

    def update_form_history(self, new_form_data: Dict, user_id: Optional[int] = None, doc_path: Optional[str] = None) -> None:
        try:
            if user_id is not None:
                new_form_data['user_id'] = user_id
            if doc_path is not None:
                from utils.form_type_detector import FormTypeDetector
                detector = FormTypeDetector(self.form_history_path)
                form_type = detector.detect_form_type(doc_path)
                new_form_data['form_type'] = form_type
            
            self.form_history.append({'form_data': new_form_data, 'user_id': user_id})
            for field_name, value in new_form_data.items():
                if value and str(value).strip():
                    val_str = str(value).strip()
                    self.field_value_mapping[field_name].append(val_str)
                    normalized_field = self._normalize_field_name(field_name)
                    self.field_index[normalized_field].append((len(self.form_history) - 1, field_name))
                    if user_id is not None:
                        if field_name not in self.user_preferences[user_id]:
                            self.user_preferences[user_id][field_name] = {
                                'count': 0,
                                'values': defaultdict(int)
                            }
                        self.user_preferences[user_id][field_name]['count'] += 1
                        self.user_preferences[user_id][field_name]['values'][val_str] += 1
            
            self._build_models()
            with open(self.form_history_path, 'w', encoding='utf-8') as f:
                json.dump(self.form_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating form history: {e}")