from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime,timezone

db = SQLAlchemy()

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(200))
    users = db.relationship('User', backref='role', lazy=True)
    
    @staticmethod
    def insert_roles():
        roles = {
            'admin': 'Quản trị viên hệ thống',
            'user': 'Người dùng thông thường'
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r, description=roles[r])
                db.session.add(role)
        db.session.commit()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)  # Nullable for Google login
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), default=2)  # Default to regular user role (2)
    
    # Google OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    
    
    # Additional profile fields
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Subscription and download tracking fields
    free_downloads_left = db.Column(db.Integer, default=5)  # 5 free downloads for new users
    subscription_type = db.Column(db.String(20), default='free')  # 'free', 'standard', 'vip'
    subscription_start = db.Column(db.DateTime, nullable=True)
    subscription_end = db.Column(db.DateTime, nullable=True)
    monthly_download_count = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
