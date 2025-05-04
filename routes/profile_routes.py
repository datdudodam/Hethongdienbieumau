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
        
        if not fullname:
            flash('Họ và tên không được để trống', 'error')
            return redirect(url_for('profile'))
        
        # Lấy user từ session để đảm bảo phiên bản hợp lệ
        user = db.session.get(User, current_user.id)
        if not user:
            flash('Không tìm thấy người dùng', 'error')
            return redirect(url_for('profile'))
        
        user.fullname = fullname
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
    
    @app.route('/upgrade')
    @login_required
    def upgrade():
        """Nâng cấp lên gói Thường"""
        import datetime
        now = datetime.datetime.now()
        current_user.subscription_type = 'standard'
        current_user.subscription_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Gói Thường có hạn 1 tháng kể từ đầu tháng
        current_user.subscription_end = (current_user.subscription_start + datetime.timedelta(days=31)).replace(day=1) - datetime.timedelta(seconds=1)
        current_user.monthly_download_count = 0
        db.session.commit()
        flash('Nâng cấp gói Thường thành công!', 'success')
        return redirect(url_for('profile'))
    
    @app.route('/upgrade_vip')
    @login_required
    def upgrade_vip():
        """Nâng cấp lên gói VIP"""
        import datetime
        now = datetime.datetime.now()
        current_user.subscription_type = 'vip'
        current_user.subscription_start = now
        # Gói VIP không giới hạn thời gian hoặc có thể set hạn dùng dài hơn
        current_user.subscription_end = None
        current_user.monthly_download_count = 0
        db.session.commit()
        flash('Nâng cấp gói VIP thành công!', 'success')
        return redirect(url_for('profile'))