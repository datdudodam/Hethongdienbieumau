# services/field_matcher.py
import numpy as np
import re
import json
import os
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
import difflib
import unicodedata
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedFieldMatcher:
    def __init__(self, form_history_path: str, min_similarity_threshold: float = 0.7):
        self.form_history_path = Path(form_history_path)
        self.min_similarity = min_similarity_threshold
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize all components with proper error handling"""
        self.stop_words = self._load_stopwords()
        self.field_value_map = defaultdict(list)
        self.field_frequency = defaultdict(int)
        self.value_frequency = defaultdict(int)
        self.user_field_value_map = defaultdict(lambda: defaultdict(list))  # user_id -> field -> [values]
        self.user_value_frequency = defaultdict(int)  # (user_id, field, value) -> frequency
        self.last_updated = None
        
        try:
            self._load_history()
            logger.info("Field matcher initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize field matcher: {str(e)}")
            raise

    def _load_stopwords(self) -> Set[str]:
        """Load combined stopwords for Vietnamese and English"""
        # Basic Vietnamese stopwords
        vi_stopwords = {
            'của', 'và', 'các', 'cho', 'với', 'có', 'được', 'trong', 'là', 'ở',
            'tại', 'từ', 'vào', 'trên', 'sau', 'khi', 'nếu', 'để', 'một', 'những'
        }
        
        # Add more stopwords as needed
        return vi_stopwords
    
    def _normalize_vietnamese(self, text: str) -> str:
        """Normalize Vietnamese text for better matching"""
        if not text:
            return ""
            
        # Normalize unicode and lowercase
        text = unicodedata.normalize('NFC', text.lower())
        
        # Remove special chars but keep Vietnamese diacritics
        text = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', text)
        
        return text.strip()
    
    def _load_history(self):
        """Load form history with proper error handling"""
        if not self.form_history_path.exists():
            logger.warning(f"Form history file not found at {self.form_history_path}")
            return
            
        try:
            with open(self.form_history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            for entry in history:
                if not isinstance(entry, dict):
                    continue
                    
                form_data = entry.get('form_data', {})
                timestamp = entry.get('timestamp')
                user_id = entry.get('user_id')  # Lấy user_id từ entry
                
                for field, value in form_data.items():
                    if not field or not value:
                        continue
                        
                    norm_field = self._normalize_vietnamese(field)
                    norm_value = self._normalize_vietnamese(str(value))
                    
                    # Lưu vào map chung
                    self.field_value_map[norm_field].append(norm_value)
                    self.field_frequency[norm_field] += 1
                    self.value_frequency[(norm_field, norm_value)] += 1
                    
                    # Lưu vào map theo user_id nếu có
                    if user_id:
                        self.user_field_value_map[user_id][norm_field].append(norm_value)
                        self.user_value_frequency[(user_id, norm_field, norm_value)] += 1
                    
            self.last_updated = datetime.now()
            logger.info(f"Loaded {len(history)} form entries")
            
        except Exception as e:
            logger.error(f"Failed to load form history: {str(e)}")
            raise
    def _find_similar_fields(self, query: str, top_n: int = 3) -> List[Tuple[str, float]]:
        """Find similar fields using multiple matching strategies"""
        if not query:
            return []
            
        # 1. Exact match
        if query in self.field_value_map:
            return [(query, 1.0)]
            
        # 2. Partial matches
        potential_matches = []
        query_words = set(query.split())
        
        for field in self.field_value_map.keys():
            if not field:
                continue
                
            # Simple word overlap
            field_words = set(field.split())
            overlap = len(query_words & field_words) / max(len(query_words), 1)
            
            # Sequence similarity
            seq_sim = difflib.SequenceMatcher(None, query, field).ratio()
            
            # Combined score
            score = 0.6 * seq_sim + 0.4 * overlap
            
            if score >= self.min_similarity:
                potential_matches.append((field, score))
                
        # Return top matches
        return sorted(potential_matches, key=lambda x: x[1], reverse=True)[:top_n]

    def get_suggested_values(self, field_name: str, limit: int = 5, user_id: Optional[str] = None) -> List[str]:
        """Get suggested values for a field with frequency ranking"""
        norm_field = self._normalize_vietnamese(field_name)
        
        # Nếu có user_id, ưu tiên gợi ý từ dữ liệu của user đó
        if user_id and user_id in self.user_field_value_map:
            # Lấy giá trị từ user hiện tại
            user_exact_matches = self.user_field_value_map[user_id].get(norm_field, [])
            
            # Tìm các trường tương tự
            similar_fields = self._find_similar_fields(norm_field)
            user_similar_values = []
            
            for similar_field, _ in similar_fields:
                user_similar_values.extend(self.user_field_value_map[user_id].get(similar_field, []))
                
            # Kết hợp và xếp hạng giá trị của user
            user_values = user_exact_matches + user_similar_values
            if user_values:  # Nếu có dữ liệu của user
                value_scores = defaultdict(float)
                
                for val in user_values:
                    # Điểm cao hơn cho trường khớp chính xác
                    score = 3.0 if val in user_exact_matches else 1.5  # Điểm cao hơn cho dữ liệu user
                    # Thêm điểm thưởng tần suất
                    score += self.user_value_frequency.get((user_id, norm_field, val), 0) * 0.2  # Trọng số cao hơn
                    value_scores[val] += score
                    
                # Bổ sung thêm một số gợi ý chung nếu gợi ý của user ít
                if len(value_scores) < limit:
                    # Lấy gợi ý chung
                    general_values = self.field_value_map.get(norm_field, [])
                    for val in general_values:
                        if val not in value_scores:  # Chỉ thêm các giá trị chưa có
                            score = 1.0  # Điểm thấp hơn cho dữ liệu chung
                            score += self.value_frequency.get((norm_field, val), 0) * 0.1
                            value_scores[val] += score
                
                # Sắp xếp theo điểm giảm dần
                ranked_values = sorted(
                    value_scores.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                return [val[0] for val in ranked_values[:limit]]
        
        # Nếu không có user_id hoặc không có dữ liệu của user, sử dụng gợi ý chung
        # Get exact matches first
        exact_matches = self.field_value_map.get(norm_field, [])
        
        # Find similar fields
        similar_fields = self._find_similar_fields(norm_field)
        similar_values = []
        
        for similar_field, _ in similar_fields:
            similar_values.extend(self.field_value_map.get(similar_field, []))
            
        # Combine and rank values
        all_values = exact_matches + similar_values
        value_scores = defaultdict(float)
        
        for val in all_values:
            # Higher score for exact field matches
            score = 2.0 if val in exact_matches else 1.0
            # Add frequency bonus
            score += self.value_frequency.get((norm_field, val), 0) * 0.1
            value_scores[val] += score
            
        # Sort by score descending
        ranked_values = sorted(
            value_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [val[0] for val in ranked_values[:limit]]
    
    
    
    def generate_suggestions(self, partial_data: Dict[str, str], user_id: Optional[str] = None) -> Dict[str, Dict]:
        """Generate suggestions for multiple fields at once"""
        suggestions = {}
        
        for field, value in partial_data.items():
            if not value:  # Only suggest for empty fields
                field_suggestions = self.get_suggested_values(field, user_id=user_id)
                if field_suggestions:
                    suggestions[field] = {
                        "values": field_suggestions,
                        "confidence": self._calculate_confidence(field, field_suggestions[0], user_id)
                    }
                    
        return suggestions
    
    def _calculate_confidence(self, field: str, value: str, user_id: Optional[str] = None) -> float:
        """Calculate confidence score for a suggestion"""
        norm_field = self._normalize_vietnamese(field)
        norm_value = self._normalize_vietnamese(value)
        
        # Nếu có user_id, ưu tiên tính điểm tin cậy dựa trên dữ liệu của user
        if user_id:
            user_freq = self.user_value_frequency.get((user_id, norm_field, norm_value), 0)
            if user_freq > 0:  # Nếu user đã từng sử dụng giá trị này
                return min(0.95, 0.7 + user_freq * 0.15)  # Điểm tin cậy cao hơn cho dữ liệu user
        
        # Base confidence on frequency
        freq = self.value_frequency.get((norm_field, norm_value), 0)
        return min(0.9, 0.5 + freq * 0.1)
    
    def update_field_value(self, field_name: str, field_value: str, user_id: Optional[str] = None):
        """Update the field value history"""
        if not field_name or not field_value:
            return
            
        norm_field = self._normalize_vietnamese(field_name)
        norm_value = self._normalize_vietnamese(str(field_value))
        
        # Update in-memory storage
        self.field_value_map[norm_field].append(norm_value)
        self.field_frequency[norm_field] += 1
        self.value_frequency[(norm_field, norm_value)] += 1
        
        # Cập nhật dữ liệu theo user_id nếu có
        if user_id:
            self.user_field_value_map[user_id][norm_field].append(norm_value)
            self.user_value_frequency[(user_id, norm_field, norm_value)] += 1
        
        # Append to history file
        try:
            new_entry = {
                "timestamp": datetime.now().isoformat(),
                "form_data": {field_name: field_value}
            }
            
            if self.form_history_path.exists():
                with open(self.form_history_path, 'r+', encoding='utf-8') as f:
                    try:
                        history = json.load(f)
                        history.append(new_entry)
                        f.seek(0)
                        json.dump(history, f, ensure_ascii=False, indent=2)
                    except json.JSONDecodeError:
                        # Handle corrupted file
                        history = [new_entry]
                        json.dump(history, f, ensure_ascii=False, indent=2)
            else:
                with open(self.form_history_path, 'w', encoding='utf-8') as f:
                    json.dump([new_entry], f, ensure_ascii=False, indent=2)
                    
            self.last_updated = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to update form history: {str(e)}")
            raise