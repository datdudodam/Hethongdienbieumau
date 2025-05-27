from models.user import db
from datetime import datetime

class WebConfig(db.Model):
    """Model for storing website configuration settings"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False, default='general')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    @classmethod
    def get_value(cls, key, default=None):
        """Get a configuration value by key"""
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default
    
    @classmethod
    def set_value(cls, key, value, category='general'):
        """Set a configuration value"""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            config.updated_at = datetime.utcnow()
        else:
            config = cls(key=key, value=value, category=category)
            db.session.add(config)
        db.session.commit()
        return config
    
    @classmethod
    def get_all_by_category(cls, category):
        """Get all configuration values by category"""
        return cls.query.filter_by(category=category).all()
    
    @classmethod
    def get_all(cls):
        """Get all configuration values"""
        return cls.query.all() 
    
# Thêm trường expiration_date vào model APIKey
class APIKey(db.Model):
    """Model for storing API keys with their status"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False, default='OpenAI API Key')
    provider = db.Column(db.String(50), nullable=False, default='openai')
    is_active = db.Column(db.Boolean, default=True)
    is_valid = db.Column(db.Boolean, default=True)
    status_message = db.Column(db.Text, nullable=True)
    last_checked = db.Column(db.DateTime, nullable=True)
    response_time = db.Column(db.Integer, nullable=True)  # Thời gian phản hồi (ms)
    available_models = db.Column(db.Text, nullable=True)  # Danh sách models dạng JSON
    error_details = db.Column(db.Text, nullable=True)  # Chi tiết lỗi nếu có
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_requests = db.Column(db.Integer, default=0)
    successful_requests = db.Column(db.Integer, default=0)
    usage_limit = db.Column(db.Integer, nullable=True)
    usage_reset_at = db.Column(db.DateTime, nullable=True)
    description = db.Column(db.Text, nullable=True)  # Thêm trường description
    expiration_date = db.Column(db.DateTime, nullable=True)
    plan_info = db.Column(db.Text, nullable=True)
    

   
    @classmethod
    def add_key(cls, key, name=None, description=None, provider='openai'):
        """Thêm API key mới vào hệ thống"""
        if not name:
            name = f'{provider.capitalize()} API Key'
        
        api_key = cls(
            key=key, 
            name=name, 
            provider=provider,
            description=description
        )
        db.session.add(api_key)
        db.session.commit()
        return api_key
    @classmethod
    def get_key_details(cls, key_id):
        """Lấy thông tin chi tiết về API key"""
        api_key = cls.query.get(key_id)
        if not api_key:
            return None
            
        return {
            'total_requests': 0,  # Bạn cần thêm trường này vào model nếu muốn theo dõi
            'successful_requests': 0,  # Bạn cần thêm trường này vào model nếu muốn theo dõi
            'available_models': api_key.available_models,
            'last_checked': api_key.last_checked,
            'response_time': api_key.response_time,
            'error_details': api_key.error_details
        }
    @classmethod
    def get_active_key(cls, provider='openai'):
        """
        Lấy API key đang hoạt động cho provider cụ thể.
        Hỗ trợ: 'openai', 'gemini'
        Ưu tiên key được tạo gần nhất và đang active.
        """
        try:
            if provider not in ['openai', 'gemini']:
                from flask import current_app
                current_app.logger.warning(f"Unsupported provider '{provider}'")
                return None

            return cls.query.filter_by(
                provider=provider,
                is_active=True
            ).order_by(cls.created_at.desc()).first()

        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error getting active API key for provider '{provider}': {str(e)}")
            return None

        
    @classmethod
    def get_all_keys(cls, provider=None):
        """Lấy tất cả API key, có thể lọc theo provider"""
        if provider:
            return cls.query.filter_by(provider=provider).order_by(cls.is_active.desc(), cls.updated_at.desc()).all()
        return cls.query.order_by(cls.provider, cls.is_active.desc(), cls.updated_at.desc()).all()
    
    @classmethod
    def update_key_status(cls, key_id, is_valid, status_message, response_time=None, available_models=None, error_details=None, expiration_date=None, plan_info=None):
        """Cập nhật trạng thái của API key"""
        try:
            api_key = cls.query.get(key_id)
            if not api_key:
                return None
                
            api_key.is_valid = is_valid
            api_key.status_message = status_message
            api_key.last_checked = datetime.now()
            
            if response_time is not None:
                api_key.response_time = response_time
                
            if available_models is not None:
                api_key.available_models = available_models
                
            if error_details is not None:
                api_key.error_details = error_details
                
            if expiration_date is not None:
                api_key.expiration_date = expiration_date
                
            if plan_info is not None:
                api_key.plan_info = plan_info
                
            db.session.commit()
            return api_key
        except Exception as e:
            db.session.rollback()
            return None
    
    @classmethod
    def set_active_key(cls, key_id, provider='openai'):
        """Đặt một API key làm key hoạt động chính và vô hiệu hóa các key khác"""
        # Vô hiệu hóa tất cả các key hiện tại của provider
        cls.query.filter_by(provider=provider).update({cls.is_active: False})
        
        # Đặt key được chọn làm key hoạt động
        api_key = cls.query.get(key_id)
        if api_key and api_key.provider == provider:
            api_key.is_active = True
            db.session.commit()
            return api_key
        return None
    
    @classmethod
    def delete_key(cls, key_id):
        """Xóa một API key"""
        api_key = cls.query.get(key_id)
        if api_key:
            db.session.delete(api_key)
            db.session.commit()
            return True
        return False
    
   