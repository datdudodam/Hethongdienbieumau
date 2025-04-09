from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.user import db, User
from utils.validators import validate_password
from werkzeug.security import check_password_hash

def register_profile_routes(app):
    """ Đăng ký các route liên quan đến hồ sơ người dùng """
    
    @app.route('/profile')
    @login_required
    def profile():
        """ Hiển thị trang hồ sơ người dùng """
        return render_template('profile.html')
    
    @app.route('/profile/update', methods=['POST'])
    @login_required
    def update_profile():
        """ Cập nhật thông tin hồ sơ người dùng """
        fullname = request.form.get('fullname')
        phone = request.form.get('phone')
        address = request.form.get('address')
        bio = request.form.get('bio')
        
        if not fullname:
            flash('Họ và tên không được để trống', 'error')
            return redirect(url_for('profile'))
        
        # Cập nhật thông tin người dùng
        current_user.fullname = fullname
        current_user.phone = phone
        current_user.address = address
        current_user.bio = bio
        
        db.session.commit()
        flash('Cập nhật thông tin thành công!', 'success')
        return redirect(url_for('profile'))
    
    @app.route('/profile/change-password', methods=['POST'])
    @login_required
    def change_password():
        """ Đổi mật khẩu người dùng """
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Kiểm tra mật khẩu hiện tại
        if not current_user.check_password(current_password):
            flash('Mật khẩu hiện tại không chính xác', 'error')
            return redirect(url_for('profile'))
        
        # Kiểm tra mật khẩu mới
        if new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp', 'error')
            return redirect(url_for('profile'))
        
        # Kiểm tra độ mạnh của mật khẩu
        is_valid_password, msg = validate_password(new_password)
        if not is_valid_password:
            flash(msg, 'error')
            return redirect(url_for('profile'))
        
        # Cập nhật mật khẩu
        current_user.set_password(new_password)
        db.session.commit()
        flash('Đổi mật khẩu thành công!', 'success')
        return redirect(url_for('profile'))
    
    @app.route('/profile/set-password', methods=['POST'])
    @login_required
    def set_password():
        """ Thiết lập mật khẩu cho tài khoản đăng nhập bằng Google """
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Kiểm tra mật khẩu mới
        if new_password != confirm_password:
            flash('Mật khẩu xác nhận không khớp', 'error')
            return redirect(url_for('profile'))
        
        # Kiểm tra độ mạnh của mật khẩu
        is_valid_password, msg = validate_password(new_password)
        if not is_valid_password:
            flash(msg, 'error')
            return redirect(url_for('profile'))
        
        # Thiết lập mật khẩu
        current_user.set_password(new_password)
        db.session.commit()
        flash('Thiết lập mật khẩu thành công!', 'success')
        return redirect(url_for('profile'))