from flask import request, jsonify, make_response
from utils.docx_generator import generate_docx
from utils.document_utils import get_doc_path
from models.data_model import load_db
import os
import datetime
from flask_login import current_user, login_required
from models.user import db, User

def register_docx_routes(app):
    """
    Đăng ký các route cho việc tạo và xuất tài liệu docx
    """
    @app.route('/generate-docx', methods=['POST'])
    @login_required
    def generate_docx_route():
        try:
            # Kiểm tra trạng thái đăng nhập
            if not current_user.is_authenticated:
                return jsonify({'error': 'Bạn cần đăng nhập để tải tài liệu.'}), 401

            # Kiểm tra trạng thái gói và số lượt tải
            user = User.query.get(current_user.id)
            now = datetime.datetime.now(datetime.timezone.utc)
            # Reset monthly download count nếu đã sang tháng mới
            if user.subscription_type == 'standard' and user.subscription_start and user.subscription_end:
                if user.subscription_end < now:
                    user.subscription_type = 'free'
                    user.subscription_start = None
                    user.subscription_end = None
                    user.monthly_download_count = 0
                    db.session.commit()
            if user.subscription_type == 'standard':
                # Nếu đã sang tháng mới, reset monthly_download_count
                if user.subscription_start and user.subscription_end:
                    if user.subscription_start.month != now.month or user.subscription_start.year != now.year:
                        user.monthly_download_count = 0
                        user.subscription_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        user.subscription_end = (user.subscription_start + datetime.timedelta(days=31)).replace(day=1) - datetime.timedelta(seconds=1)
                        db.session.commit()
            # Kiểm tra quyền tải
            allow_download = False
            if user.subscription_type == 'vip':
                allow_download = True
            elif user.subscription_type == 'standard':
                if user.monthly_download_count < 100:
                    allow_download = True
                else:
                    return jsonify({'error': 'Bạn đã hết lượt tải trong tháng. Vui lòng nâng cấp gói hoặc chờ sang tháng mới.'}), 403
            elif user.subscription_type == 'free':
                if user.free_downloads_left > 0:
                    allow_download = True
                else:
                    return jsonify({'error': 'Bạn đã hết lượt tải miễn phí. Vui lòng đăng ký gói để tiếp tục tải.'}), 403
            if not allow_download:
                return jsonify({'error': 'Không đủ quyền tải tài liệu.'}), 403
            # Kiểm tra và xử lý dữ liệu từ request
            request_data = None
            form_data = None
            
            if request.is_json:
                try:
                    request_data = request.get_json()
                    if request_data and isinstance(request_data, dict):
                        form_data = {k: v for k, v in request_data.items() if k != 'filename'}
                except Exception as e:
                    print(f"Error parsing JSON: {str(e)}")
                    return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400
            else:
                try:
                    form_data = request.form.to_dict()
                except Exception as e:
                    print(f"Error parsing form data: {str(e)}")
                    return jsonify({'error': 'Không thể đọc dữ liệu form'}), 400

            # Nếu không có dữ liệu form, sử dụng dữ liệu mới nhất từ DB
            if not form_data or not any(form_data.values()):
                db_data = load_db()
                if not db_data:
                    return jsonify({'error': 'Không có dữ liệu để tạo tài liệu'}), 400
                form_data = db_data[-1]['data']

            custom_filename = request_data.get('filename') if request_data else None
            doc_path = get_doc_path()
            
            # Gọi hàm tạo tài liệu
            result, status_code = generate_docx(form_data, doc_path, custom_filename)
            if status_code != 200:
                return jsonify(result), status_code
            # Cập nhật số lượt tải
            if user.subscription_type == 'vip':
                pass
            elif user.subscription_type == 'standard':
                user.monthly_download_count += 1
                db.session.commit()
            elif user.subscription_type == 'free':
                user.free_downloads_left -= 1
                db.session.commit()
            
            # Xử lý kết quả thành công
            doc_data = result.get("doc_data")
            ascii_filename = result.get("ascii_filename")
            utf8_filename = result.get("utf8_filename")
            temp_doc_path = result.get("temp_doc_path")
            
            # Chuẩn bị thông tin trạng thái gói cho user
            user_status = {
                "subscription_type": user.subscription_type,
                "free_downloads_left": user.free_downloads_left if hasattr(user, 'free_downloads_left') else None,
                "monthly_download_count": user.monthly_download_count if hasattr(user, 'monthly_download_count') else None,
                "subscription_start": user.subscription_start.isoformat() if user.subscription_start else None,
                "subscription_end": user.subscription_end.isoformat() if user.subscription_end else None
            }
            
            # Tạo response
            response = make_response(doc_data)
            response.headers.set('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response.headers.set('Content-Disposition', f'attachment; filename="{ascii_filename}"; filename*=UTF-8''{utf8_filename}')
            response.headers.set('Content-Length', str(len(doc_data)))
            response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
            response.headers.set('Pragma', 'no-cache')
            response.headers.set('Expires', '0')
            response.headers.set('Access-Control-Expose-Headers', 'Content-Disposition')
            response.headers.set('X-Content-Type-Options', 'nosniff')
            # Thêm trạng thái gói vào header để client dễ lấy
            response.headers.set('X-User-Status', str(user_status))
            
            # Xóa file tạm sau khi gửi
            try:
                if os.path.exists(temp_doc_path):
                    os.remove(temp_doc_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not remove temporary file: {str(cleanup_error)}")
            
            return response

        except Exception as e:
            print(f"Error generating document: {str(e)}")
            return jsonify({'error': 'Có lỗi xảy ra khi tạo tài liệu. Vui lòng thử lại sau.'}), 500