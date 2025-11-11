from datetime import datetime
from extensions import db

class Cart(db.Model):
    __tablename__ = 'cart'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, comment='学生ID')
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False, comment='菜品ID')
    quantity = db.Column(db.Integer, default=1, comment='数量')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='添加时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 联合唯一约束（同一学生不能重复添加同一菜品）
    __table_args__ = (db.UniqueConstraint('student_id', 'dish_id', name='unique_student_dish'),)

    def __repr__(self):
        return f'<Cart {self.id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'dish_id': self.dish_id,
            'quantity': self.quantity,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'update_time': self.update_time.isoformat() if self.update_time else None
        }