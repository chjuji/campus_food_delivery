from datetime import datetime
from models.order import Order
from models.merchant import Merchant
from models.admin import Admin
from app import db

def simulate_payment(order_id: int) -> bool:
    """模拟支付"""
    order = Order.query.get(order_id)
    if not order:
        raise ValueError("订单不存在")
    if order.status != '待支付':
        raise ValueError("订单状态错误")
    
    # 模拟支付成功
    order.status = '待接单'  # 支付后订单状态改为待接单
    order.pay_time = datetime.now()
    
      # 获取配送费（从Admin表获取）
    admin_config = Admin.get_config()
    delivery_fee = admin_config.delivery_fee

    # 获取对应商户
    merchant = Merchant.query.get(order.merchant_id)
    if merchant:
        # 计算商户应得金额（包含配送费）
        order_amount = float(order.pay_amount)
        delivery_fee = float(delivery_fee)
        
        old_balance = float(merchant.wallet)
        merchant.wallet = old_balance + order_amount
        new_balance = float(merchant.wallet)
        
        # 添加详细日志，包括配送费信息
        print(f"商户 {merchant.merchant_name} 钱包更新：")
        print(f"  - 订单实付金额：¥{order_amount:.2f}（含配送费：¥{delivery_fee:.2f}）")
        print(f"  - 原余额：¥{old_balance:.2f}")
        print(f"  - 新余额：¥{new_balance:.2f}")
        print(f"  - 本次增加：¥{order_amount:.2f}")
    
    db.session.commit()
    return True