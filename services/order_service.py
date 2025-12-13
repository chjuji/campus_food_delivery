import uuid
from datetime import datetime
from models.order import Order, OrderItem
from models.cart import Cart
from models.address import Address
from models.merchant import Merchant
from models.platform_config import PlatformConfig
from models.coupon import Coupon, UserCoupon
from models.dish import Dish
from app import db

def create_order(student_id: int, merchant_id: int, address_id: int, remark: str = '', coupon = None, cart_item_ids=None, status='待支付', user_coupon=None):
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
    
    # 获取配送费（从PlatformConfig表获取）
    config = PlatformConfig.get_by_key('default_delivery_fee')
    delivery_fee = float(config.config_value) if config else 5.0  # 默认5元
    
    # 计算总金额（菜品总价 + 配送费）
    total_amount = dish_total + delivery_fee
    pay_amount = total_amount
    
    # 应用优惠券
    discount_amount = 0
    if coupon:
        # 检查是否满足最低消费条件（最低消费只算菜品费用）
        if dish_total >= coupon.min_spend:
            # 根据优惠券类型计算折扣（只对菜品费用进行折扣）
            if coupon.type == '满减' or coupon.type == '无门槛':
                discount_amount = min(coupon.value, dish_total)  # 确保折扣不超过菜品总价
                # 实付金额 = 菜品总价 - 折扣金额 + 配送费
                pay_amount = dish_total - discount_amount + delivery_fee
            elif coupon.type == '折扣':
                discount_amount = dish_total * (1 - coupon.value / 10)  # 只对菜品费用进行折扣
                # 实付金额 = 菜品总价 - 折扣金额 + 配送费
                pay_amount = dish_total - discount_amount + delivery_fee
            
            # 确保支付金额不为负数
            if pay_amount < 0:
                pay_amount = 0
            
            # 使用优惠券后更新状态
            if user_coupon and status != '待支付':  # 只有当订单支付成功时才使用优惠券
                user_coupon.is_used = True
                user_coupon.use_time = datetime.now()
                coupon.used += 1
    
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
        
        # 如果订单状态不是待支付（即已经支付），更新库存
        if status != '待支付':
            # 获取菜品信息
            dish = Dish.query.get(item.dish_id)
            if dish and dish.stock != 0:  # 库存为0表示无限库存，不做处理
                # 当前库存等于订单数量时，支付成功后直接变为-1
                if dish.stock == item.quantity:
                    dish.stock = -1
                else:
                    # 其他情况下库存减去订单数量
                    dish.stock -= item.quantity
                print(f"订单创建时，菜品 {dish.dish_name} 库存更新：原库存 {dish.stock + item.quantity}，订单数量 {item.quantity}，新库存 {dish.stock}")
    
    # 如果订单状态不是待支付，说明已经支付，需要给商户钱包加钱
    if status != '待支付':
        # 获取对应商户
        merchant = Merchant.query.get(merchant_id)
        if merchant:
            # 计算商户应得金额（不含配送费）
            merchant_earnings = float(pay_amount) - delivery_fee
            
            # 给商户钱包加上对应菜品的价值（不含配送费）
            old_balance = float(merchant.wallet)
            merchant.wallet = old_balance + merchant_earnings
            new_balance = float(merchant.wallet)
            print(f"订单创建时，商户 {merchant.merchant_name} 钱包金额增加：{merchant_earnings}，原余额：{old_balance}，新余额：{new_balance}")
    
        # 更新平台配送费收入
        current_earnings = PlatformConfig.get_delivery_fee_earnings()
        new_earnings = current_earnings + float(delivery_fee)
        PlatformConfig.update_delivery_fee_earnings(new_earnings)
        
        # 添加配送费收入日志
        print(f"订单创建时，平台配送费收入增加：{delivery_fee}，原收入：{current_earnings}，新收入：{new_earnings}")
    
    # 发放优惠券
    coupons_added = 0
    if status == '待接单':
        try:
            # 查询商户的所有已激活且在有效期内的优惠券
            current_time = datetime.now()
            active_coupons = Coupon.query.filter_by(
                merchant_id=merchant_id,
                is_active=True
            ).filter(
                Coupon.start_time <= current_time,
                Coupon.end_time >= current_time
            ).all()
            
            # 为学生发放符合条件的优惠券
            coupons_to_add = []
            for coupon in active_coupons:
                # 检查学生是否已领取过该优惠券
                existing = UserCoupon.query.filter_by(
                    student_id=student_id,
                    coupon_id=coupon.id
                ).first()
                
                # 如果未领取，且优惠券还有剩余数量
                if not existing and coupon.used < coupon.total:
                    # 创建用户优惠券记录
                    user_coupon = UserCoupon(
                        student_id=student_id,
                        coupon_id=coupon.id
                    )
                    coupons_to_add.append(user_coupon)
                    db.session.add(user_coupon)
            
            coupons_added = len(coupons_to_add)
        except Exception as e:
            # 优惠券发放失败不影响订单创建，记录错误即可
            import traceback
            traceback.print_exc()
    
    # 提交订单创建的事务
    db.session.commit()
    
    return order, coupons_added