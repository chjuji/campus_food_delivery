def send_order_notification(phone: str, order_no: str, status: str):
    """模拟发送订单通知（实际应对接短信API）"""
    print(f"【通知】用户{phone}的订单{order_no}状态更新为：{status}")
    return True