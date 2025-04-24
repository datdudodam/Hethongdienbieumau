from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.user import db, User, Role
from models.data_model import load_db, save_db, load_form_history, save_form_history
from functools import wraps
import os
from werkzeug.utils import secure_filename
from config.config import BASE_DIR

def admin_required(f):
    """Decorator để kiểm tra quyền admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role_id != 1:  # 1 là role_id của admin
            flash('Bạn không có quyền truy cập trang này', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def register_admin_routes(app):
    """Đăng ký các route cho trang admin"""
    
    @app.route('/admin')
    @login_required
    @admin_required
    def admin_dashboard():
        """Trang dashboard của admin"""
        user_count = User.query.count()
        forms_data = load_form_history()
        form_count = len(forms_data)
        return render_template('admin/dashboard.html', user_count=user_count, form_count=form_count)
    @app.route('/web-config', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def web_config():
        from models.web_config import WebConfig
        
        # Handle form submission
        if request.method == 'POST':
            # Process metadata settings
            if 'metadata_form' in request.form:
                WebConfig.set_value('site_title', request.form.get('site_title'), 'metadata')
                WebConfig.set_value('site_description', request.form.get('site_description'), 'metadata')
                # Handle logo upload if provided
                if 'site_logo' in request.files and request.files['site_logo'].filename:
                    logo_file = request.files['site_logo']
                    # Save the file and update the config
                    filename = secure_filename(logo_file.filename)
                    logo_path = os.path.join('static', 'images', filename)
                    logo_file.save(os.path.join(BASE_DIR, logo_path))
                    WebConfig.set_value('site_logo', logo_path, 'metadata')
                flash('Cập nhật metadata thành công', 'success')
            
            # Process SEO settings
            elif 'seo_form' in request.form:
                WebConfig.set_value('meta_title', request.form.get('meta_title'), 'seo')
                WebConfig.set_value('meta_description', request.form.get('meta_description'), 'seo')
                # Handle OG image upload if provided
                if 'og_image' in request.files and request.files['og_image'].filename:
                    og_file = request.files['og_image']
                    filename = secure_filename(og_file.filename)
                    og_path = os.path.join('static', 'images', filename)
                    og_file.save(os.path.join(BASE_DIR, og_path))
                    WebConfig.set_value('og_image', og_path, 'seo')
                WebConfig.set_value('robots_txt', request.form.get('robots_txt'), 'seo')
                flash('Cập nhật SEO thành công', 'success')
            
            # Process UI settings
            elif 'ui_form' in request.form:
                WebConfig.set_value('primary_color', request.form.get('primary_color'), 'ui')
                WebConfig.set_value('font_family', request.form.get('font_family'), 'ui')
                WebConfig.set_value('layout_type', request.form.get('layout_type'), 'ui')
                WebConfig.set_value('display_mode', request.form.get('display_mode'), 'ui')
                flash('Cập nhật giao diện thành công', 'success')
                
            # Process contact information settings
            elif 'contact_form' in request.form:
                WebConfig.set_value('contact_phone', request.form.get('contact_phone'), 'contact')
                WebConfig.set_value('contact_email', request.form.get('contact_email'), 'contact')
                WebConfig.set_value('contact_address', request.form.get('contact_address'), 'contact')
                flash('Cập nhật thông tin liên hệ thành công', 'success')
            
            return redirect(url_for('web_config'))
        
        # Get current config values for display
        config = {
            'metadata': {
                'site_title': WebConfig.get_value('site_title', 'Hệ Thống Nhập Liệu Thông Minh'),
                'site_description': WebConfig.get_value('site_description', 'Hệ thống nhập liệu thông minh hỗ trợ AI, giúp bạn nhập thông tin nhanh chóng và chính xác.'),
                'site_logo': WebConfig.get_value('site_logo', '/static/images/favicon.png')
            },
            'seo': {
                'meta_title': WebConfig.get_value('meta_title', 'Hệ Thống Nhập Liệu Thông Minh'),
                'meta_description': WebConfig.get_value('meta_description', 'Nhập thông tin một cách thông minh với sự hỗ trợ của AI và gợi ý tự động.'),
                'og_image': WebConfig.get_value('og_image', '/static/images/og-image.png'),
                'robots_txt': WebConfig.get_value('robots_txt', 'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /uploads/\nDisallow: /flask_session/\nDisallow: /login/google/callback\n\n# Sitemap\nSitemap: http://localhost:55003/sitemap.xml')
            },
            'ui': {
                'primary_color': WebConfig.get_value('primary_color', '#3b82f6'),
                'font_family': WebConfig.get_value('font_family', 'Inter'),
                'layout_type': WebConfig.get_value('layout_type', 'sidebar'),
                'display_mode': WebConfig.get_value('display_mode', 'light')
            },
            'contact': {
                'contact_phone': WebConfig.get_value('contact_phone', '0123 456 789'),
                'contact_email': WebConfig.get_value('contact_email', 'contact@example.com'),
                'contact_address': WebConfig.get_value('contact_address', '123 Đường ABC, Quận XYZ, TP. HCM')
            }
        }
        
        return render_template('admin/web_config.html', config=config)
    @app.route('/admin/users')
    @login_required
    @admin_required
    def admin_users():
        """Trang quản lý người dùng"""
        users = User.query.all()
        roles = Role.query.all()
        return render_template('admin/users.html', users=users, roles=roles)
    
    @app.route('/admin/users/add', methods=['POST'])
    @login_required
    @admin_required
    def admin_add_user():
        """Thêm người dùng mới"""
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        role_id = request.form.get('role_id', 2)  # Mặc định là user role
        
        if User.query.filter_by(email=email).first():
            flash('Email đã tồn tại', 'error')
            return redirect(url_for('admin_users'))
        
        user = User(fullname=fullname, email=email, role_id=role_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Thêm người dùng thành công', 'success')
        return redirect(url_for('admin_users'))
    
    @app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_edit_user(user_id):
        """Chỉnh sửa thông tin người dùng"""
        user = User.query.get_or_404(user_id)
        
        user.fullname = request.form.get('fullname')
        user.role_id = request.form.get('role_id')
        
        # Nếu có mật khẩu mới thì cập nhật
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            user.set_password(new_password)
        
        db.session.commit()
        flash('Cập nhật thông tin người dùng thành công', 'success')
        return redirect(url_for('admin_users'))
    
    @app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_user(user_id):
        """Xóa người dùng"""
        if current_user.id == user_id:
            flash('Không thể xóa tài khoản của chính mình', 'error')
            return redirect(url_for('admin_users'))
        
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        
        flash('Xóa người dùng thành công', 'success')
        return redirect(url_for('admin_users'))
    
    @app.route('/admin/forms')
    @login_required
    @admin_required
    def admin_forms():
        """Trang quản lý biểu mẫu"""
        forms_data = load_form_history()
        # Thêm thông tin user_name vào mỗi form
        for form in forms_data:
            user = User.query.get(form.get('user_id'))
            form['user_name'] = user.fullname if user else 'Unknown'
        return render_template('admin/forms.html', forms=forms_data)
    
    @app.route('/admin/forms/<form_id>')
    @login_required
    @admin_required
    def admin_view_form(form_id):
        """Xem chi tiết biểu mẫu"""
        forms_data = load_form_history()
        form = next((f for f in forms_data if f.get('form_id') == form_id), None)
        
        if not form:
            flash('Không tìm thấy biểu mẫu', 'error')
            return redirect(url_for('admin_forms'))
        
        # Lấy thông tin người dùng
        user = User.query.get(form.get('user_id'))
        form['user_name'] = user.fullname if user else 'Unknown'
        
        # Chuẩn bị dữ liệu form để hiển thị
        form_fields = []
        if 'form_data' in form:
            for field_name, field_value in form['form_data'].items():
                if field_name not in ['form_id', 'document_name']:  # Bỏ qua các trường hệ thống
                    form_fields.append({
                        'name': field_name,
                        'value': field_value
                    })
        
        return render_template('admin/form_detail.html', 
                            form=form, 
                            form_fields=form_fields,
                            document_name=form.get('form_data', {}).get('document_name', ''))
    
    @app.route('/admin/forms/edit/<form_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_edit_form(form_id):
        """Chỉnh sửa biểu mẫu"""
        forms_data = load_form_history()
        form_index = next((i for i, f in enumerate(forms_data) if f.get('form_id') == form_id), None)
        
        if form_index is None:
            flash('Không tìm thấy biểu mẫu', 'error')
            return redirect(url_for('admin_forms'))
        
        # Cập nhật thông tin biểu mẫu
        new_document_name = request.form.get('document_name')
        if new_document_name:
            forms_data[form_index]['form_data']['document_name'] = new_document_name
        
        # Cập nhật các trường dữ liệu
        field_names = request.form.getlist('field_name[]')
        field_values = request.form.getlist('field_value[]')
        
        for name, value in zip(field_names, field_values):
            if name in forms_data[form_index]['form_data']:
                forms_data[form_index]['form_data'][name] = value
        
        save_form_history(forms_data)
        flash('Cập nhật biểu mẫu thành công', 'success')
        return redirect(url_for('admin_view_form', form_id=form_id))
    
    @app.route('/admin/forms/delete/<form_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_form(form_id):
        """Xóa biểu mẫu"""
        forms_data = load_form_history()
        forms_data = [f for f in forms_data if f.get('form_id') != form_id]
        save_form_history(forms_data)
        
        flash('Xóa biểu mẫu thành công', 'success')
        return redirect(url_for('admin_forms'))
    
    @app.route('/admin/forms/history')
    @login_required
    @admin_required
    def admin_form_history():
        """Xem lịch sử biểu mẫu"""
        history_data = load_form_history()
        # Thêm thông tin user_name vào mỗi bản ghi
        for record in history_data:
            user = User.query.get(record.get('user_id'))
            record['user_name'] = user.fullname if user else 'Unknown'
        return render_template('admin/form_history.html', history=history_data)