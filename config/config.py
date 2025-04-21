import os
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Đường dẫn gốc của ứng dụng
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cấu hình đường dẫn
DB_PATH = os.path.join(BASE_DIR, "form_data.json")
FORM_HISTORY_PATH = os.path.join(BASE_DIR, "form_history.json")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATE_FORMS_PATH = os.path.join(BASE_DIR, "data", "template_forms.json")

# Đảm bảo thư mục uploads tồn tại
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

# Cấu hình OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Cấu hình Google OAuth
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/login/google/callback')

# Cấu hình ứng dụng
DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'