from datetime import datetime
from extensions import db

class Dish(db.Model):
    __tablename__ = 'dish'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False, comment='商户ID')
    dish_name = db.Column(db.String(50), nullable=False, comment='菜品名称')
    price = db.Column(db.Float, nullable=False, comment='单价')
    stock = db.Column(db.Integer, default=0, comment='库存（0=无限）')
    category = db.Column(db.String(20), nullable=False, comment='分类')
    img_url = db.Column(db.String(255), default='default_dish.jpg', comment='图片路径')
    description = db.Column(db.Text, comment='菜品描述')
    is_shelf = db.Column(db.Boolean, default=True, comment='是否上架')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    cart_items = db.relationship('Cart', backref='dish', lazy=True, cascade="all, delete-orphan")
    order_items = db.relationship('OrderItem', backref='dish', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Dish {self.dish_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'dish_name': self.dish_name,
            'price': self.price,
            'stock': self.stock,
            'category': self.category,
            'img_url': self.img_url,
            'description': self.description,
            'is_shelf': self.is_shelf,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }