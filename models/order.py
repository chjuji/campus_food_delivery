from datetime import datetime
from extensions import db

class Order(db.Model):
    __tablename__ = 'food_order'  # 修改为非保留关键字

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_no = db.Column(db.String(32), unique=True, nullable=False, comment='订单号')
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False, comment='商户ID')
    total_amount = db.Column(db.Float, nullable=False, comment='总金额')
    pay_amount = db.Column(db.Float, nullable=False, comment='实付金额')
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupon.id'), nullable=True, comment='优惠券ID')
    discount_amount = db.Column(db.Float, default=0, nullable=False, comment='优惠金额')

    status = db.Column(db.String(20), nullable=False, comment='状态：待支付/已支付/待接单/待配送/已完成/已取消')
    address = db.Column(db.String(255), nullable=False, comment='收货地址')
    remark = db.Column(db.Text, comment='备注')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    pay_time = db.Column(db.DateTime, comment='支付时间')
    finish_time = db.Column(db.DateTime, comment='完成时间')

    # 关联关系
    order_items = db.relationship('OrderItem', backref='order', lazy=True)
    comment = db.relationship('Comment', backref='order', foreign_keys='Comment.order_id', uselist=False)
    refund = db.relationship('Refund', backref='order', uselist=False)

    def __repr__(self):
        return f'<Order {self.order_no}>'

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'student_id': self.student_id,
            'merchant_id': self.merchant_id,
            'total_amount': self.total_amount,
            'pay_amount': self.pay_amount,
            'coupon_id': self.coupon_id,
            'discount_amount': self.discount_amount,

            'status': self.status,
            'address': self.address,
            'remark': self.remark,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'pay_time': self.pay_time.isoformat() if self.pay_time else None,
            'finish_time': self.finish_time.isoformat() if self.finish_time else None
        }

class OrderItem(db.Model):
    __tablename__ = 'food_order_item'  # 修改为非保留关键字

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('food_order.id'), nullable=False, comment='订单ID')
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False, comment='菜品ID')
    quantity = db.Column(db.Integer, nullable=False, comment='数量')
    price = db.Column(db.Float, nullable=False, comment='购买时单价')

    def __repr__(self):
        return f'<OrderItem {self.id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'dish_id': self.dish_id,
            'quantity': self.quantity,
            'price': self.price
        }

class Refund(db.Model):
    __tablename__ = 'food_refund'  # 修改为非保留关键字

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('food_order.id'), nullable=False, comment='订单ID')
    refund_amount = db.Column(db.Float, nullable=False, comment='退款金额')
    reason = db.Column(db.Text, nullable=False, comment='退款原因')
    status = db.Column(db.String(20), default='申请中', comment='状态：申请中/已同意/已拒绝')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='申请时间')
    handle_time = db.Column(db.DateTime, comment='处理时间')

    def __repr__(self):
        return f'<Refund {self.id}>'