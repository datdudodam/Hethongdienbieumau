import re
from docx import Document
from utils.document_utils import extract_fields, load_document

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
    đồng thời loại bỏ các trường trùng lặp dựa trên `field_code`.
    """
    # Trích xuất từ văn bản và bảng
    text = load_document(doc_path)
    text_fields = extract_fields(text)
    table_fields = extract_table_fields(doc_path)
    
    # Kết hợp & loại bỏ trùng lặp
    combined_fields = []
    seen_codes = set()

    for field in text_fields + table_fields:
        code = field["field_code"]
        if code not in seen_codes:
            combined_fields.append(field)
            seen_codes.add(code)
    
    return combined_fields
