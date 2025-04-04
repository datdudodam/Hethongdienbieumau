
from docx import Document
import os
import uuid
from urllib.parse import quote
from config.config import UPLOADS_DIR
import datetime
from models.data_model import load_form_history, save_form_history
from flask import send_file
import os
def generate_docx(form_data, doc_path, custom_filename=None):
    """
    Tạo tài liệu docx từ mẫu và dữ liệu form, sau đó gửi file về client.
    """
    # Kiểm tra tài liệu mẫu
    if not doc_path or not os.path.exists(doc_path) or not doc_path.endswith('.docx'):
        return {"error": "Tài liệu mẫu không hợp lệ"}, 400

    try:
        doc = Document(doc_path)

        # Thay thế nội dung trong tài liệu
        for paragraph in doc.paragraphs:
            for field_code, value in form_data.items():
                paragraph.text = paragraph.text.replace(field_code, str(value) if value else '')

        # Xử lý các bảng
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for field_code, value in form_data.items():
                            paragraph.text = paragraph.text.replace(field_code, str(value) if value else '')

        # Lưu file DOCX tạm thời
        temp_filename = f'temp_output_{uuid.uuid4()}.docx'
        temp_doc_path = os.path.join(UPLOADS_DIR, temp_filename)

        if not os.path.exists(UPLOADS_DIR):
            os.makedirs(UPLOADS_DIR)

        doc.save(temp_doc_path)

        # Đặt tên file tải về
        download_filename = custom_filename if custom_filename else os.path.basename(doc_path)
        if not download_filename.endswith('.docx'):
            download_filename += '.docx'

        # Trả về file DOCX
        return send_file(temp_doc_path, as_attachment=True, download_name=download_filename)

    except Exception as e:
        print(f"Lỗi khi xử lý tài liệu: {str(e)}")
        return {"error": "Lỗi khi xử lý tài liệu. Vui lòng thử lại."}, 500