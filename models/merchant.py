from datetime import datetime
from extensions import db
from models.comment import Comment

class Merchant(db.Model):
    __tablename__ = 'merchant'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    merchant_name = db.Column(db.String(100), nullable=False, comment='店铺名称')
    contact_name = db.Column(db.String(50), nullable=False, comment='联系人')
    contact_phone = db.Column(db.String(11), nullable=False, comment='联系电话')
    license_img = db.Column(db.String(255), nullable=False, comment='营业执照')
    logo = db.Column(db.String(255), comment='商铺Logo')
    address = db.Column(db.String(255), nullable=False, comment='店铺地址')
    description = db.Column(db.Text, comment='商铺描述')
    business_hours = db.Column(db.String(50), comment='营业时间，格式：09:00-22:00')
    is_open = db.Column(db.Boolean, default=True, comment='商铺状态：True-营业中 False-休息中')
    status = db.Column(db.Integer, default=0, comment='0-待审核 1-已通过 2-已下架')
    service_fee = db.Column(db.Float, default=0.05, comment='平台服务费比例')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    password = db.Column(db.String(128), nullable=False)

    # 关联关系
    dishes = db.relationship('Dish', backref='merchant', lazy=True)
    orders = db.relationship('Order', backref='merchant', lazy=True)
    coupons = db.relationship('Coupon', backref='merchant', lazy=True)
    comments = db.relationship('Comment', backref='merchant', lazy=True)

    def __repr__(self):
        return f'<Merchant {self.merchant_name}>'
