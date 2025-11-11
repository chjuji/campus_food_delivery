from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.order import Order, Refund
from services.payment_service import simulate_payment
from extensions import db

order_bp = Blueprint('order', __name__)

# 支付订单
@order_bp.post('/pay/<int:order_id>')
@jwt_required()
def pay_order(order_id):
    identity = get_jwt_identity()
    data = request.get_json()
    pay_type = data.get('pay_type', 'wechat')
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'code': 404, 'msg': '订单不存在'}), 404
    if order.student_id != identity['id']:
        return jsonify({'code': 403, 'msg': '无权操作此订单'}), 403
    
    try:
        simulate_payment(order_id, pay_type)
        return jsonify({'code': 200, 'msg': '支付成功'})
    except Exception as e:
        return jsonify({'code': 500, 'msg': str(e)}), 500

# 申请退款
@order_bp.post('/refund/apply/<int:order_id>')
@jwt_required()
def apply_refund(order_id):
    identity = get_jwt_identity()
    data = request.get_json()
    reason = data.get('reason')
    
    if not reason:
        return jsonify({'code': 400, 'msg': '请填写退款原因'}), 400
    
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'code': 404, 'msg': '订单不存在'}), 404
    if order.student_id != identity['id']:
        return jsonify({'code': 403, 'msg': '无权操作此订单'}), 403
    
    # 检查是否已申请过退款
    if Refund.query.filter_by(order_id=order_id).first():
        return jsonify({'code': 400, 'msg': '已申请过退款'}), 400
    
    refund = Refund(
        order_id=order_id,
        refund_amount=order.pay_amount,
        reason=reason
    )
    db.session.add(refund)
    db.session.commit()
    
    return jsonify({'code': 200, 'msg': '退款申请已提交'})