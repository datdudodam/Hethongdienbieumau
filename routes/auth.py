from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from models.user import db, User
from utils.validators import validate_email, validate_password

def register_auth_routes(app):
    """ Đăng ký các route xác thực """
    dangNhap_Dangky(app)

def dangNhap_Dangky(app):
    """ Đăng ký và Đăng nhập
    """
    @app.route('/GoiThuong.html')
    def serve_goi_thuong():
         return render_template('GoiThuong.html')
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # Lấy tham số redirect từ URL nếu có
        redirect_url = request.args.get('redirect')
        
        if current_user.is_authenticated:
            # Nếu người dùng đã đăng nhập và là admin, chuyển hướng đến trang admin
            if current_user.role_id == 1:  # 1 là role_id của admin
                return redirect(url_for('admin_dashboard'))
            # Nếu có tham số redirect, chuyển hướng đến URL đó
            if redirect_url:
                return redirect(redirect_url)
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            remember = request.form.get('remember') == 'on'
            # Lấy tham số redirect từ form nếu có
            form_redirect = request.form.get('redirect')

            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                login_user(user, remember=remember)
                flash('Đăng nhập thành công!', 'success')
                # Kiểm tra vai trò người dùng và chuyển hướng phù hợp
                if user.role_id == 1:  # 1 là role_id của admin
                    return redirect(url_for('admin_dashboard'))
                # Nếu có tham số redirect từ form, ưu tiên sử dụng nó
                if form_redirect:
                    return redirect(form_redirect)
                # Nếu có tham số redirect từ URL, sử dụng nó
                if redirect_url:
                    return redirect(redirect_url)
                return redirect(url_for('index'))
            else:
                flash('Email hoặc mật khẩu không chính xác', 'error')

        return render_template('DangNhap.html', redirect_url=redirect_url)

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            fullname = request.form.get('fullname')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not all([fullname, email, password, confirm_password]):
                flash('Vui lòng điền đầy đủ thông tin', 'error')
                return redirect(url_for('signup'))

            if not validate_email(email):
                flash('Email không hợp lệ', 'error')
                return redirect(url_for('signup'))

            if User.query.filter_by(email=email).first():
                flash('Email đã được đăng ký', 'error')
                return redirect(url_for('signup'))

            if password != confirm_password:
                flash('Mật khẩu xác nhận không khớp', 'error')
                return redirect(url_for('signup'))

            is_valid_password, msg = validate_password(password)
            if not is_valid_password:
                flash(msg, 'error')
                return redirect(url_for('signup'))

            user = User(fullname=fullname, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return render_template('DangNhap.html')

        return render_template('DangKy.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Đã đăng xuất thành công.', 'success')
        return redirect(url_for('login'))
