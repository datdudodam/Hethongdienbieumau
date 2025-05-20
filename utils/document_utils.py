import re
from docx import Document
import os
import uuid
from werkzeug.utils import secure_filename
from config.config import UPLOADS_DIR
from flask import session


# Biến toàn cục để lưu đường dẫn tài liệu hiện tại
doc_path = None

def load_document(doc_path):
    """
    Tải nội dung từ tài liệu docx
    """
    doc = Document(doc_path)
    return "\n".join([para.text.strip() for para in doc.paragraphs])

def extract_fields(text):
    """
    Trích xuất các trường từ văn bản
    """
    matches = re.finditer(r"\[_\d+_\]", text)
    fields = []
    special_words = {"ngày", "tháng", "năm"}
    
    for match in matches:
        end_index = match.start()
        field_name = ""
        i = end_index - 1
        while i >= 0 and text[i] == " ":
            i -= 1
        
        for word in special_words:
            if text[max(0, i - len(word) + 1):end_index].strip().lower() == word:
                field_name = word
                break
        
        if not field_name:
            for j in range(i, -1, -1):
                if text[j].isupper():
                    field_name = text[j:end_index].strip()
                    break
        
        if field_name:
            fields.append({"field_name": field_name, "field_code": match.group()})
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
    
    # Xác định loại biểu mẫu
    from utils.form_type_detector import FormTypeDetector
    detector = FormTypeDetector()
    form_type = detector.detect_form_type(filepath)
    
    # Trả về thông tin về số lần upload còn lại nếu là gói miễn phí
    if current_user.is_authenticated and current_user.subscription_type == 'free':
        return {
            "message": "File uploaded successfully", 
            "filename": filename,
            "free_downloads_left": current_user.free_downloads_left,
            "form_type": form_type
        }, 200
    
    return {"message": "File uploaded successfully", "filename": filename, "form_type": form_type}, 200

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
    """
    doc = Document(doc_path)
    fields = []
    
    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) >= 2:
                field_name = row.cells[0].text.strip()
                field_value = row.cells[1].text.strip()
                
                match = re.search(r"\[_\d+_\]", field_value)
                if match:
                    field_code = match.group()
                    fields.append({
                        "field_name": field_name,
                        "field_code": field_code
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

    # Sắp xếp từ trên xuống dưới (giả sử có key 'y' biểu thị vị trí theo chiều dọc)
    all_fields.sort(key=lambda field: field.get("y", 0))  # bạn có thể thay "y" bằng "position" hay tên key phù hợp

    # Loại bỏ trùng lặp dựa trên `field_code`
    combined_fields = []
    seen_codes = set()

    for field in all_fields:
        code = field["field_code"]
        if code not in seen_codes:
            combined_fields.append(field)
            seen_codes.add(code)

    return combined_fields