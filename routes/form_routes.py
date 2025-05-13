from flask import render_template, request, jsonify
from utils.document_utils import load_document, extract_all_fields, get_doc_path, set_doc_path

from models.data_model import load_db, save_db, load_form_history, save_form_history
import os
import uuid
import datetime

def register_form_routes(app):
    """
    Đăng ký các route cho biểu mẫu
    """
    @app.route('/form')
    def form():
        doc_path = get_doc_path()
        if not doc_path:
            return jsonify({'error': 'No document uploaded'}), 400
        text = load_document(doc_path)
        fields = extract_all_fields(doc_path)
        db_data = load_db()
        return render_template("index.html", fields=fields)
    @app.route('/save-and-generate-docx', methods=['POST'])
    def save_and_generate_docx():
        try:
            form_data = request.form.to_dict()
            # Nếu không có dữ liệu form, thử lấy từ JSON nếu request là JSON
            if not form_data and request.is_json:
                try:
                    json_data = request.get_json()
                    if json_data and isinstance(json_data, dict):
                        form_data = {k: v for k, v in json_data.items() if k != 'filename'}
                except Exception as e:
                    print(f"Error parsing JSON: {str(e)}")
            
            # Nếu vẫn không có dữ liệu, thử lấy từ DB
            if not form_data or not any(form_data.values()):
                db_data = load_db()
                if db_data and len(db_data) > 0:
                    form_data = db_data[-1]['data']
                else:
                    return jsonify({"error": "Không có dữ liệu được gửi và không tìm thấy dữ liệu trong DB"}), 400

            # Lấy document path hiện tại
            doc_path = get_doc_path()
            if not doc_path:
                return jsonify({"error": "Không tìm thấy tài liệu"}), 400

            # Lưu dữ liệu form (phần này giữ nguyên như cũ)
            form_id = str(uuid.uuid4())
            text = load_document(doc_path)
            fields = extract_all_fields(doc_path)
            
            transformed_data = {
                "form_id": form_id,
                "document_name": form_data.get('document_name', '')
            }
            
            for field in fields:
                field_code = field['field_code']
                field_name = field['field_name']
                if field_code in form_data:
                    transformed_data[field_name] = form_data[field_code]

            # Lưu vào form history
            try:
                from flask_login import current_user
                form_history = load_form_history()
                
                # Đảm bảo form_history là một list
                if form_history is None or not isinstance(form_history, list):
                    form_history = []
                
                # Thêm tên tài liệu vào form_entry nếu có
                document_name = form_data.get('document_name', '')
                if not document_name:
                    document_name = os.path.basename(doc_path)
                
                form_entry = {
                    "form_id": form_id,
                    "path": doc_path,
                    "name": document_name,  # Thêm tên để hiển thị trong biểu mẫu gần đây
                    "form_data": transformed_data,
                    "timestamp": __import__('datetime').datetime.now().isoformat(),
                    "user_id": current_user.id if current_user.is_authenticated else None,
                    "user_name": current_user.fullname if current_user.is_authenticated else None
                }
                
                form_history.append(form_entry)
                save_form_history(form_history)
                print(f"Form history saved successfully: {form_id}")
            except Exception as e:
                print(f"Error saving form history: {str(e)}")
                import traceback
                traceback.print_exc()

            # Tạo và trả về file docx
            custom_filename = form_data.get('document_name', None)
            from utils.docx_generator import generate_docx
            from flask import make_response
            
            # Gọi hàm tạo tài liệu
            result, status_code = generate_docx(form_data, doc_path, custom_filename)
            if status_code != 200:
                return jsonify(result), status_code
                
            # Xử lý kết quả thành công
            doc_data = result.get("doc_data")
            ascii_filename = result.get("ascii_filename")
            utf8_filename = result.get("utf8_filename")
            temp_doc_path = result.get("temp_doc_path")
            
            # Tạo response
            response = make_response(doc_data)
            response.headers.set('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response.headers.set('Content-Disposition', f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{utf8_filename}')
            response.headers.set('Content-Length', str(len(doc_data)))
            response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
            response.headers.set('Pragma', 'no-cache')
            response.headers.set('Expires', '0')
            
            # Xóa file tạm sau khi gửi
            try:
                if os.path.exists(temp_doc_path):
                    os.remove(temp_doc_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not remove temporary file: {str(cleanup_error)}")
            
            return response

        except Exception as e:
            print(f"Error in save_and_generate_docx: {str(e)}")
            return jsonify({"error": "Có lỗi xảy ra khi xử lý yêu cầu"}), 500
    
    
    @app.route('/form/<form_id>')
    def view_form(form_id):
        try:
            form_history = load_form_history()
            clean_form_id = form_id.replace('_test', '').split('_')[0]
            print("clean_form_id",clean_form_id)
            # Tìm form theo form_id
            form_data = None
            form_path = None
            
            for form in form_history:
                file_name = os.path.basename(form['path'])
                file_id = file_name.split('_')[0]
                print("file_id",file_id)
                if file_id == clean_form_id:
                    form_data = form.get('form_data')
                    form_path = form['path']
                    break

            
            if not form_data or not form_path:
                return jsonify({'error': 'Không tìm thấy biểu mẫu'}), 404
                
            # Set document path và load fields
            set_doc_path(form_path)
            text = load_document(form_path)
            fields = extract_all_fields(form_path)
            
            # Gán giá trị trực tiếp từ form_data vào fields
            for field in fields:
                field_name = field['field_name']
                field['value'] = form_data.get(field_name, '')
            
            # Get suggestions
            db_data = load_db()
            #suggestions = generate_suggestions(db_data) if db_data else {}
            
            return render_template(
                "index.html",
                fields=fields,
               # suggestions=suggestions,
                form_data=form_data,
                document_name=form_data.get('document_name', '')
            )
            
        except Exception as e:
            print(f"Error loading form: {str(e)}")
            return jsonify({'error': f'Không thể tải biểu mẫu: {str(e)}'}), 500
    
    @app.route('/delete-form/<form_id>', methods=['DELETE'])
    def delete_form(form_id):
        try:
            # Load form history
            form_history = load_form_history()
            
            # Find the form with the matching ID
            form_index = None
            for i, form in enumerate(form_history):
                # Lấy ID từ đường dẫn file
                file_name = os.path.basename(form['path'])
                file_id = file_name.split('_')[0] if '_' in file_name else file_name.split('.')[0]
                
                # So sánh với form_id được truyền vào
                if file_id == form_id or file_name.startswith(form_id):
                    form_index = i
                    break
            
            if form_index is None:
                return jsonify({'error': 'Form not found'}), 404
            
            # Xóa form khỏi lịch sử
            deleted_form = form_history.pop(form_index)
            save_form_history(form_history)
            
            # Xóa file nếu cần
            try:
                if os.path.exists(deleted_form['path']) and os.path.isfile(deleted_form['path']):
                    # Chỉ xóa file nếu nó nằm trong thư mục uploads
                    from config.config import UPLOADS_DIR
                    if UPLOADS_DIR in deleted_form['path']:
                        os.remove(deleted_form['path'])
            except Exception as e:
                print(f"Warning: Could not delete file: {str(e)}")
            
            return jsonify({'message': 'Form deleted successfully'})
            
        except Exception as e:
            print(f"Error deleting form: {str(e)}")
            return jsonify({'error': 'Failed to delete form'}), 500