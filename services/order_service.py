import uuid
from datetime import datetime
from models.order import Order, OrderItem
from models.cart import Cart
from app import db

def create_order(student_id: int, merchant_id: int, address: str, pay_type: str, remark: str = ''):
    """从购物车创建订单"""
    # 查询该学生在该商户的购物车商品
    cart_items = Cart.query.filter_by(student_id=student_id).join(
        Cart.dish
    ).filter_by(merchant_id=merchant_id).all()
    
    if not cart_items:
        raise ValueError("购物车为空")
    
    # 计算金额
    total_amount = sum(item.dish.price * item.quantity for item in cart_items)
    pay_amount = total_amount  # 简化：暂不处理优惠
    
    # 生成订单号
    order_no = f"ORD{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    
    # 创建订单
    order = Order(
        order_no=order_no,
        student_id=student_id,
        merchant_id=merchant_id,
        total_amount=total_amount,
        pay_amount=pay_amount,
        pay_type=pay_type,
        status='待接单',
        address=address,
        remark=remark
    )
    db.session.add(order)
    db.session.flush()  # 获取order.id
    
    # 创建订单项
    for item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            dish_id=item.dish_id,
            quantity=item.quantity,
            price=item.dish.price
        )
        db.session.add(order_item)
        # 清空购物车
        db.session.delete(item)
    
    db.session.commit()
    return order