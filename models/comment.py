from datetime import datetime
from extensions import db

class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False, comment='订单ID')
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False, comment='商户ID')
    dish_score = db.Column(db.Integer, nullable=False, comment='菜品评分1-5')
    service_score = db.Column(db.Integer, nullable=False, comment='服务评分1-5')
    content = db.Column(db.Text, comment='评价内容')
    img_urls = db.Column(db.Text, comment='评价图片（逗号分隔）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='评价时间')
    merchant_reply = db.Column(db.Text, comment='商家回复')
    reply_time = db.Column(db.DateTime, comment='回复时间')

    def __repr__(self):
        return f'<Comment {self.id}>'