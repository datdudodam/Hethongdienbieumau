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

# Cấu hình cơ sở dữ liệu từ biến môi trường
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://postgres:postgres@db:5432/updatelan5')  # Kết nối PostgreSQL
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
app.config['GOOGLE_REDIRECT_URI'] = "http://localhost:55003/login/google/callback"

# Khởi tạo database với Flask app
db.init_app(app)

# Đảm bảo có một app context khi truy vấn DB
with app.app_context():
    # Import WebConfig model trước khi tạo bảng để đảm bảo nó được đăng ký với SQLAlchemy
    from models.web_config import WebConfig
    
    # Tạo tất cả các bảng sau khi đã import tất cả các model
    try:
        # Kiểm tra xem bảng đã tồn tại chưa trước khi tạo
        inspector = db.inspect(db.engine)
        if not inspector.has_table('role'):
            db.create_all()
            # Khởi tạo các vai trò
            from models.user import Role
            Role.insert_roles()
        else:
            print("Bảng đã tồn tại, bỏ qua việc tạo bảng và khởi tạo vai trò")
    except Exception as e:
        print(f"Lỗi khi kiểm tra hoặc tạo bảng: {e}")

# Cấu hình Flask-Login
login_manager = LoginManager() 
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    with app.app_context():
        # Use query.get instead of session.get to ensure the object stays attached to the session
        return db.session.get(User, int(user_id))

# Register context processor to make config values available to all templates
@app.context_processor
def inject_config():
    # Import here to avoid circular imports
    from models.web_config import WebConfig
    import datetime
    
    # Get basic configuration values that are used across the site
    return {
        # Metadata
        'site_title': WebConfig.get_value('site_title', 'Hệ Thống Nhập Liệu Thông Minh'),
        'site_description': WebConfig.get_value('site_description', 'Hệ thống nhập liệu thông minh hỗ trợ AI'),
        'site_logo': WebConfig.get_value('site_logo', '/static/images/favicon.png'),
        
        # SEO
        'meta_title': WebConfig.get_value('meta_title', 'Hệ Thống Nhập Liệu Thông Minh'),
        'meta_description': WebConfig.get_value('meta_description', 'Nhập thông tin một cách thông minh với sự hỗ trợ của AI và gợi ý tự động.'),
        'og_image': WebConfig.get_value('og_image', '/static/images/og-image.png'),
        
       
        
        # Contact Information
        'contact_phone': WebConfig.get_value('contact_phone', '0123 456 789'),
        'contact_email': WebConfig.get_value('contact_email', 'contact@example.com'),
        'contact_address': WebConfig.get_value('contact_address', '123 Đường ABC, Quận XYZ, TP. HCM'),
       
        # Current Year for Copyright
        'current_year': datetime.datetime.now().year,
        
        # CSS Variables for dynamic styling
        
    }
# Đăng ký các route
register_routes(app)

def run_app():
    app.run(host="0.0.0.0", port=55003)

if __name__ == '__main__':
    run_app()
