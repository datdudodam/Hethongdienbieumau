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