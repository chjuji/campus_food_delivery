from datetime import datetime
from extensions import db

class Address(db.Model):
    __tablename__ = 'address'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    recipient = db.Column(db.String(50), nullable=False, comment='收件人姓名')
    phone = db.Column(db.String(11), nullable=False, comment='联系电话')
    province = db.Column(db.String(50), nullable=False, comment='省份')
    city = db.Column(db.String(50), nullable=False, comment='城市')
    district = db.Column(db.String(50), nullable=False, comment='区县')
    detail_address = db.Column(db.String(200), nullable=False, comment='详细地址')
    is_default = db.Column(db.Boolean, default=False, comment='是否默认地址')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 关联关系
    # student 关系在 Student 模型中已定义
    
    def __repr__(self):
        return f'<Address {self.id}: {self.recipient} - {self.detail_address}>'