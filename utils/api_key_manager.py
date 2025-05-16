from openai import OpenAI, AuthenticationError, RateLimitError
from models.web_config import WebConfig
from datetime import datetime
import time
import logging
from flask import current_app
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Quản lý API key OpenAI với khả năng fallback khi key hết hạn"""
    
    _instance = None
    _primary_client = None
    _fallback_client = None
    _current_primary_key = None
    _current_fallback_key = None
    _last_key_check = None
    _key_validity_cache = {}
    _active_client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def _initialize(self):
        """Khởi tạo các giá trị mặc định"""
        if not self._initialized:
            self._current_primary_key = ''
            self._current_fallback_key = ''
            self._primary_client = None 
            self._fallback_client = None
            self._active_client = None
            self._last_key_check = None
            self._key_validity_cache = {}
            self._initialized = True
    
    def get_client(self) -> Optional[OpenAI]:
        """
        Lấy client OpenAI đang hoạt động (primary hoặc fallback)
        Tự động chuyển đổi nếu phát hiện key hết hạn
        """
        try:
            self._initialize()
            
            # Kiểm tra và cập nhật các key từ config
            self._update_keys_from_config()
            
            # Nếu không có client nào được khởi tạo, thử khởi tạo primary client
            if self._active_client is None:
                self._switch_to_primary()
                
            # Nếu vẫn không có client hoạt động, thử fallback
            if self._active_client is None:
                self._switch_to_fallback()
                
            return self._active_client
            
        except Exception as e:
            logger.error(f"Error getting OpenAI client: {str(e)}")
            return None
    
    def _update_keys_from_config(self):
        """Cập nhật các key từ cấu hình nếu có thay đổi"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                # Lấy primary key
                primary_key = WebConfig.get_value('openai_api_key', '')
                if primary_key != self._current_primary_key:
                    self._current_primary_key = primary_key
                    self._primary_client = OpenAI(api_key=primary_key) if primary_key else None
                
                # Lấy fallback key
                fallback_key = WebConfig.get_value('openai_fallback_key', '')
                if fallback_key != self._current_fallback_key:
                    self._current_fallback_key = fallback_key
                    self._fallback_client = OpenAI(api_key=fallback_key) if fallback_key else None
                    
        except RuntimeError as e:
            if "working outside of application context" in str(e).lower():
                logger.warning("Working outside of application context")
            else:
                raise
    
    def _switch_to_primary(self) -> bool:
        """Chuyển sang sử dụng primary key"""
        if self._primary_client:
            # Kiểm tra tính hợp lệ của primary key
            validity = self._check_key_validity(self._primary_client, self._current_primary_key)
            if validity['valid']:
                self._active_client = self._primary_client
                logger.info("Switched to PRIMARY OpenAI API key")
                return True
        return False
    
    def _switch_to_fallback(self) -> bool:
        """Chuyển sang sử dụng fallback key khi primary không hoạt động"""
        if self._fallback_client:
            # Kiểm tra tính hợp lệ của fallback key
            validity = self._check_key_validity(self._fallback_client, self._current_fallback_key)
            if validity['valid']:
                self._active_client = self._fallback_client
                logger.warning("Switched to FALLBACK OpenAI API key")
                # Gửi thông báo về việc sử dụng key dự phòng
                self._notify_key_switch(primary_valid=False)
                return True
        return False
    
    def _check_key_validity(self, client: OpenAI, key: str) -> Dict:
        """Kiểm tra tính hợp lệ của một API key cụ thể"""
        if not key or not client:
            return {
                "valid": False,
                "message": "Empty API key or client",
                "details": None
            }
            
        # Kiểm tra cache trước
        cache_key = f"{key[:5]}...{key[-5:]}"
        if cache_key in self._key_validity_cache:
            cached = self._key_validity_cache[cache_key]
            if time.time() - cached['timestamp'] < 300:  # Cache trong 5 phút
                return cached['result']
        
        try:
            start_time = time.time()
            response = client.models.list()
            end_time = time.time()
            
            result = {
                "valid": True,
                "message": "API key hợp lệ",
                "details": {
                    "response_time_ms": round((end_time - start_time) * 1000),
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            # Lưu vào cache
            self._key_validity_cache[cache_key] = {
                'timestamp': time.time(),
                'result': result
            }
            
            return result
            
        except AuthenticationError as e:
            error_msg = str(e)
            if "expired" in error_msg.lower():
                message = "API key đã hết hạn"
            elif "Incorrect API key" in error_msg or "Invalid API key" in error_msg:
                message = "API key không hợp lệ"
            else:
                message = f"Lỗi xác thực: {error_msg}"
                
            result = {
                "valid": False,
                "message": message,
                "details": {
                    "error": error_msg,
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            
            # Lưu vào cache cho key không hợp lệ (cache ngắn hơn)
            self._key_validity_cache[cache_key] = {
                'timestamp': time.time(),
                'result': result
            }
            
            # Gửi thông báo nếu key hết hạn
            if "expired" in error_msg.lower():
                self._notify_key_expired(key, is_primary=(client == self._primary_client))
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            result = {
                "valid": False,
                "message": f"Lỗi khi kiểm tra API key: {error_msg}",
                "details": {
                    "error": error_msg,
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            return result
    
    def _notify_key_expired(self, key: str, is_primary: bool = True):
        """Gửi thông báo khi key hết hạn"""
        key_type = "PRIMARY" if is_primary else "FALLBACK"
        short_key = f"{key[:5]}...{key[-5:]}"
        message = f"OpenAI {key_type} API key {short_key} đã hết hạn hoặc không hợp lệ"
        
        # Ghi log cảnh báo
        logger.warning(message)
        
        # TODO: Thêm logic gửi thông báo qua email/slack/webhook ở đây
        # Ví dụ: send_alert_notification(message)
    
    def _notify_key_switch(self, primary_valid: bool):
        """Gửi thông báo khi chuyển đổi giữa primary và fallback key"""
        if primary_valid:
            message = "Đã chuyển lại về PRIMARY OpenAI API key"
        else:
            message = "Đã chuyển sang sử dụng FALLBACK OpenAI API key do primary key không hoạt động"
        
        logger.warning(message)
        
        # TODO: Thêm logic gửi thông báo qua email/slack/webhook ở đây
    
    def check_api_key_validity(self, force_check: bool = False) -> Dict:
        """
        Kiểm tra tính hợp lệ của API key đang hoạt động
        """
        client = self.get_client()
        active_key = self._current_primary_key if client == self._primary_client else self._current_fallback_key
        
        if not client:
            return {
                "valid": False,
                "message": "Không có client OpenAI nào hoạt động",
                "details": {
                    "primary_key": bool(self._current_primary_key),
                    "fallback_key": bool(self._current_fallback_key),
                    "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        
        # Kiểm tra key hiện tại
        result = self._check_key_validity(client, active_key)
        
        # Nếu key hiện tại không hợp lệ, thử chuyển đổi
        if not result['valid']:
            if client == self._primary_client and self._fallback_client:
                # Thử chuyển sang fallback
                if self._switch_to_fallback():
                    # Kiểm tra lại với fallback client
                    result = self._check_key_validity(self._active_client, self._current_fallback_key)
            elif client == self._fallback_client and self._primary_client:
                # Thử chuyển lại về primary
                if self._switch_to_primary():
                    # Kiểm tra lại với primary client
                    result = self._check_key_validity(self._active_client, self._current_primary_key)
        
        return result
    
    def get_active_key_info(self) -> Dict:
        """Lấy thông tin về key đang hoạt động"""
        if self._active_client == self._primary_client:
            return {
                "type": "primary",
                "key": self._current_primary_key,
                "short_key": f"{self._current_primary_key[:5]}...{self._current_primary_key[-5:]}" if self._current_primary_key else None
            }
        elif self._active_client == self._fallback_client:
            return {
                "type": "fallback",
                "key": self._current_fallback_key,
                "short_key": f"{self._current_fallback_key[:5]}...{self._current_fallback_key[-5:]}" if self._current_fallback_key else None
            }
        else:
            return {
                "type": None,
                "key": None,
                "short_key": None
            }
    
    def update_api_key(self, new_primary_key: str, new_fallback_key: str = None) -> bool:
        """Cập nhật API key mới vào cơ sở dữ liệu"""
        try:
            if current_app and hasattr(current_app, 'app_context'):
                # Cập nhật primary key
                if new_primary_key and new_primary_key.strip() != "":
                    WebConfig.set_value('openai_api_key', new_primary_key, 'api')
                    self._current_primary_key = new_primary_key
                    self._primary_client = OpenAI(api_key=new_primary_key)
                
                # Cập nhật fallback key nếu được cung cấp
                if new_fallback_key is not None:
                    WebConfig.set_value('openai_fallback_key', new_fallback_key, 'api')
                    self._current_fallback_key = new_fallback_key
                    self._fallback_client = OpenAI(api_key=new_fallback_key)
                
                # Reset active client để hệ thống tự động chọn lại
                self._active_client = None
                self.get_client()  # Tự động chọn client tốt nhất
                
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating API keys: {str(e)}")
            return False

# Singleton instance
def get_api_key_manager():
    return APIKeyManager()