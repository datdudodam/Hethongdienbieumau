from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models.user import db, User

class Transaction(db.Model):
    __tablename__ = 'transactions'  # ✅ thêm dòng này
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Số tiền thanh toán (VND)
    payment_method = db.Column(db.String(50), nullable=False)  # 'momo', 'card', etc.
    subscription_type = db.Column(db.String(20), nullable=False)  # 'standard', 'vip'
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending', 'completed', 'failed'
    transaction_ref = db.Column(db.String(100), nullable=True)  # Mã tham chiếu từ cổng thanh toán
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    response_data = db.Column(db.Text, nullable=True)  # Dữ liệu phản hồi từ cổng thanh toán (JSON)
    
    # Quan hệ với User
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))
    
    def __repr__(self):
        return f'<Transaction {self.order_id}>'
    
    @classmethod
    def create_transaction(cls, user_id, order_id, amount, payment_method, subscription_type):
        """
        Tạo một giao dịch mới
        
        Args:
            user_id (int): ID của người dùng
            order_id (str): Mã đơn hàng
            amount (int): Số tiền thanh toán
            payment_method (str): Phương thức thanh toán
            subscription_type (str): Loại gói đăng ký
            
        Returns:
            Transaction: Đối tượng giao dịch đã được tạo
        """
        transaction = cls(
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            payment_method=payment_method,
            subscription_type=subscription_type,
            status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return transaction
    
    def update_status(self, status, transaction_ref=None, response_data=None):
        """
        Cập nhật trạng thái giao dịch
        
        Args:
            status (str): Trạng thái mới ('pending', 'completed', 'failed')
            transaction_ref (str, optional): Mã tham chiếu từ cổng thanh toán
            response_data (str, optional): Dữ liệu phản hồi từ cổng thanh toán (JSON)
        """
        self.status = status
        
        if transaction_ref:
            self.transaction_ref = transaction_ref
            
        if response_data:
            self.response_data = response_data
            
        self.updated_at = datetime.now()
        db.session.commit()