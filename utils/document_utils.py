import re
from docx import Document
import os
import uuid
from werkzeug.utils import secure_filename
from config.config import UPLOADS_DIR
from flask import session
from utils.fuzzy_matcher import FuzzyMatcher  # Import lớp FuzzyMatcher mới

# Biến toàn cục để lưu đường dẫn tài liệu hiện tại
doc_path = None
fuzzy_matcher = FuzzyMatcher()  # Khởi tạo FuzzyMatcher

def load_document(doc_path):
    """
    Tải nội dung từ tài liệu docx
    """
    doc = Document(doc_path)
    return "\n".join([para.text.strip() for para in doc.paragraphs])

def extract_fields(text):
    """
    Trích xuất các trường từ văn bản với khả năng nhận diện nâng cao
    Sử dụng FuzzyMatcher để cải thiện độ chính xác
    """
    # Tìm tất cả các mã trường [_123_]
    matches = re.finditer(r"\[_\d+_\]", text)
    fields = []
    
    for match in matches:
        field_code = match.group()
        field_code_position = match.start()
        
        # Sử dụng FuzzyMatcher để tìm tên trường
        field_name = fuzzy_matcher.find_field_name(text, field_code_position)
        
        if field_name:
            # Phân tích ngữ cảnh của trường
            context_info = fuzzy_matcher.get_field_context(text, field_name, field_code_position)
            
            fields.append({
                "field_name": field_name,
                "field_code": field_code,
                "context_info": context_info
            })
    
    return fields

def upload_document(file):
    """
    Xử lý tải lên tài liệu và kiểm tra giới hạn upload của người dùng
    """
    global doc_path
    
    if file.filename == '':
        return {"error": "No selected file"}, 400
    
    if not file.filename.endswith('.docx'):
        return {"error": "Only DOCX files are allowed"}, 400
    
    # Kiểm tra giới hạn upload của người dùng
    from flask_login import current_user
    if current_user.is_authenticated:
        # Kiểm tra loại gói đăng ký
        if current_user.subscription_type == 'free':
            # Kiểm tra số lần upload còn lại
            if current_user.free_downloads_left <= 0:
                return {"error": "Bạn đã sử dụng hết lượt upload miễn phí. Vui lòng nâng cấp lên gói VIP để tiếp tục sử dụng.", "upgrade_required": True}, 403
            
            # Giảm số lần upload còn lại
            from models.user import db
            current_user.free_downloads_left -= 1
            db.session.commit()
        elif current_user.subscription_type == 'standard':
            # Kiểm tra số lần upload trong tháng
            if current_user.monthly_download_count >= 100:
                return {"error": "Bạn đã sử dụng hết 100 lượt upload trong tháng. Vui lòng nâng cấp lên gói VIP để không giới hạn số lần upload.", "upgrade_required": True}, 403
            
            # Tăng số lần upload trong tháng
            from models.user import db
            current_user.monthly_download_count += 1
            db.session.commit()
        # Gói VIP không giới hạn số lần upload
    
    filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)
    
    # Lưu đường dẫn vào cả session và biến toàn cục
    set_doc_path(filepath)
    
    # Trả về thông tin về số lần upload còn lại nếu là gói miễn phí
    if current_user.is_authenticated and current_user.subscription_type == 'free':
        return {
            "message": "File uploaded successfully", 
            "filename": filename,
            "free_downloads_left": current_user.free_downloads_left
        }, 200
    
    return {"message": "File uploaded successfully", "filename": filename}, 200

def get_doc_path():
    """
    Trả về đường dẫn tài liệu hiện tại từ session hoặc biến toàn cục
    """
    try:
        # Ưu tiên lấy từ session nếu có
        if 'doc_path' in session:
            return session['doc_path']
        return doc_path
    except Exception as e:
        print(f"Error in get_doc_path: {str(e)}")
        return doc_path

def set_doc_path(path):
    """
    Thiết lập đường dẫn tài liệu hiện tại vào session và biến toàn cục
    """
    global doc_path
    try:
        # Lưu vào cả session và biến toàn cục
        session['doc_path'] = path
    except Exception as e:
        print(f"Error setting doc_path in session: {str(e)}")
    # Vẫn lưu vào biến toàn cục để đảm bảo tương thích ngược
    doc_path = path

def extract_table_fields(doc_path):
    """
    Trích xuất các trường từ bảng trong tài liệu docx.
    Trường hợp bảng có dạng: | Tên trường | [_123_] |
    Sử dụng FuzzyMatcher để chuẩn hóa tên trường
    """
    doc = Document(doc_path)
    fields = []
    
    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) >= 2:
                raw_field_name = row.cells[0].text.strip()
                field_value = row.cells[1].text.strip()
                
                # Chuẩn hóa tên trường bằng FuzzyMatcher
                normalized_field_name = fuzzy_matcher.normalize_text(raw_field_name)
                
                # Tìm trường phù hợp nhất trong từ điển đồng nghĩa
                best_match = None
                highest_similarity = 0
                
                for standard_field, synonyms in fuzzy_matcher.synonym_map.items():
                    for synonym in [standard_field] + synonyms:
                        similarity = fuzzy_matcher.calculate_similarity(normalized_field_name, synonym, 'hybrid')
                        if similarity > highest_similarity and similarity > fuzzy_matcher.similarity_threshold:
                            highest_similarity = similarity
                            best_match = standard_field
                
                field_name = best_match if best_match else raw_field_name
                
                match = re.search(r"\[_\d+_\]", field_value)
                if match:
                    field_code = match.group()
                    fields.append({
                        "field_name": field_name,
                        "field_code": field_code,
                        "raw_field_name": raw_field_name,
                        "similarity_score": highest_similarity if best_match else None
                    })
    return fields

def extract_all_fields(doc_path):
    """
    Trích xuất tất cả các trường từ tài liệu (bao gồm văn bản và bảng),
    sắp xếp từ trên xuống dưới và loại bỏ các trường trùng lặp dựa trên `field_code`.
    """
    # Trích xuất từ văn bản và bảng
    text = load_document(doc_path)
    text_fields = extract_fields(text)
    table_fields = extract_table_fields(doc_path)
    
    # Gộp tất cả các trường lại
    all_fields = text_fields + table_fields

    # Sắp xếp từ trên xuống dưới dựa trên vị trí xuất hiện trong tài liệu
    # Đối với text_fields, vị trí đã được xác định trong extract_fields
    # Đối với table_fields, cần thêm logic để xác định vị trí
    
    # Tạm thời sắp xếp theo thứ tự xuất hiện (text_fields trước, table_fields sau)
    all_fields.sort(key=lambda f: f.get("position", 0))

    # Loại bỏ trùng lặp dựa trên `field_code`
    combined_fields = []
    seen_codes = set()

    for field in all_fields:
        code = field["field_code"]
        if code not in seen_codes:
            combined_fields.append(field)
            seen_codes.add(code)

    return combined_fields