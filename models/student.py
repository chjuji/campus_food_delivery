from datetime import datetime
from extensions import db

class Student(db.Model):
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False, comment='学号')
    phone = db.Column(db.String(11), unique=True, nullable=False, comment='手机号')
    password = db.Column(db.String(128), nullable=False, comment='加密密码')
    pay_password = db.Column(db.String(128), nullable=True, default=None, comment='支付密码')
    name = db.Column(db.String(50), nullable=False, comment='姓名')
    avatar = db.Column(db.String(255), default='default_avatar.jpg', comment='头像路径')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='注册时间')
    is_active = db.Column(db.Boolean, default=True, comment='账户是否激活')
    gender = db.Column(db.String(10), default='未知', comment='性别')
    wallet = db.Column(db.Numeric(10, 2), default=0.00, comment='钱包余额')

    # 关联关系
    orders = db.relationship('Order', backref='student', lazy=True)
    cart_items = db.relationship('Cart', backref='student', lazy=True)
    comments = db.relationship('Comment', backref='student', lazy=True)
    addresses = db.relationship('Address', backref='student', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Student {self.student_id}>'