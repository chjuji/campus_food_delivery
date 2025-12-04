import uuid
from datetime import datetime
from models.order import Order, OrderItem
from models.cart import Cart
from models.address import Address
from models.merchant import Merchant
from models.admin import Admin
from app import db

def create_order(student_id: int, merchant_id: int, address_id: int, remark: str = '', coupon = None, cart_item_ids=None, status='待支付'):
    """从购物车创建订单"""
    # 获取地址信息
    address_obj = Address.query.get(address_id)
    if not address_obj:
        raise ValueError("地址不存在")
    
    # 构建完整地址字符串
    address = f"{address_obj.province}{address_obj.city}{address_obj.district}{address_obj.detail_address} {address_obj.recipient} {address_obj.phone}"
    
    # 构建查询
    query = Cart.query.filter_by(student_id=student_id).join(Cart.dish).filter_by(merchant_id=merchant_id)
    
    # 如果提供了cart_item_ids，则只查询这些ID的购物车项
    if cart_item_ids:
        query = query.filter(Cart.id.in_(cart_item_ids))
    
    # 执行查询
    cart_items = query.all()
    
    if not cart_items:
        raise ValueError("购物车为空")
    
    # 计算菜品总价
    dish_total = sum(item.dish.price * item.quantity for item in cart_items)
    
    # 获取配送费（从Admin表获取）
    admin_config = Admin.get_config()
    delivery_fee = admin_config.delivery_fee
    
    # 计算总金额（菜品总价 + 配送费）
    total_amount = dish_total + delivery_fee
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
            # delivery_fee=delivery_fee,
            status=status,
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
    
    # 如果订单状态不是待支付，说明已经支付，需要给商户钱包加钱
    if status != '待支付':
        # 获取对应商户
        merchant = Merchant.query.get(merchant_id)
        if merchant:
            # 给商户钱包加上对应菜品的价值（实付金额）
            old_balance = float(merchant.wallet)
            merchant.wallet = old_balance + float(pay_amount)
            new_balance = float(merchant.wallet)
            print(f"订单创建时，商户 {merchant.merchant_name} 钱包金额增加：{pay_amount}，原余额：{old_balance}，新余额：{new_balance}")
    
    db.session.commit()
    return order