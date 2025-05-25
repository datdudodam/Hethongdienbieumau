import re
from docx import Document
import os
import uuid
from werkzeug.utils import secure_filename
from config.config import UPLOADS_DIR
from flask import session
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
model_name = "Davlan/bert-base-multilingual-cased-ner-hrl"  # hỗ trợ nhiều ngôn ngữ
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)
ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

# Biến toàn cục để lưu đường dẫn tài liệu hiện tại
doc_path = None

def load_document(doc_path):
    """
    Tải nội dung từ tài liệu docx
    """
    doc = Document(doc_path)
    return "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])


def clean_label(text):
    """
    Làm sạch nhãn để tránh nhiễu đầu ra
    """
    text = re.sub(r"\[_\d+_\]", "", text)
    text = re.sub(r"[^\w\sÀ-ỹ]", "", text)
    text = text.strip()
    return text

def extract_fields(text,window_size=50):
    """
    Trích xuất tên trường chính xác từ văn bản, tách phần context thật sự gần mã trường nhất.
    """
    field_pattern = r"\[_\d+_\]|_{4,}|\.{4,}|\[fill\]"
    lines = text.splitlines()
    fields = []
    special_keywords = ["ngày", "tháng", "năm"]

    for i, line in enumerate(lines):
        matches = list(re.finditer(field_pattern, line))
        prev_match_end = 0

        for match in matches:
            field_code = match.group()
            match_start = match.start()
            match_end = match.end()

            # Lấy đoạn trước mã trường
            raw_context = line[prev_match_end:match_start].strip()
            prev_match_end = match_end

            # Fallback nếu không có context
            if not raw_context and i > 0:
                raw_context = lines[i - 1].strip()

            # 👉 Tách cụm cuối cùng nếu có dấu phẩy
            if "," in raw_context:
                context_segment = raw_context.split(",")[-1].strip()
            else:
                context_segment = raw_context

            cleaned_context = clean_label(context_segment)
            cleaned_context_lower = cleaned_context.lower()
            field_name = ""

            # Nếu là cụm ngắn gọn → giữ nguyên
            if len(cleaned_context.split()) <= 4 and not re.search(r"[:\.\-]", cleaned_context):
                field_name = cleaned_context
            else:
                # Ưu tiên từ khóa đặc biệt
                for kw in special_keywords:
                    if kw in cleaned_context_lower:
                        field_name = kw.capitalize()
                        break

                # Nếu không có từ khóa, dùng AI
                if not field_name:
                    limited_context = cleaned_context_lower[-window_size:]
                    label_text = ""
                    ner_results = ner_pipeline(limited_context)
                    for entity in ner_results:
                        if entity["entity_group"] in {"PER", "ORG", "LOC", "MISC"}:
                            label_text += entity["word"] + " "
                    if not label_text:
                        label_text = cleaned_context
                    field_name = label_text.strip()

            if field_name:
                fields.append({
                    "field_name": field_name,
                    "field_code": field_code
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
def extract_table_fields(doc_path,window_size=40): 
    """
    Trích xuất các trường từ bảng với độ chính xác cao hơn, tránh rút ngắn nhãn sai lệch.
    """
    doc = Document(doc_path)
    fields = []

    field_patterns = [r"\[_\d+_\]", r"\.{4,}", r"_{4,}", r"\[fill\]"]
    special_keywords = ["ngày", "tháng", "năm"]

    for table in doc.tables:
        for row in table.rows:
            if len(row.cells) >= 2:
                raw_label = row.cells[0].text.strip()
                field_value = row.cells[1].text.strip()

                for pattern in field_patterns:
                    match = re.search(pattern, field_value)
                    if match:
                        field_code = match.group()
                        field_name = ""

                        cleaned_label = clean_label(raw_label)
                        cleaned_label_lower = cleaned_label.lower()

                        # Nếu nhãn ngắn gọn, không chứa ký tự gây nhiễu → giữ nguyên
                        if len(cleaned_label.split()) <= 4 and not re.search(r"[:\.\-]", cleaned_label):
                            field_name = cleaned_label
                        else:
                            # Ưu tiên từ khóa đặc biệt
                            for kw in special_keywords:
                                if kw in cleaned_label_lower:
                                    field_name = kw.capitalize()
                                    break

                            # Nếu vẫn chưa có, dùng AI
                            if not field_name:
                                label_text = ""
                                limited_context = cleaned_label_lower[-window_size:]
                                ner_results = ner_pipeline(limited_context)
                                for entity in ner_results:
                                    if entity["entity_group"] in {"PER", "ORG", "LOC", "MISC"}:
                                        label_text += entity["word"] + " "
                                if not label_text:
                                    label_text = cleaned_label
                                field_name = label_text.strip()

                        if field_name:
                            fields.append({
                                "field_name": field_name.strip(),
                                "field_code": field_code
                            })
                        break

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