from datetime import datetime
from extensions import db

class Complaint(db.Model):
    __tablename__ = 'complaint'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    order_id = db.Column(db.Integer, db.ForeignKey('food_order.id'), comment='关联订单ID')
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), comment='关联商户ID')
    content = db.Column(db.Text, nullable=False, comment='投诉内容')
    img_urls = db.Column(db.Text, comment='证据图片')
    status = db.Column(db.String(20), default='待处理', comment='状态：待处理/已解决/已驳回')
    handle_result = db.Column(db.Text, comment='处理结果')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='投诉时间')
    handle_time = db.Column(db.DateTime, comment='处理时间')

    def __repr__(self):
        return f'<Complaint {self.id}>'