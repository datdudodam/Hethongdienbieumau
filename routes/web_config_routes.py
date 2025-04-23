from flask import render_template

def register_web_config_routes(app):
    """
    Đăng ký các route cho trang cấu hình web
    """
    @app.route('/web-config')
    def web_config():
        return render_template('web_config.html')