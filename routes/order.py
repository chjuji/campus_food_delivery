from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.order import Order, Refund
from models.cart import Cart
from models.dish import Dish
from services.payment_service import simulate_payment
from extensions import db
from routes.student import api_login_required

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

# 购物车数据接口 - 用于首页购物车弹窗
@order_bp.get('/cart')
@api_login_required
def get_order_cart():
    try:
        from flask import session
        user_id = session['student_id']
        # 获取购物车数据
        cart_items = Cart.query.filter_by(student_id=user_id).all()
        
        items = []
        total_amount = 0
        total_count = 0
        
        for item in cart_items:
            dish = Dish.query.get(item.dish_id)
            if dish:
                item_total = float(dish.price) * item.quantity
                total_amount += item_total
                total_count += item.quantity
                
                items.append({
                    'id': item.id,
                    'dish_id': dish.id,
                    'name': dish.name,
                    'price': float(dish.price),
                    'quantity': item.quantity,
                    'total': item_total,
                    'image': dish.image
                })
        
        return jsonify({
            'code': 200,
            'data': {
                'items': items,
                'total_amount': round(total_amount, 2),
                'total_count': total_count
            }
        })
    except Exception as e:
        print(f'获取购物车数据错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '获取购物车数据失败'}), 500