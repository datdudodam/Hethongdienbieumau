from openai import OpenAI
from models.web_config import WebConfig, APIKey
from models.user import db  # Thêm dòng này để import db
from datetime import datetime
import time
import logging
import json
from flask import current_app
logger = logging.getLogger(__name__)

class APIKeyManager:
    """Quản lý API key OpenAI từ cơ sở dữ liệu"""
    
    _instance = None
    _client = None
    _current_api_key = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def _initialize(self):
        """Khởi tạo các giá trị mặc định"""
        if not self._initialized:
            self._current_api_key = ''
            self._client = None
            self._initialized = True
    
    def get_client(self):
        """Lấy client OpenAI hiện tại, khởi tạo nếu cần"""
        try:
            print("DEBUG: Initializing APIKeyManager")  # Debug
            self._initialize()
            
            print("DEBUG: Getting active API key")  # Debug
            active_key = self._get_active_api_key()
            print(f"DEBUG: Active key result: {active_key}")  # Debug
            
            if not active_key:
                print("DEBUG: No active key, trying to get from WebConfig")  # Debug
                db_api_key = self._get_api_key_from_config()
                print(f"DEBUG: WebConfig key: {db_api_key}")  # Debug
                
                if db_api_key is None:
                    print("DEBUG: No application context available")  # Debug
                    logger.warning("No application context available. Returning None client.")
                    return None
                    
                if db_api_key and db_api_key.strip() != "":
                    print("DEBUG: Adding legacy API key to database")  # Debug
                    self.add_api_key(db_api_key, "Legacy API Key")
                    active_key = self._get_active_api_key()
                    print(f"DEBUG: New active key after adding legacy: {active_key}")  # Debug
            
            if active_key:
                print(f"DEBUG: Current API key: {self._current_api_key}, New active key: {active_key.key}")  # Debug
                if active_key.key != self._current_api_key:
                    print("DEBUG: API key changed, reinitializing client")  # Debug
                    self._current_api_key = active_key.key
                    if self._current_api_key and self._current_api_key.strip() != "":
                        print("DEBUG: Creating new OpenAI client")  # Debug
                        self._client = OpenAI(api_key=self._current_api_key)
                        print("DEBUG: Client created successfully")  # Debug
                    else:
                        print("DEBUG: Empty API key provided")  # Debug
                        self._client = None
                        logger.warning("Empty OpenAI API key provided")
            
            print(f"DEBUG: Returning client: {self._client}")  # Debug
            return self._client
        except Exception as e:
            print(f"DEBUG: Error in get_client: {str(e)}")  # Debug
            logger.error(f"Error getting OpenAI client: {str(e)}")
            return None
    
    def _get_api_key_from_config(self):
        """Lấy API key từ WebConfig với xử lý application context (tương thích ngược)"""
        try:
            # Kiểm tra xem có application context không
            if current_app and hasattr(current_app, 'app_context'):
                return WebConfig.get_value('openai_api_key', '')
            return None
        except RuntimeError as e:
            if "working outside of application context" in str(e).lower():
                logger.warning("Working outside of application context")
                return None
            raise
            
    def _get_active_api_key(self):
        """Lấy API key đang hoạt động từ bảng APIKey"""
        try:
            print("DEBUG: Checking for application context")  # Debug
            if current_app and hasattr(current_app, 'app_context'):
                print("DEBUG: Getting active key from database")  # Debug
                active_key = APIKey.get_active_key('openai')
                print(f"DEBUG: Active key: {active_key}")  # Debug
                if active_key:
                    print(f"DEBUG: Active key details - ID: {active_key.id}, Key: {active_key.key[:4]}...")  # Debug
                return active_key
            print("DEBUG: No application context")  # Debug
            return None
        except Exception as e:
            print(f"DEBUG: Error getting active API key: {str(e)}")  # Debug
            logger.error(f"Error getting active API key: {str(e)}")
            return None
    
    def check_api_key_validity(self, api_key=None):
        """Kiểm tra tính hợp lệ của API key
        
        Args:
            api_key: API key cần kiểm tra, nếu None thì kiểm tra key hiện tại
            
        Returns:
            dict: Thông tin về trạng thái của API key
        """
        # Nếu không có api_key được truyền vào, sử dụng client hiện tại
        if api_key is None:
            client = self.get_client()
        else:
            # Tạo client tạm thời với api_key được truyền vào
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
            
            # Lấy toàn bộ danh sách models
            all_models = [model.id for model in response.data]
            
            # Phân loại models
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
            logger.error(f"API key validation error: {error_message}")
            
            # Phân tích lỗi để đưa ra thông báo phù hợp
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
    
    def add_api_key(self, new_api_key, name=None,description=None, provider='openai'):
        """Thêm API key mới vào hệ thống và kiểm tra tính hợp lệ
        
        Args:
            new_api_key (str): API key mới
            name (str, optional): Tên hiển thị của API key
            provider (str, optional): Nhà cung cấp API (mặc định: 'openai')
            description (str, optional): Mô tả cho API key
        Returns:
            APIKey: Đối tượng API key đã được thêm vào hệ thống
        """
        try:
            if not new_api_key or new_api_key.strip() == "":
                logger.warning("Empty API key provided")
                return None
                
            # Kiểm tra application context
            if not (current_app and hasattr(current_app, 'app_context')):
                logger.warning("Cannot add API key - no application context")
                return None
                
            # Kiểm tra tính hợp lệ của API key
            validity_result = self.check_api_key_validity(new_api_key)
            
            # Thêm API key vào cơ sở dữ liệu
            api_key = APIKey.add_key(new_api_key, name, provider, description)
            
            # Cập nhật trạng thái của API key
            is_valid = validity_result['valid']
            status_message = validity_result['message']
            
            # Lưu thông tin chi tiết
            response_time = None
            available_models = None
            error_details = None
            
            if is_valid:
                response_time = validity_result['details'].get('response_time_ms')
                available_models = json.dumps(validity_result['details'].get('available_models', []))
            else:
                error_details = validity_result['details'].get('error')
            
            # Cập nhật trạng thái
            APIKey.update_key_status(
                api_key.id, 
                is_valid, 
                status_message, 
                response_time, 
                available_models, 
                error_details
            )
            
            # Nếu đây là API key đầu tiên hoặc không có key nào đang hoạt động, đặt làm key mặc định
            active_key = APIKey.get_active_key(provider)
            if not active_key:
                APIKey.set_active_key(api_key.id, provider)
                
                # Cập nhật client hiện tại
                if is_valid:
                    self._current_api_key = new_api_key
                    self._client = OpenAI(api_key=new_api_key)
            
            # Cập nhật WebConfig cho tương thích ngược
            if is_valid and not active_key:
                WebConfig.set_value('openai_api_key', new_api_key, 'api')
            
            return api_key
        except Exception as e:
            logger.error(f"Error adding API key: {str(e)}")
            return None
    def get_key_details(self, key_id):
        """Lấy thông tin chi tiết về API key
        
        Args:
            key_id (int): ID của API key cần lấy thông tin
            
        Returns:
            dict: Thông tin chi tiết về API key hoặc None nếu không tìm thấy
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return None
                    
                # Kiểm tra lại trạng thái nếu cần
                if not api_key.last_checked or (datetime.now() - api_key.last_checked).total_seconds() > 3600:  # 1 giờ
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
        """
        Kiểm tra tính hợp lệ của API key và cập nhật trạng thái
        
        Args:
            key_id (int): ID của API key cần kiểm tra
            
        Returns:
            tuple: (success: bool, result: dict/str)
        """
        try:
            # Lấy thông tin API key từ database
            api_key = APIKey.query.get(key_id)
            if not api_key:
                return False, "API key không tồn tại"
            
            # Kiểm tra tính hợp lệ của key
            validity_result = self.check_api_key_validity(api_key.key)
            
            # Chuẩn bị dữ liệu để cập nhật
            is_valid = validity_result['valid']
            status_message = validity_result['message']
            response_time = validity_result['details'].get('response_time_ms')
            available_models = json.dumps(validity_result['details'].get('available_models', [])) if is_valid else None
            error_details = validity_result['details'].get('error') if not is_valid else None
            
            # Cập nhật trạng thái key trong database
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
            
            # Trả về kết quả chi tiết nếu key hợp lệ
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
    def update_api_key(self, new_api_key):
            """Cập nhật API key mới vào cơ sở dữ liệu (tương thích ngược)"""
            try:
                if new_api_key and new_api_key.strip() != "":
                    # Kiểm tra application context trước khi cập nhật
                    if not (current_app and hasattr(current_app, 'app_context')):
                        logger.warning("Cannot update API key - no application context")
                        return None

                    # Kiểm tra key đã tồn tại chưa
                    existing_key = APIKey.query.filter_by(key=new_api_key).first()
                    if existing_key:
                        logger.info("API key already exists, setting as active")
                        APIKey.set_active_key(existing_key.id, provider='openai')
                        self._current_api_key = new_api_key
                        self._client = OpenAI(api_key=new_api_key)
                    else:
                        # Thêm và kiểm tra key mới
                        self.add_api_key(new_api_key, name="Updated Key")

                    # Cập nhật trong WebConfig để tương thích ngược
                    WebConfig.set_value('openai_api_key', new_api_key, 'api')
                    return True
                else:
                    logger.warning("Empty API key provided for update")
                    return False
            except Exception as e:
                logger.error(f"Error updating API key: {str(e)}")
                return False

            
    def get_all_api_keys(self, provider='openai'):
        """Lấy tất cả API key của một provider
        
        Args:
            provider (str, optional): Nhà cung cấp API (mặc định: 'openai')
            
        Returns:
            list: Danh sách các API key
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                return APIKey.get_all_keys(provider)
            return []
        except Exception as e:
            logger.error(f"Error getting API keys: {str(e)}")
            return []
    
    def set_active_api_key(self, key_id, provider='openai'):
        """Đặt một API key làm key hoạt động chính
        
        Args:
            key_id (int): ID của API key
            provider (str, optional): Nhà cung cấp API (mặc định: 'openai')
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.set_active_key(key_id, provider)
                
                if api_key:
                    # Cập nhật client hiện tại
                    self._current_api_key = api_key.key
                    self._client = OpenAI(api_key=api_key.key)
                    
                    # Cập nhật WebConfig cho tương thích ngược
                    WebConfig.set_value('openai_api_key', api_key.key, 'api')
                    
                    return True
            return False
        except Exception as e:
            logger.error(f"Error setting active API key: {str(e)}")
            return False
    
    def delete_api_key(self, key_id):
        """Xóa một API key
        
        Args:
            key_id (int): ID của API key
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                return APIKey.delete_key(key_id)
            return False
        except Exception as e:
            logger.error(f"Error deleting API key: {str(e)}")
            return False
    
    def deactivate_api_key(self, key_id):
        """Vô hiệu hóa một API key (không xóa)
        
        Args:
            key_id (int): ID của API key
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return False
                    
                # Đánh dấu key là không hoạt động
                api_key.is_active = False
                db.session.commit()
                
                # Nếu đây là key đang hoạt động, cần chọn key khác
                if api_key.is_active:
                    # Tìm key hợp lệ khác để đặt làm active
                    other_key = APIKey.query.filter_by(
                        provider=api_key.provider, 
                        is_valid=True, 
                        is_active=True
                    ).filter(APIKey.id != key_id).first()
                    
                    if other_key:
                        self.set_active_api_key(other_key.id, api_key.provider)
                    else:
                        # Đánh dấu không có key nào đang hoạt động
                        api_key.is_active = False
                        db.session.commit()
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error deactivating API key: {str(e)}")
            return False

    def reactivate_api_key(self, key_id):
        """Kích hoạt lại một API key đã bị vô hiệu hóa
        
        Args:
            key_id (int): ID của API key
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                if not api_key:
                    return False
                    
                # Kiểm tra lại tính hợp lệ của key trước khi kích hoạt
                api_key = self.refresh_api_key_status(key_id)
                if not api_key or not api_key.is_valid:
                    return False
                    
                # Đánh dấu key là đang hoạt động
                api_key.is_active = True
                db.session.commit()
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error reactivating API key: {str(e)}")
            return False

    def refresh_api_key_status(self, key_id):
        """Cập nhật trạng thái của một API key
        
        Args:
            key_id (int): ID của API key
            
        Returns:
            APIKey: API key đã được cập nhật trạng thái
        """
        try:
            if current_app and hasattr(current_app, 'app_context'):
                api_key = APIKey.query.get(key_id)
                
                if api_key:
                    # Kiểm tra tính hợp lệ của API key
                    validity_result = self.check_api_key_validity(api_key.key)
                    
                    # Cập nhật trạng thái
                    is_valid = validity_result['valid']
                    status_message = validity_result['message']
                    
                    # Lưu thông tin chi tiết
                    response_time = None
                    available_models = None
                    error_details = None
                    
                    if is_valid:
                        response_time = validity_result['details'].get('response_time_ms')
                        available_models = json.dumps(validity_result['details'].get('available_models', []))
                    else:
                        error_details = validity_result['details'].get('error')
                    
                    # Cập nhật trạng thái
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


# Singleton instance
def get_api_key_manager():
    return APIKeyManager()