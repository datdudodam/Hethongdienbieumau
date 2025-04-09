from .home_routes import register_home_routes
from .form_routes import register_form_routes
from .docx_routes import register_docx_routes
from .auth import register_auth_routes
from .ml_routes import register_ml_routes
from .enhanced_routes import register_enhanced_routes
from .admin_routes import register_admin_routes
from .oauth import register_oauth_routes
from .profile_routes import register_profile_routes
from .goiy_openai import GOI_Y_AI
def register_routes(app):
    register_home_routes(app)
    register_form_routes(app)
    register_docx_routes(app)
    register_auth_routes(app)
    register_ml_routes(app)
    register_enhanced_routes(app)
    GOI_Y_AI(app)
    register_admin_routes(app)
    register_oauth_routes(app)
    register_profile_routes(app)