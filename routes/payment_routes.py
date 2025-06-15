from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_required, current_user
from models.user import db, User
from models.transaction import Transaction
from utils.momo_payment import MomoPayment, generate_order_id, get_subscription_price
import json
import os

def register_payment_routes(app):
    """ Đăng ký các route liên quan đến thanh toán """
    
    # Khởi tạo đối tượng MomoPayment với cấu hình từ biến môi trường
    from flask import request
    
    # Lấy domain từ request hoặc sử dụng giá trị mặc định
    host_url = os.environ.get('HOST_URL', 'http://localhost:55003')
    
    momo_config = {
        'partner_code': os.environ.get('MOMO_PARTNER_CODE', 'MOMO'),
        'access_key': os.environ.get('MOMO_ACCESS_KEY', 'F8BBA842ECF85'),
        'secret_key': os.environ.get('MOMO_SECRET_KEY', 'K951B6PE1waDMi640xX08PD3vg6EkVlz'),
        'api_endpoint': os.environ.get('MOMO_API_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/create'),
        'return_url': os.environ.get('MOMO_RETURN_URL', f'{host_url}/payment/momo/return'),
        'ipn_url': os.environ.get('MOMO_IPN_URL', f'{host_url}/payment/momo/ipn'),
    }
    momo_payment = MomoPayment(momo_config)
    
    @app.route('/payment/momo/create', methods=['POST'])
    @login_required
    def create_momo_payment():
        """ Tạo yêu cầu thanh toán MoMo """
        try:
            # Lấy thông tin từ form
            base_url = request.host_url.rstrip('/')
            momo_payment.config.update({
                'return_url': f"{base_url}/payment/momo/return",
                'ipn_url': f"{base_url}/payment/momo/ipn"
            })
            subscription_type = request.form.get('subscription_type', 'standard')
            phone_number = request.form.get('phone_number')
            print("Phone:", phone_number)

            
            # Kiểm tra loại gói đăng ký
            if subscription_type not in ['standard', 'vip']:
                flash('Loại gói đăng ký không hợp lệ', 'error')
                return redirect(url_for('profile'))
            
            # Lấy giá gói đăng ký
            amount = get_subscription_price(subscription_type)
            if amount <= 0:
                flash('Giá gói đăng ký không hợp lệ', 'error')
                return redirect(url_for('profile'))
            
            # Tạo mã đơn hàng
            order_id = generate_order_id(current_user.id)
            
            # Tạo thông tin đơn hàng
            order_info = f"Thanh toán gói {subscription_type} cho tài khoản {current_user.email}"
            
            # Lưu thông tin giao dịch vào cơ sở dữ liệu
            transaction = Transaction.create_transaction(
                user_id=current_user.id,
                order_id=order_id,
                amount=amount,
                payment_method='momo',
                subscription_type=subscription_type
            )
            
            # Tạo yêu cầu thanh toán MoMo
            payment_response = momo_payment.create_payment_request(
                order_id=order_id,
                amount=amount,
                order_info=order_info,
                user_id=current_user.id,
                subscription_type=subscription_type
            )
            print(">>> Momo response:", payment_response)
            
            # Kiểm tra kết quả từ MoMo
            if payment_response.get('errorCode') != 0:
                # Cập nhật trạng thái giao dịch
                transaction.update_status(
                    status='failed',
                    response_data=json.dumps(payment_response)
                )
                
                flash(f"Lỗi tạo giao dịch: {payment_response.get('message', 'Lỗi không xác định')}", 'error')
                return redirect(url_for('profile'))
            
            # Cập nhật thông tin giao dịch
            transaction.update_status(
                status='pending',
                transaction_ref=payment_response.get('requestId'),
                response_data=json.dumps(payment_response)
            )
            
            # Chuyển hướng đến trang thanh toán MoMo
            pay_url = payment_response.get('payUrl')
            if pay_url:
                return redirect(pay_url)
            else:
                flash('Không thể tạo URL thanh toán', 'error')
                return redirect(url_for('profile'))
                
        except Exception as e:
            current_app.logger.error(f"Error creating MoMo payment: {str(e)}")
            flash(f"Lỗi khi tạo giao dịch: {str(e)}", 'error')
            return redirect(url_for('profile'))
    
    @app.route('/payment/momo/return')
    def momo_payment_return():
        """ Xử lý kết quả trả về từ MoMo """
        # Lấy tham số từ URL
        result_code = request.args.get('resultCode')
        order_id = request.args.get('orderId')
        message = request.args.get('message')
        
        # Tìm giao dịch trong cơ sở dữ liệu
        transaction = Transaction.query.filter_by(order_id=order_id).first()
        
        if not transaction:
            flash('Không tìm thấy thông tin giao dịch', 'error')
            return redirect(url_for('profile'))
        
        # Kiểm tra kết quả thanh toán
        if result_code == '0':
            # Thanh toán thành công
            transaction.update_status(
                status='completed',
                response_data=json.dumps(request.args.to_dict())
            )
            
            # Cập nhật thông tin đăng ký cho người dùng
            momo_payment.update_user_subscription(
                user_id=transaction.user_id,
                subscription_type=transaction.subscription_type
            )
            
            flash('Thanh toán thành công! Gói dịch vụ của bạn đã được nâng cấp.', 'success')
        else:
            # Thanh toán thất bại
            transaction.update_status(
                status='failed',
                response_data=json.dumps(request.args.to_dict())
            )
            
            flash(f"Thanh toán thất bại: {message}", 'error')
        
        return redirect(url_for('profile'))
    
    @app.route('/payment/momo/ipn', methods=['POST'])
    def momo_payment_ipn():
        """ Xử lý IPN (Instant Payment Notification) từ MoMo """
        try:
            # Lấy dữ liệu từ request
            ipn_data = request.json
            
            # Xử lý callback từ MoMo
            result = momo_payment.process_payment_callback(ipn_data)
            
            # Trả về kết quả cho MoMo
            if result.get('success'):
                return jsonify({'status': 'ok', 'message': 'Success'}), 200
            else:
                return jsonify({'status': 'error', 'message': result.get('message')}), 400
                
        except Exception as e:
            current_app.logger.error(f"Error processing MoMo IPN: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    @app.route('/payment/momo/request', methods=['POST'])
    @login_required
    def request_momo_payment():
        """ Xử lý yêu cầu thanh toán MoMo từ JavaScript """
        try:
            # Lấy thông tin từ request
            data = request.get_json()
            print(">>> JSON data:", data)
            print(">>> form data:", request.form)
            print(">>> current_user:", current_user)
            print(">>> is_authenticated:", current_user.is_authenticated)

            if not data:
                # Nếu không phải JSON, thử lấy từ form data
                phone_number = request.form.get('phone_number')
                subscription_type = request.form.get('subscription_type', 'standard')
            else:
                phone_number = data.get('phone_number')
                subscription_type = data.get('subscription_type', 'standard')
            
            print(">>> phone_number:", phone_number)
            print(">>> subscription_type:", subscription_type)
            
            # Kiểm tra số điện thoại
            if not phone_number or len(phone_number) < 10:
                error_msg = 'Số điện thoại không hợp lệ'
                print(">>> Error:", error_msg)
                return jsonify({'success': False, 'message': error_msg}), 400
            
            # Kiểm tra loại gói đăng ký
            if subscription_type not in ['standard', 'vip']:
                error_msg = 'Loại gói đăng ký không hợp lệ'
                print(">>> Error:", error_msg)
                return jsonify({'success': False, 'message': error_msg}), 400
            
            # Lấy giá gói đăng ký
            amount = get_subscription_price(subscription_type)
            if amount <= 0:
                error_msg = 'Giá gói đăng ký không hợp lệ'
                print(">>> Error:", error_msg)
                return jsonify({'success': False, 'message': error_msg}), 400
            
            # Tạo mã đơn hàng
            order_id = generate_order_id(current_user.id)
            print(">>> order_id:", order_id)
            
            # Tạo thông tin đơn hàng
            order_info = f"Thanh toán gói {subscription_type} cho tài khoản {current_user.email}"
            
            # Lưu thông tin giao dịch vào cơ sở dữ liệu
            transaction = Transaction.create_transaction(
                user_id=current_user.id,
                order_id=order_id,
                amount=amount,
                payment_method='momo',
                subscription_type=subscription_type
            )
            
            # Tạo yêu cầu thanh toán MoMo
            payment_response = momo_payment.create_payment_request(
                order_id=order_id,
                amount=amount,
                order_info=order_info,
                user_id=current_user.id,
                subscription_type=subscription_type
            )
            
            print(">>> MoMo API response:", payment_response)
            
            # Kiểm tra kết quả từ MoMo
            if payment_response.get('errorCode') != 0:
                # Cập nhật trạng thái giao dịch
                transaction.update_status(
                    status='failed',
                    response_data=json.dumps(payment_response)
                )
                
                error_msg = payment_response.get('message', 'Lỗi không xác định')
                print(">>> MoMo error:", error_msg)
                return jsonify({
                    'success': False, 
                    'message': error_msg
                }), 400
            
            # Cập nhật thông tin giao dịch
            transaction.update_status(
                status='pending',
                transaction_ref=payment_response.get('requestId'),
                response_data=json.dumps(payment_response)
            )
            
            # Trả về URL thanh toán
            pay_url = payment_response.get('payUrl')
            if pay_url:
                print(">>> Success, pay_url:", pay_url)
                return jsonify({
                    'success': True,
                    'pay_url': pay_url,
                    'order_id': order_id
                }), 200
            else:
                error_msg = 'Không thể tạo URL thanh toán'
                print(">>> Error:", error_msg)
                return jsonify({
                    'success': False,
                    'message': error_msg
                }), 400
                
        except Exception as e:
            error_msg = str(e)
            current_app.logger.error(f"Error requesting MoMo payment: {error_msg}")
            print(">>> Exception:", error_msg)
            return jsonify({'success': False, 'message': error_msg}), 500