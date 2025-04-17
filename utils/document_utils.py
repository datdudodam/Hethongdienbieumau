import re
from docx import Document
import os
import uuid
from werkzeug.utils import secure_filename
from config.config import UPLOADS_DIR


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
    Xử lý tải lên tài liệu
    """
    global doc_path
    
    if file.filename == '':
        return {"error": "No selected file"}, 400
    
    if not file.filename.endswith('.docx'):
        return {"error": "Only DOCX files are allowed"}, 400
    
    filename = secure_filename(str(uuid.uuid4()) + '_' + file.filename)
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)
    
    doc_path = filepath
    
    return {"message": "File uploaded successfully", "filename": filename}, 200

def get_doc_path():
    """
    Trả về đường dẫn tài liệu hiện tại
    """
    return doc_path

def set_doc_path(path):
    """
    Thiết lập đường dẫn tài liệu hiện tại
    """
    global doc_path
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
