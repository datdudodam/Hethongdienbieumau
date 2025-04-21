import json
import os
from config.config import TEMPLATE_FORMS_PATH

def load_template_forms():
    """
    Tải danh sách biểu mẫu tham khảo từ file JSON
    """
    try:
        if os.path.exists(TEMPLATE_FORMS_PATH):
            with open(TEMPLATE_FORMS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Đảm bảo dữ liệu trả về luôn là một list
                if not isinstance(data, list):
                    return []
                return data
        return []
    except Exception as e:
        print(f"Error loading template forms: {str(e)}")
        return []

def save_template_forms(data):
    """
    Lưu danh sách biểu mẫu tham khảo vào file JSON
    """
    # Đảm bảo thư mục tồn tại
    os.makedirs(os.path.dirname(TEMPLATE_FORMS_PATH), exist_ok=True)
    with open(TEMPLATE_FORMS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_template_form_by_id(template_id):
    """
    Lấy biểu mẫu tham khảo theo ID
    """
    templates = load_template_forms()
    return next((t for t in templates if t.get('template_id') == template_id), None)

def add_template_form(template_data):
    """
    Thêm biểu mẫu tham khảo mới
    """
    templates = load_template_forms()
    templates.append(template_data)
    save_template_forms(templates)
    return template_data

def update_template_form(template_id, updated_data):
    """
    Cập nhật biểu mẫu tham khảo
    """
    templates = load_template_forms()
    for i, template in enumerate(templates):
        if template.get('template_id') == template_id:
            templates[i].update(updated_data)
            save_template_forms(templates)
            return templates[i]
    return None

def delete_template_form(template_id):
    """
    Xóa biểu mẫu tham khảo
    """
    templates = load_template_forms()
    templates = [t for t in templates if t.get('template_id') != template_id]
    save_template_forms(templates)
    return True

def search_template_forms(query):
    """
    Tìm kiếm biểu mẫu tham khảo theo từ khóa
    """
    templates = load_template_forms()
    if not query:
        return templates
    
    query = query.lower()
    return [t for t in templates if 
            query in t.get('name', '').lower() or 
            query in t.get('description', '').lower() or
            query in t.get('category', '').lower()]