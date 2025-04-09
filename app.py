from flask import Flask, redirect, url_for
from config.config import DEBUG, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI  # Import cấu hình OAuth
from routes.home_routes import register_home_routes
from routes.form_routes import register_form_routes
from routes.docx_routes import register_docx_routes
from routes import register_routes
from flask_login import LoginManager
from models.user import User, db
from flask_session import Session
import os
# Khởi tạo ứng dụng Flask
app = Flask(__name__)

# Cấu hình cơ sở dữ liệu (Thay thế bằng URI thật của bạn)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'  # Hoặc PostgreSQL/MySQL URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Use a fixed secret key for development to ensure session persistence
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-for-session-persistence') # Thêm secret key cho session

# Cấu hình session cho OAuth
app.config['SESSION_COOKIE_NAME'] = 'My Flask App'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # Session lifetime in seconds
app.config['SESSION_COOKIE_HTTPONLY'] = True
# Disable secure cookie for local development
app.config['SESSION_COOKIE_SECURE'] = False
# Enable session persistence
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_session')
# Đảm bảo session được lưu trữ đúng cách
app.config['SESSION_PERMANENT'] = True

# Create session directory if it doesn't exist
if not os.path.exists(app.config['SESSION_FILE_DIR']):
    os.makedirs(app.config['SESSION_FILE_DIR'])

# Initialize Flask-Session
Session(app)

# Cấu hình Google OAuth
app.config['GOOGLE_CLIENT_ID'] = "30787395526-jqgac7lj9usbv356ho35cahvcokq7868.apps.googleusercontent.com"
app.config['GOOGLE_CLIENT_SECRET'] ="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"
app.config['GOOGLE_REDIRECT_URI'] = "http://localhost:5000/auth/google/callback"

# Khởi tạo database với Flask app
db.init_app(app)

# Đảm bảo có một app context khi truy vấn DB
with app.app_context():
    db.create_all()
    # Khởi tạo các vai trò
    from models.user import Role
    Role.insert_roles()

# Cấu hình Flask-Login
login_manager = LoginManager() 
login_manager.init_app(app)
login_manager.login_view = 'login'  # Đặt view đăng nhập mặc định

@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        # Use query.get instead of session.get to ensure the object stays attached to the session
        return db.session.get(User, int(user_id))
# Đăng ký các route
register_routes(app)

def run_app():
    app.run(host='0.0.0.0', debug=DEBUG)

if __name__ == '__main__':
    run_app()
