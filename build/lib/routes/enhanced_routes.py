from flask import Flask, request, jsonify
from utils.field_matcher import FieldMatcher 
from utils.ml_recommender import get_ml_suggestions, get_recommender
import json

matcher = FieldMatcher()

def register_enhanced_routes(app):
    """
    Đăng ký các route cho tính năng nâng cao
    """
    
    def find_best_match(values, filled_fields):
        """Tìm giá trị phù hợp nhất dựa trên các trường đã điền"""
        if not filled_fields:
            return None
            
        # Tìm giá trị có chứa thông tin từ các trường đã điền
        filled_values = ' '.join(filled_fields.values()).lower()
        
        for value in values:
            value_lower = value.lower()
            # Kiểm tra xem giá trị có chứa thông tin từ các trường đã điền không
            for filled_value in filled_fields.values():
                if filled_value.lower() in value_lower:
                    return value
                    
            # Kiểm tra độ tương đồng tổng thể
            if filled_values in value_lower:
                return value
        
        return None

    def find_by_context(field_code, filled_fields):
        """Tìm giá trị dựa trên ngữ cảnh các trường đã điền"""
        if not filled_fields:
            return None
        
        # Tìm tất cả các form trong lịch sử có các trường tương tự
        matched_forms = []
        
        for form in matcher.form_history:
            if 'form_data' not in form:
                continue
                
            form_data = form['form_data']
            match_score = 0
            
            # Tính điểm khớp dựa trên các trường đã điền
            for filled_name, filled_value in filled_fields.items():
                for form_field, form_value in form_data.items():
                    if filled_name == form_field and filled_value == form_value:
                        match_score += 2
                    elif filled_value == form_value:
                        match_score += 1
            
            if match_score > 0:
                # Nếu form này có trường cần điền
                if field_code in form_data:
                    matched_forms.append({
                        'form': form_data,
                        'score': match_score,
                        'value': form_data[field_code]
                    })
        
        if matched_forms:
            # Sắp xếp theo điểm khớp giảm dần
            matched_forms.sort(key=lambda x: x['score'], reverse=True)
            best_match = matched_forms[0]
            
            return {
                'value': best_match['value'],
                'confidence': min(best_match['score'] / (len(filled_fields) * 2), 1.0)
            }
        
        return None

   

   