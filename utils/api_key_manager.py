from openai import OpenAI
from models.web_config import WebConfig, APIKey
from models.user import db
from datetime import datetime
import time
import logging
import json
from flask import current_app
import google.generativeai as genai

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Quản lý API key OpenAI và Gemini từ cơ sở dữ liệu"""
    
    _instance = None
    _openai_client = None
    _gemini_client = None
    _current_openai_key = None
    _current_gemini_key = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def _initialize(self):
        """Khởi tạo các giá trị mặc định"""
        if not self._initialized:
            self._current_openai_key = None
            self._current_gemini_key = None
            self._openai_client = None
            self._gemini_client = None
            self._initialized = True
            
    # Add this at the top of your class
    @property
    def openai_client(self):
        """Property to access OpenAI client with lazy initialization"""
        if self._openai_client is None:
            self._get_openai_client()
        return self._openai_client

    @property
    def gemini_client(self):
        """Property to access Gemini client with lazy initialization"""
        if self._gemini_client is None:
            self._get_gemini_client()
        return self._gemini_client

    def get_client(self, provider='openai'):
        """Lấy client AI hiện tại theo provider
        
        Args:
            provider (str): 'openai' hoặc 'gemini'
            
        Returns:
            Client tương ứng hoặc None nếu có lỗi
        """
        try:
            if provider == 'openai':
                return self.openai_client
            elif provider == 'gemini':
                return self.gemini_client
            else:
                logger.error(f"Unsupported provider: {provider}")
                return None
        except Exception as e:
            logger.error(f"Error getting {provider} client: {str(e)}")
            return None
   
    
    def _get_openai_client(self):
        """Lấy client OpenAI hiện tại, khởi tạo nếu cần"""
        try:
            self._initialize()
            
            active_key = self._get_active_api_key('openai')
            
            if not active_key:
                db_api_key = self._get_api_key_from_config('openai')
                if db_api_key and db_api_key.strip() != "":
                    self.add_api_key(db_api_key, "Legacy API Key", 'openai')
                    active_key = self._get_active_api_key('openai')
            
            if active_key:
                if active_key.key != self._current_openai_key:
                    self._current_openai_key = active_key.key
                    if self._current_openai_key and self._current_openai_key.strip() != "":
                        self._openai_client = OpenAI(api_key=self._current_openai_key)
                    else:
                        self._openai_client = None
                        logger.warning("Empty OpenAI API key provided")
            
            return self._openai_client
        except Exception as e:
            logger.error(f"Error getting OpenAI client: {str(e)}")
            return None
    def _initialize_openai_client(self):
        """Khởi tạo OpenAI client"""
        try:
            self._initialize()
            active_key = self._get_active_api_key('openai')
            
            if not active_key:
                db_api_key = self._get_api_key_from_config('openai')
                if db_api_key and db_api_key.strip() != "":
                    self.add_api_key(db_api_key, "Legacy API Key", 'openai')
                    active_key = self._get_active_api_key('openai')
            
            if active_key:
                if active_key.key != self._current_openai_key:
                    self._current_openai_key = active_key.key
                    if self._current_openai_key and self._current_openai_key.strip() != "":
                        self._openai_client = OpenAI(api_key=self._current_openai_key)
                        logger.info("OpenAI client initialized successfully")
                    else:
                        self._openai_client = None
                        logger.warning("Empty OpenAI API key provided")
            
            return self._openai_client
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            return None
    def _get_gemini_client(self):
        """Lấy client Gemini hiện tại, khởi tạo nếu cần"""
        try:
            self._initialize()
            
            active_key = self._get_active_api_key('gemini')
            
            if not active_key:
                db_api_key = self._get_api_key_from_config('gemini')
                if db_api_key and db_api_key.strip() != "":
                    self.add_api_key(db_api_key, "Legacy Gemini Key", 'gemini')
                    active_key = self._get_active_api_key('gemini')
            
            if active_key:
                if active_key.key != self._current_gemini_key:
                    self._current_gemini_key = active_key.key
                    if self._current_gemini_key and self._current_gemini_key.strip() != "":
                        genai.configure(api_key=self._current_gemini_key)
                        self._gemini_client = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
                    else:
                        self._gemini_client = None
                        logger.warning("Empty Gemini API key provided")
            
            return self._gemini_client
        except Exception as e:
            logger.error(f"Error getting Gemini client: {str(e)}")
            return None

    def _get_active_api_key(self, provider='openai'):
        """Lấy API key đang hoạt động từ bảng APIKey"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                return APIKey.get_active_key(provider)
            return None
        except Exception as e:
            logger.error(f"Error getting active API key for {provider}: {str(e)}")
            return None
    
    def _get_api_key_from_config(self, provider='openai'):
        """Lấy API key từ WebConfig với xử lý application context"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                config_key = f"{provider}_api_key"
                return WebConfig.get_value(config_key, '')
            return None
        except RuntimeError as e:
            if "working outside of application context" in str(e).lower():
                logger.warning("Working outside of application context")
                return None
            raise
    
    def check_api_key_validity(self, api_key=None, provider='openai'):
        """Kiểm tra tính hợp lệ của API key
        
        Args:
            api_key: API key cần kiểm tra, nếu None thì kiểm tra key hiện tại
            provider: 'openai' hoặc 'gemini'
            
        Returns:
            dict: Thông tin về trạng thái của API key
        """
        if provider == 'openai':
            return self._check_openai_key(api_key)
        elif provider == 'gemini':
            return self._check_gemini_key(api_key)
        else:
            return {
                "valid": False,
                "message": f"Unsupported provider: {provider}",
                "details": {
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
    
    def _check_openai_key(self, api_key=None):
        """Kiểm tra tính hợp lệ của OpenAI API key"""
        if api_key is None:
            client = self._get_openai_client()
        else:
            client = OpenAI(api_key=api_key)
        
        if not client:
            return {
                "valid": False,
                "message": "Không thể khởi tạo client OpenAI",
                "details": {
                    "reason": "Client is None",
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        
        try:
            start_time = time.time()
            response = client.models.list()
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000)
            
            all_models = [model.id for model in response.data]
            gpt_models = [m for m in all_models if 'gpt' in m]
            embedding_models = [m for m in all_models if 'embedding' in m or 'embed-' in m]
            other_models = [m for m in all_models if m not in gpt_models and m not in embedding_models]
            
            return {
                "valid": True,
                "message": "API key hợp lệ và đang hoạt động",
                "details": {
                    "response_time_ms": response_time,
                    "total_models": len(all_models),
                    "gpt_models": gpt_models,
                    "embedding_models": embedding_models,
                    "other_models": other_models,
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
        except Exception as e:
            error_message = str(e)
            logger.error(f"OpenAI API key validation error: {error_message}")
            return self._parse_openai_error(error_message)
    
    def _check_gemini_key(self, api_key=None):
        """Kiểm tra tính hợp lệ của Gemini API key"""
        try:
            if api_key is None:
                client = self._get_gemini_client()
            else:
                genai.configure(api_key=api_key)
                client = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            
            if not client:
                return {
                    "valid": False,
                    "message": "Không thể khởi tạo client Gemini",
                    "details": {
                        "reason": "Client is None",
                        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
            
            start_time = time.time()
            response = client.generate_content("Test connection")
            end_time = time.time()
            response_time = round((end_time - start_time) * 1000)
            
            if response and response.text:
                return {
                    "valid": True,
                    "message": "API key hợp lệ và đang hoạt động",
                    "details": {
                        "response_time_ms": response_time,
                        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                }
            else:
                return {
                    "valid": False,
                    "message": "Không nhận được phản hồi từ Gemini",
                    "details": {
                        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
        except Exception as e:
            error_message = str(e)
            logger.error(f"Gemini API key validation error: {error_message}")
            return self._parse_gemini_error(error_message)
    
    def _parse_openai_error(self, error_message):
        """Phân tích lỗi OpenAI để đưa ra thông báo phù hợp"""
        if "Incorrect API key" in error_message or "Invalid API key" in error_message:
            message = "API key không hợp lệ"
        elif "exceeded your current quota" in error_message:
            message = "API key đã vượt quá hạn mức sử dụng"
        elif "deactivated" in error_message:
            message = "API key đã bị vô hiệu hóa"
        elif "expired" in error_message:
            message = "API key đã hết hạn"
        else:
            message = f"Lỗi khi kiểm tra API key: {error_message}"
        
        return {
            "valid": False,
            "message": message,
            "details": {
                "error": error_message,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        }
    
    def _parse_gemini_error(self, error_message):
        """Phân tích lỗi Gemini để đưa ra thông báo phù hợp"""
        if "API_KEY_INVALID" in error_message:
            message = "API key không hợp lệ"
        elif "quota" in error_message.lower():
            message = "API key đã vượt quá hạn mức sử dụng"
        else:
            message = f"Lỗi khi kiểm tra API key: {error_message}"
        
        return {
            "valid": False,
            "message": message,
            "details": {
                "error": error_message,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        }

    def add_api_key(self, new_api_key, name=None, description=None, provider='openai'):
        """Thêm API key mới vào hệ thống và kiểm tra tính hợp lệ"""
        try:
            if not new_api_key or new_api_key.strip() == "":
                logger.warning("Empty API key provided")
                return None
                
            if not (current_app and hasattr(current_app, 'app_context')):
                logger.warning("Cannot add API key - no application context")
                return None
                
            validity_result = self.check_api_key_validity(new_api_key, provider)
            
            api_key = APIKey.add_key(new_api_key, name, provider, description)
            
            is_valid = validity_result['valid']
            status_message = validity_result['message']
            
            response_time = None
            available_models = None
            error_details = None
            
            if is_valid:
                response_time = validity_result['details'].get('response_time_ms')
                if provider == 'openai':
                    available_models = json.dumps(validity_result['details'].get('available_models', []))
            else:
                error_details = validity_result['details'].get('error')
            
            APIKey.update_key_status(
                api_key.id, 
                is_valid, 
                status_message, 
                response_time, 
                available_models, 
                error_details
            )
            
            active_key = APIKey.get_active_key(provider)
            if not active_key:
                APIKey.set_active_key(api_key.id, provider)
                
                if is_valid:
                    if provider == 'openai':
                        self._current_openai_key = new_api_key
                        self._openai_client = OpenAI(api_key=new_api_key)
                    elif provider == 'gemini':
                        self._current_gemini_key = new_api_key
                        genai.configure(api_key=new_api_key)
                        self._gemini_client = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            
            if is_valid and not active_key and provider == 'openai':
                WebConfig.set_value('openai_api_key', new_api_key, 'api')
            
            return api_key
        except Exception as e:
            logger.error(f"Error adding API key for {provider}: {str(e)}")
            return None

    def get_key_details(self, key_id):
        """Lấy thông tin chi tiết về API key"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return None
                    
                if not api_key.last_checked or (datetime.now() - api_key.last_checked).total_seconds() > 3600:
                    api_key = self.refresh_api_key_status(key_id)
                    
                return {
                    'total_requests': api_key.total_requests if hasattr(api_key, 'total_requests') else 0,
                    'successful_requests': api_key.successful_requests if hasattr(api_key, 'successful_requests') else 0,
                    'available_models': json.loads(api_key.available_models) if api_key.available_models else [],
                    'last_checked': api_key.last_checked,
                    'response_time': api_key.response_time,
                    'error_details': api_key.error_details,
                    'name': api_key.name,
                    'is_active': api_key.is_active,
                    'is_valid': api_key.is_valid,
                    'status_message': api_key.status_message,
                    'created_at': api_key.created_at,
                    'updated_at': api_key.updated_at
                }
            return None
        except Exception as e:
            logger.error(f"Error getting key details: {str(e)}")
            return None

    def test_api_key(self, key_id):
        """Kiểm tra tính hợp lệ của API key và cập nhật trạng thái"""
        try:
            api_key = APIKey.query.get(key_id)
            if not api_key:
                return False, "API key không tồn tại"
            
            validity_result = self.check_api_key_validity(api_key.key, api_key.provider)
            
            is_valid = validity_result['valid']
            status_message = validity_result['message']
            response_time = validity_result['details'].get('response_time_ms')
            available_models = json.dumps(validity_result['details'].get('available_models', [])) if is_valid else None
            error_details = validity_result['details'].get('error') if not is_valid else None
            
            updated_key = APIKey.update_key_status(
                key_id,
                is_valid=is_valid,
                status_message=status_message,
                response_time=response_time,
                available_models=available_models,
                error_details=error_details
            )
            
            if not updated_key:
                return False, "Không thể cập nhật trạng thái API key"
            
            if is_valid:
                return True, {
                    "status": "valid",
                    "message": status_message,
                    "available_models": json.loads(available_models) if available_models else [],
                    "response_time": response_time
                }
            else:
                return False, status_message
                
        except Exception as e:
            logger.error(f"Error testing API key {key_id}: {str(e)}")
            return False, f"Lỗi hệ thống khi kiểm tra API key: {str(e)}"

    def update_api_key(self, new_api_key, provider='openai'):
        """Cập nhật API key mới vào cơ sở dữ liệu"""
        try:
            if new_api_key and new_api_key.strip() != "":
                if not (current_app and hasattr(current_app, 'app_context')):
                    logger.warning("Cannot update API key - no application context")
                    return None

                existing_key = APIKey.query.filter_by(key=new_api_key, provider=provider).first()
                if existing_key:
                    logger.info("API key already exists, setting as active")
                    APIKey.set_active_key(existing_key.id, provider)
                    if provider == 'openai':
                        self._current_openai_key = new_api_key
                        self._openai_client = OpenAI(api_key=new_api_key)
                    elif provider == 'gemini':
                        self._current_gemini_key = new_api_key
                        genai.configure(api_key=new_api_key)
                        self._gemini_client = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
                else:
                    self.add_api_key(new_api_key, f"Updated {provider} Key", provider=provider)

                if provider == 'openai':
                    WebConfig.set_value('openai_api_key', new_api_key, 'api')
                return True
            else:
                logger.warning("Empty API key provided for update")
                return False
        except Exception as e:
            logger.error(f"Error updating API key: {str(e)}")
            return False

    def get_all_api_keys(self, provider='openai'):
        """Lấy tất cả API key của một provider"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                return APIKey.get_all_keys(provider)
            return []
        except Exception as e:
            logger.error(f"Error getting API keys: {str(e)}")
            return []

    def set_active_api_key(self, key_id, provider='openai'):
        """Đặt một API key làm key hoạt động chính"""
        try:
            # Đảm bảo chúng ta có app context
            if not current_app:
                logger.error("Không có Flask app context")
                return False

            # Lấy key từ database
            api_key = APIKey.query.get(key_id)
            if not api_key:
                logger.error(f"Không tìm thấy API key với ID {key_id}")
                return False

            # Kiểm tra provider có khớp không
            if api_key.provider != provider:
                logger.error(f"Provider không khớp: key {api_key.provider} vs yêu cầu {provider}")
                return False

            # Deactivate tất cả các key khác cùng provider
            APIKey.query.filter_by(provider=provider).update({APIKey.is_active: False})
            
            # Activate key hiện tại
            api_key.is_active = True
            api_key.last_checked = datetime.now()
            db.session.commit()

            key_value = api_key.key.strip()
            
            # Cấu hình client tương ứng
            if provider == 'openai':
                self._current_openai_key = key_value
                self._openai_client = OpenAI(api_key=key_value)
                WebConfig.set_value('openai_api_key', key_value, 'api')
                logger.info(f"Đã kích hoạt OpenAI key: {api_key.name}")

            elif provider == 'gemini':
                self._current_gemini_key = key_value
                genai.configure(api_key=key_value)
                self._gemini_client = genai.GenerativeModel('gemini-pro')
                logger.info(f"Đã kích hoạt Gemini key: {api_key.name}")

            return True

        except Exception as e:
            logger.error(f"Lỗi khi kích hoạt API key: {str(e)}", exc_info=True)
            db.session.rollback()
            return False
    # Trong models/web_config.py (hoặc file chứa model APIKey)
    @classmethod
    def set_active_key(cls, key_id, provider):
        """Phương thức class để set active key và trả về key đó"""
        try:
            # Deactivate tất cả các key cùng provider
            cls.query.filter_by(provider=provider).update({cls.is_active: False})
            
            # Activate key được chọn
            key = cls.query.get(key_id)
            if key:
                key.is_active = True
                key.last_checked = datetime.now()
                db.session.commit()
                return key
            return None
        except Exception as e:
            db.session.rollback()
            raise e


    def delete_api_key(self, key_id):
        """Xóa một API key"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                return APIKey.delete_key(key_id)
            return False
        except Exception as e:
            logger.error(f"Error deleting API key: {str(e)}")
            return False

    def deactivate_api_key(self, key_id):
        """Vô hiệu hóa một API key (không xóa)"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return False
                    
                api_key.is_active = False
                db.session.commit()
                
                if api_key.is_active:
                    other_key = APIKey.query.filter_by(
                        provider=api_key.provider, 
                        is_valid=True, 
                        is_active=True
                    ).filter(APIKey.id != key_id).first()
                    
                    if other_key:
                        self.set_active_api_key(other_key.id, api_key.provider)
                    else:
                        api_key.is_active = False
                        db.session.commit()
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error deactivating API key: {str(e)}")
            return False

    def reactivate_api_key(self, key_id):
        """Kích hoạt lại một API key đã bị vô hiệu hóa"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return False
                    
                api_key = self.refresh_api_key_status(key_id)
                if not api_key or not api_key.is_valid:
                    return False
                    
                api_key.is_active = True
                db.session.commit()
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error reactivating API key: {str(e)}")
            return False

    def refresh_api_key_status(self, key_id):
        """Cập nhật trạng thái của một API key"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                
                if api_key:
                    validity_result = self.check_api_key_validity(api_key.key, api_key.provider)
                    
                    is_valid = validity_result['valid']
                    status_message = validity_result['message']
                    response_time = validity_result['details'].get('response_time_ms')
                    available_models = json.dumps(validity_result['details'].get('available_models', [])) if is_valid else None
                    error_details = validity_result['details'].get('error') if not is_valid else None
                    
                    return APIKey.update_key_status(
                        key_id, 
                        is_valid, 
                        status_message, 
                        response_time, 
                        available_models, 
                        error_details
                    )
            return None
        except Exception as e:
            logger.error(f"Error refreshing API key status: {str(e)}")
            return None

def get_api_key_manager():
    return APIKeyManager()