import hashlib
import hmac
import json
import uuid
import requests
from datetime import datetime
from flask import url_for, current_app
from models.user import User, db

class MomoPayment:
    def __init__(self, config=None):
        """
        Khởi tạo đối tượng thanh toán MoMo với các thông số cấu hình
        
        Args:
            config (dict): Cấu hình cho MoMo API
        """
        self.config = config or {}
        self.partner_code = self.config.get('partner_code', 'MOMO')
        self.access_key = self.config.get('access_key', 'F8BBA842ECF85')
        self.secret_key = self.config.get('secret_key', 'K951B6PE1waDMi640xX08PD3vg6EkVlz')
        self.api_endpoint = self.config.get('api_endpoint', 'https://test-payment.momo.vn/v2/gateway/api/create')
        self.return_url = self.config.get('return_url', '')
        self.notify_url = self.config.get('notify_url', '')
        self.ipn_url = self.config.get('ipn_url', '')
    
    def create_signature(self, data):
        """
        Tạo chữ ký cho request MoMo
        
        Args:
            data (dict): Dữ liệu cần tạo chữ ký
            
        Returns:
            str: Chữ ký đã được mã hóa
        """
        # Sắp xếp các tham số theo thứ tự alphabet
        keys = sorted(data.keys())
        
        # Tạo chuỗi raw signature
        raw_signature = "&".join([f"{key}={data[key]}" for key in keys])
        
        # Tạo HMAC-SHA256 signature
        h = hmac.new(bytes(self.secret_key, 'utf-8'), 
                    bytes(raw_signature, 'utf-8'), 
                    hashlib.sha256)
        
        return h.hexdigest()
    
    def create_payment_request(self, order_id, amount, order_info, user_id, subscription_type):
        """
        Tạo yêu cầu thanh toán MoMo
        """
        request_id = str(uuid.uuid4())

        # Tạo extraData đúng định dạng và mã hóa base64
        extra_data_json = json.dumps({
            'user_id': user_id,
            'subscription_type': subscription_type
        })
        import base64
        extra_data = base64.b64encode(extra_data_json.encode('utf-8')).decode('utf-8')

        request_data = {
            'partnerCode': self.partner_code,
            'accessKey': self.access_key,
            'requestId': request_id,
            'amount': str(amount),  # 💡 nên ép thành chuỗi
            'orderId': order_id,
            'orderInfo': order_info,
            'redirectUrl': self.return_url,
            'ipnUrl': self.ipn_url,
            'extraData': extra_data,
            'requestType': 'captureWallet',
            'lang': 'vi'
        }

        # ✅ Tạo chữ ký chính xác từ raw data
        request_data['signature'] = self.create_signature(request_data)

        try:
            response = requests.post(
                self.api_endpoint,
                json=request_data,
                headers={'Content-Type': 'application/json'}
            )
            return response.json()
        except Exception as e:
            current_app.logger.error(f"Error creating MoMo payment: {str(e)}")
            return {'errorCode': -1, 'message': str(e)}

    
    def verify_ipn_signature(self, ipn_params):
        """
        Xác thực chữ ký từ MoMo IPN callback
        
        Args:
            ipn_params (dict): Tham số từ MoMo IPN callback
            
        Returns:
            bool: True nếu chữ ký hợp lệ, False nếu không
        """
        # Lấy chữ ký từ request
        received_signature = ipn_params.get('signature')
        if not received_signature:
            return False
        
        # Tạo bản sao của params và loại bỏ signature
        params_to_verify = ipn_params.copy()
        params_to_verify.pop('signature', None)
        
        # Tạo chữ ký mới từ params
        calculated_signature = self.create_signature(params_to_verify)
        
        # So sánh chữ ký
        return calculated_signature == received_signature
    
    def process_payment_callback(self, callback_params):
        """
        Xử lý callback từ MoMo sau khi thanh toán
        
        Args:
            callback_params (dict): Tham số callback từ MoMo
            
        Returns:
            dict: Kết quả xử lý
        """
        # Xác thực chữ ký
        if not self.verify_ipn_signature(callback_params):
            return {'success': False, 'message': 'Invalid signature'}
        
        # Kiểm tra trạng thái thanh toán
        result_code = callback_params.get('resultCode')
        if result_code != 0:
            return {'success': False, 'message': callback_params.get('message', 'Payment failed')}
        
        try:
            # Lấy thông tin từ extraData và giải mã base64
            import base64
            extra_data_base64 = callback_params.get('extraData', '')
            extra_data_json = base64.b64decode(extra_data_base64).decode('utf-8')
            extra_data = json.loads(extra_data_json)
            
            user_id = extra_data.get('user_id')
            subscription_type = extra_data.get('subscription_type')
            
            if not user_id or not subscription_type:
                return {'success': False, 'message': 'Missing user or subscription information'}
            
            # Cập nhật thông tin đăng ký cho người dùng
            self.update_user_subscription(user_id, subscription_type)
            
            # Lưu thông tin giao dịch vào cơ sở dữ liệu (có thể thêm model Transaction)
            
            return {'success': True, 'message': 'Payment processed successfully'}
        except Exception as e:
            current_app.logger.error(f"Error processing payment callback: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def update_user_subscription(self, user_id, subscription_type):
        """
        Cập nhật thông tin đăng ký cho người dùng
        
        Args:
            user_id (int): ID của người dùng
            subscription_type (str): Loại gói đăng ký
        """
        try:
            import datetime
            now = datetime.datetime.now()
            
            # Lấy thông tin người dùng
            user = User.query.get(user_id)
            if not user:
                current_app.logger.error(f"User not found: {user_id}")
                return
            
            # Cập nhật thông tin đăng ký
            user.subscription_type = subscription_type
            user.subscription_start = now
            
            # Thiết lập thời hạn dựa trên loại gói
            if subscription_type == 'standard':
                # Gói Thường có hạn 1 tháng kể từ đầu tháng
                user.subscription_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                user.subscription_end = (user.subscription_start + datetime.timedelta(days=31)).replace(day=1) - datetime.timedelta(seconds=1)
            elif subscription_type == 'vip':
                # Gói VIP không giới hạn thời gian hoặc có thể set hạn dùng dài hơn
                user.subscription_end = None
            
            # Reset số lượt tải xuống hàng tháng
            user.monthly_download_count = 0
            
            # Lưu thay đổi
            db.session.commit()
            current_app.logger.info(f"Updated subscription for user {user_id} to {subscription_type}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating user subscription: {str(e)}")
            raise

# Hàm tiện ích để tạo mã đơn hàng
def generate_order_id(user_id):
    """
    Tạo mã đơn hàng duy nhất
    
    Args:
        user_id (int): ID của người dùng
        
    Returns:
        str: Mã đơn hàng
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"ORDER_{user_id}_{timestamp}"

# Hàm tiện ích để lấy giá gói đăng ký
def get_subscription_price(subscription_type):
    """
    Lấy giá của gói đăng ký
    
    Args:
        subscription_type (str): Loại gói đăng ký
        
    Returns:
        int: Giá gói đăng ký (VND)
    """
    prices = {
        'free': 0,
        'standard': 99000,  # 99,000 VND
        'vip': 199000       # 199,000 VND
    }
    return prices.get(subscription_type, 0)