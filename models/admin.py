from extensions import db

class Admin(db.Model):
    """管理员配置表，用于管理配送费"""
    __tablename__ = 'admin'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    delivery_fee = db.Column(db.Float, default=5.0, nullable=False, comment='配送费，默认5元')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'delivery_fee': self.delivery_fee
        }
    
    @classmethod
    def get_config(cls):
        """获取管理员配置，只有一条记录"""
        config = cls.query.first()
        if not config:
            # 如果没有记录，创建一条默认记录
            config = cls(delivery_fee=5.0)
            db.session.add(config)
            db.session.commit()
        return config
    
    @classmethod
    def update_delivery_fee(cls, delivery_fee):
        """更新配送费"""
        config = cls.get_config()
        config.delivery_fee = delivery_fee
        db.session.commit()
        return config
