from datetime import datetime
from models.order import Order
from models.merchant import Merchant
from models.platform_config import PlatformConfig
from app import db

def simulate_payment(order_id: int) -> tuple[bool, int]:
    """模拟支付"""
    order = Order.query.get(order_id)
    if not order:
        raise ValueError("订单不存在")
    if order.status != '待支付':
        raise ValueError("订单状态错误")
    
    # 模拟支付成功
    order.status = '待接单'  # 支付后订单状态改为待接单
    order.pay_time = datetime.now()
    
    # 标记优惠券为已使用
    from models.coupon import UserCoupon
    if order.coupon_id:
        # 查找用户的优惠券
        user_coupon = UserCoupon.query.filter_by(
            student_id=order.student_id,
            coupon_id=order.coupon_id,
            is_used=False
        ).first()
        
        if user_coupon:
            user_coupon.is_used = True
            user_coupon.use_time = datetime.now()
            # 更新优惠券使用次数
            coupon = user_coupon.coupon
            if coupon:
                coupon.used += 1
    
      # 获取配送费（从PlatformConfig表获取）
    config = PlatformConfig.get_by_key('default_delivery_fee')
    delivery_fee = float(config.config_value) if config else 5.0  # 默认5元

    # 获取对应商户
    merchant = Merchant.query.get(order.merchant_id)
    if merchant:
        # 计算商户应得金额（不含配送费）
        order_amount = float(order.pay_amount)
        delivery_fee = float(delivery_fee)
        merchant_earnings = order_amount - delivery_fee
        
        old_balance = float(merchant.wallet)
        merchant.wallet = old_balance + merchant_earnings
        new_balance = float(merchant.wallet)
        
        # 添加详细日志，包括配送费信息
        print(f"商户 {merchant.merchant_name} 钱包更新：")
        print(f"  - 订单实付金额：¥{order_amount:.2f}")
        print(f"  - 配送费：¥{delivery_fee:.2f}（平台收取）")
        print(f"  - 商户应得：¥{merchant_earnings:.2f}")
        print(f"  - 原余额：¥{old_balance:.2f}")
        print(f"  - 新余额：¥{new_balance:.2f}")
        print(f"  - 本次增加：¥{merchant_earnings:.2f}")
    
    # 更新平台配送费收入
    current_earnings = PlatformConfig.get_delivery_fee_earnings()
    new_earnings = current_earnings + float(delivery_fee)
    PlatformConfig.update_delivery_fee_earnings(new_earnings)
    
    # 添加配送费收入日志
    print(f"平台配送费收入更新：")
    print(f"  - 原收入：¥{current_earnings:.2f}")
    print(f"  - 新增配送费：¥{delivery_fee:.2f}")
    print(f"  - 新收入：¥{new_earnings:.2f}")
    
    # 先提交订单状态和钱包更新的事务
    db.session.commit()
    
    # 支付成功后，为用户发放商户的已激活优惠券
    coupons_added = 0
    try:
        from models.coupon import Coupon, UserCoupon
        
        # 查询商户的所有已激活且在有效期内的优惠券
        current_time = datetime.now()
        
        active_coupons = Coupon.query.filter_by(
            merchant_id=order.merchant_id,
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
                student_id=order.student_id,
                coupon_id=coupon.id
            ).first()
            
            # 如果未领取，且优惠券还有剩余数量
            if not existing and coupon.used < coupon.total:
                # 创建用户优惠券记录
                user_coupon = UserCoupon(
                    student_id=order.student_id,
                    coupon_id=coupon.id
                )
                coupons_to_add.append(user_coupon)
                db.session.add(user_coupon)
        
        # 提交发放优惠券的事务
        if active_coupons:
            db.session.commit()
            coupons_added = len(coupons_to_add)
    except Exception as e:
        # 优惠券发放失败不影响订单支付，记录错误即可
        import traceback
        traceback.print_exc()  # 打印详细的异常堆栈信息
        db.session.rollback()
    
    return True, coupons_added