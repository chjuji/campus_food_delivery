from extensions import db
from app import create_app

def remove_pay_type_column():
    """从数据库表中移除pay_type字段"""
    app = create_app()
    with app.app_context():
        # 执行原始SQL来移除字段
        db.session.execute(db.text('ALTER TABLE food_order DROP COLUMN pay_type'))
        db.session.commit()
        print("Successfully removed pay_type column from food_order table")

if __name__ == '__main__':
    remove_pay_type_column()