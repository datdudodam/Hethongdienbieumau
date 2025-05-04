from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models.user import db, User, Role
from models.web_config import WebConfig
from functools import wraps
import json

def admin_required_api(f):
    """Decorator để kiểm tra quyền admin cho API"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role_id != 1:  # 1 là role_id của admin
            return jsonify({'error': 'Không có quyền truy cập'}), 403
        return f(*args, **kwargs)
    return decorated_function

def register_api_routes(app):
    """Đăng ký các route API"""
    
    @app.route('/api/users', methods=['GET'])
    @login_required
    @admin_required_api
    def api_get_users():
        """API lấy danh sách người dùng"""
        users = User.query.all()
        users_data = []
        
        for user in users:
            user_data = {
                'id': user.id,
                'fullname': user.fullname,
                'email': user.email,
                'role_id': user.role_id,
                'role_name': user.role.name if user.role else 'Unknown',
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
                'subscription_type': user.subscription_type,
                'subscription_end': user.subscription_end.strftime('%Y-%m-%d') if user.subscription_end else None,
                'free_downloads_left': user.free_downloads_left,
                'monthly_download_count': user.monthly_download_count
            }
            users_data.append(user_data)
        
        return jsonify(users_data)
    
    @app.route('/api/users/<int:user_id>', methods=['GET'])
    @login_required
    def api_get_user(user_id):
        """API lấy thông tin người dùng"""
        # Kiểm tra quyền truy cập: chỉ admin hoặc chính người dùng đó mới có quyền xem
        if current_user.role_id != 1 and current_user.id != user_id:
            return jsonify({'error': 'Không có quyền truy cập'}), 403
        
        user = User.query.get_or_404(user_id)
        user_data = {
            'id': user.id,
            'fullname': user.fullname,
            'email': user.email,
            'phone': user.phone,
            'address': user.address,
            'bio': user.bio,
            'role_id': user.role_id,
            'role_name': user.role.name if user.role else 'Unknown',
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            'subscription_type': user.subscription_type,
            'subscription_end': user.subscription_end.strftime('%Y-%m-%d') if user.subscription_end else None,
            'free_downloads_left': user.free_downloads_left,
            'monthly_download_count': user.monthly_download_count
        }
        
        return jsonify(user_data)
    
    @app.route('/api/users/<int:user_id>', methods=['PUT'])
    @login_required
    def api_update_user(user_id):
        """API cập nhật thông tin người dùng"""
        # Kiểm tra quyền truy cập: chỉ admin hoặc chính người dùng đó mới có quyền cập nhật
        if current_user.role_id != 1 and current_user.id != user_id:
            return jsonify({'error': 'Không có quyền truy cập'}), 403
        
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        # Cập nhật thông tin cơ bản (người dùng thường có thể cập nhật)
        if 'fullname' in data:
            user.fullname = data['fullname']
        if 'phone' in data:
            user.phone = data['phone']
        if 'address' in data:
            user.address = data['address']
        if 'bio' in data:
            user.bio = data['bio']
        
        # Các thông tin chỉ admin mới có thể cập nhật
        if current_user.role_id == 1:  # Nếu là admin
            if 'role_id' in data:
                user.role_id = data['role_id']
            if 'subscription_type' in data:
                user.subscription_type = data['subscription_type']
            if 'subscription_end' in data:
                from datetime import datetime
                try:
                    user.subscription_end = datetime.strptime(data['subscription_end'], '%Y-%m-%d')
                except ValueError:
                    pass
            if 'free_downloads_left' in data:
                user.free_downloads_left = data['free_downloads_left']
            if 'monthly_download_count' in data:
                user.monthly_download_count = data['monthly_download_count']
        
        db.session.commit()
        return jsonify({'message': 'Cập nhật thông tin thành công', 'user_id': user.id})
    
    @app.route('/api/web-config', methods=['GET'])
    @login_required
    @admin_required_api
    def api_get_web_config():
        """API lấy cấu hình web"""
        configs = WebConfig.get_all()
        config_data = {}
        
        for config in configs:
            if config.category not in config_data:
                config_data[config.category] = {}
            config_data[config.category][config.key] = config.value
        
        return jsonify(config_data)
    
    @app.route('/api/web-config', methods=['PUT'])
    @login_required
    @admin_required_api
    def api_update_web_config():
        """API cập nhật cấu hình web"""
        data = request.get_json()
        
        for category, configs in data.items():
            for key, value in configs.items():
                WebConfig.set_value(key, value, category)
        
        return jsonify({'message': 'Cập nhật cấu hình thành công'})