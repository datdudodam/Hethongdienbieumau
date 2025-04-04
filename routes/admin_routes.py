from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models.user import db, User, Role
from models.data_model import load_db, save_db, load_form_history, save_form_history
from functools import wraps

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