from routes.home_routes import register_home_routes
from routes.form_routes import register_form_routes
from routes.docx_routes import register_docx_routes
from routes.auth import register_auth_routes
from routes.oauth import register_oauth_routes
from routes.profile_routes import register_profile_routes
from routes.admin_routes import register_admin_routes
from routes.api_routes import register_api_routes
from routes.enhanced_routes import register_enhanced_routes
from routes.api_docs_routes import register_api_docs_routes
from routes.payment_routes import register_payment_routes
from routes.ai_feedback import register_ai_feedback_routes
from routes.goiy_openai import register_goiy_openai_routes

def register_routes(app):
    """
    Đăng ký tất cả các route cho ứng dụng
    """
    register_home_routes(app)
    register_form_routes(app)
    register_docx_routes(app)
    register_auth_routes(app)
    register_oauth_routes(app)
    register_profile_routes(app)
    register_admin_routes(app)
    register_api_routes(app)
    register_enhanced_routes(app)
    register_api_docs_routes(app)
    register_payment_routes(app)
    register_ai_feedback_routes(app)
    register_goiy_openai_routes(app)  # Đăng ký route mới
   