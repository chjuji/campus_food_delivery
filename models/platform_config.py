from extensions import db
from datetime import datetime

class PlatformConfig(db.Model):
    """平台配置信息模型"""
    __tablename__ = 'platform_config'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False, comment='配置键名')
    config_value = db.Column(db.Text, nullable=True, comment='配置值')
    config_type = db.Column(db.String(20), nullable=False, default='string', comment='配置类型：string, number, boolean等')
    description = db.Column(db.String(200), nullable=True, comment='配置描述')
    category = db.Column(db.String(50), nullable=True, default='basic', comment='配置分类')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description,
            'category': self.category,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
    
    @classmethod
    def get_by_key(cls, key):
        """根据键名获取配置"""
        return cls.query.filter_by(config_key=key).first()
    
    @classmethod
    def get_by_category(cls, category):
        """根据分类获取配置列表"""
        return cls.query.filter_by(category=category).all()
    
    @classmethod
    def get_all(cls):
        """获取所有配置"""
        return cls.query.all()
    
    @classmethod
    def get_delivery_fee_earnings(cls):
        """获取平台配送费收入配置"""
        config = cls.get_by_key('delivery_fee_earnings')
        return float(config.config_value) if config else 0.00
    
    @classmethod
    def update_delivery_fee_earnings(cls, amount):
        """更新平台配送费收入配置"""
        # 限制为两位小数
        amount = round(float(amount), 2)
        
        config = cls.get_by_key('delivery_fee_earnings')
        if config:
            config.config_value = str(amount)
            db.session.commit()
            return config
        return None
    
    @classmethod
    def add_wallet_config(cls, key, value, description):
        """添加钱包相关配置"""
        existing = cls.get_by_key(key)
        if not existing:
            new_config = cls(
                config_key=key,
                config_value=str(value),
                config_type='number',
                description=description,
                category='basic'
            )
            db.session.add(new_config)
            db.session.commit()
            return new_config
        return existing
