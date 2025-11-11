from datetime import datetime
from extensions import db

class Coupon(db.Model):
    __tablename__ = 'coupon'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False, comment='商户ID')
    coupon_name = db.Column(db.String(50), nullable=False, comment='优惠券名称')
    type = db.Column(db.String(20), nullable=False, comment='类型：满减/折扣/无门槛')
    value = db.Column(db.Float, nullable=False, comment='满减金额/折扣比例')
    min_spend = db.Column(db.Float, default=0, comment='最低消费')
    total = db.Column(db.Integer, nullable=False, comment='总数量')
    used = db.Column(db.Integer, default=0, comment='已使用数量')
    start_time = db.Column(db.DateTime, nullable=False, comment='开始时间')
    end_time = db.Column(db.DateTime, nullable=False, comment='结束时间')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联用户领取记录
    user_coupons = db.relationship('UserCoupon', backref='coupon', lazy=True)

    def __repr__(self):
        return f'<Coupon {self.coupon_name}>'

class UserCoupon(db.Model):
    __tablename__ = 'user_coupon'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupon.id'), nullable=False, comment='优惠券ID')
    is_used = db.Column(db.Boolean, default=False, comment='是否使用')
    use_time = db.Column(db.DateTime, comment='使用时间')
    get_time = db.Column(db.DateTime, default=datetime.now, comment='领取时间')

    __table_args__ = (db.UniqueConstraint('student_id', 'coupon_id', name='unique_user_coupon'),)

    def __repr__(self):
        return f'<UserCoupon {self.id}>'