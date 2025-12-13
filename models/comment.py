from datetime import datetime
from extensions import db

class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey('food_order.id'), unique=True, nullable=False, comment='订单ID')
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False, comment='商户ID')
    dish_score = db.Column(db.Integer, nullable=False, comment='菜品评分1-5')
    service_score = db.Column(db.Integer, nullable=False, comment='服务评分1-5')
    content = db.Column(db.Text, comment='评价内容')
    img_urls = db.Column(db.Text, comment='评价图片（逗号分隔）')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='评价时间')
    merchant_reply = db.Column(db.Text, comment='商家回复')
    reply_time = db.Column(db.DateTime, comment='回复时间')

    @property
    def formatted_img_urls(self):
        """将图片URL中的单数形式路径转换为复数形式"""
        if not self.img_urls:
            return []
        # 分割URL列表
        urls = self.img_urls.split(',')
        # 将单数形式的'comment'替换为复数形式的'comments'
        formatted_urls = [url.replace('/comment/', '/comments/') for url in urls]
        return formatted_urls

    def __repr__(self):
        return f'<Comment {self.id}>'