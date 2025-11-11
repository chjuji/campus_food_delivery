from datetime import datetime
from models.order import Order
from app import db

def simulate_payment(order_id: int, pay_type: str) -> bool:
    """模拟支付"""
    order = Order.query.get(order_id)
    if not order:
        raise ValueError("订单不存在")
    if order.status != '待接单':
        raise ValueError("订单状态错误")
    
    # 模拟支付成功
    order.status = '待接单'  # 支付后仍为待接单（商家需手动接单）
    order.pay_type = pay_type
    order.pay_time = datetime.now()
    db.session.commit()
    return True