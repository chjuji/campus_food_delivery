import uuid
from datetime import datetime
from models.order import Order, OrderItem
from models.cart import Cart
from app import db

def create_order(student_id: int, merchant_id: int, address: str, pay_type: str, remark: str = '', coupon = None):
    """从购物车创建订单"""
    # 查询该学生在该商户的购物车商品
    cart_items = Cart.query.filter_by(student_id=student_id).join(
        Cart.dish
    ).filter_by(merchant_id=merchant_id).all()
    
    if not cart_items:
        raise ValueError("购物车为空")
    
    # 计算金额
    total_amount = sum(item.dish.price * item.quantity for item in cart_items)
    pay_amount = total_amount
    
    # 应用优惠券
    discount_amount = 0
    if coupon:
        # 检查是否满足最低消费条件
        if total_amount >= coupon.min_spend:
            # 根据优惠券类型计算折扣
            if coupon.type == '满减' or coupon.type == '无门槛':
                discount_amount = min(coupon.value, total_amount)  # 确保折扣不超过总价
                pay_amount = total_amount - discount_amount
            elif coupon.type == '折扣':
                discount_amount = total_amount * (1 - coupon.value / 10)  # 假设value是折扣百分比，如8.5表示85折
                pay_amount = total_amount - discount_amount
            
            # 确保支付金额不为负数
            if pay_amount < 0:
                pay_amount = 0
    
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
            remark=remark,
            coupon_id=coupon.id if coupon else None,
            discount_amount=discount_amount
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