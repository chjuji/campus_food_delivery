from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.student import Student
from models.cart import Cart
from models.dish import Dish
from services.auth_service import student_register, student_login
from services.order_service import create_order
from utils.validator import validate_student_register
from extensions import db
import bcrypt

student_bp = Blueprint('student', __name__)

# 注册
@student_bp.post('/register')  # 对应前端请求的/api/student/register
def register():
    data = request.get_json()
    student_id = data.get('student_id')
    phone = data.get('phone')
    password = data.get('password')
    name = data.get('name')

    # 校验逻辑（示例）
    if Student.query.filter_by(student_id=student_id).first():
        return jsonify({'code': 400, 'msg': '学号已注册'})
    if len(password) < 8:
        return jsonify({'code': 400, 'msg': '密码需8-20位'})
    required = ['student_id', 'name', 'password']
    if not all(k in data for k in required):
        return jsonify({'code': 400, 'msg': '缺少必填字段'})
    
    # 密码加密
    hashed_pwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    new_student = Student(
        student_id=student_id,
        phone=phone,
        password=hashed_pwd.decode('utf-8'),
        name=name
    )
    # 保存到数据库
    try:
        db.session.add(new_student)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '注册成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'注册失败：{str(e)}'}), 500

# 登录
@student_bp.post('/login')
def login():
    data = request.get_json()
    login_id = data.get('student_id') or data.get('phone')
    password = data.get('password')
    
    if not login_id or not password:
        return jsonify({'code': 400, 'msg': '请输入账号和密码'}), 400
    
    result = student_login(login_id, password)
    if not result or isinstance(result, dict) and result.get('error'):
        # 如果返回包含具体错误信息，直接传递给前端
        msg = result.get('error') if isinstance(result, dict) else '账号或密码错误'
        return jsonify({'code': 401, 'msg': msg}), 401
    
    return jsonify({
        'code': 200,
        'msg': '登录成功',
        'data': result
    })

# 获取个人信息
@student_bp.get('/profile')
@jwt_required()
def get_profile():
    identity = get_jwt_identity()
    if identity['type'] != 'student':
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    student = Student.query.get(identity['id'])
    if not student:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'student_id': student.student_id,
            'name': student.name,
            'phone': student.phone,
            'avatar': student.avatar,
            'register_time': student.create_time.strftime('%Y-%m-%d %H:%M')
        }
    })

# 添加购物车
@student_bp.route('/cart/add', methods=['POST'])
@jwt_required()
def add_to_cart():
    try:
        current_user = get_jwt_identity()
        if current_user['type'] != 'student':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        data = request.json
        dish_id = data.get('dish_id')
        quantity = data.get('quantity', 1)
        
        if not dish_id:
            return jsonify({
                'code': 400,
                'msg': '缺少菜品ID'
            }), 400
        
        # 检查菜品是否存在
        dish = Dish.query.get(dish_id)
        if not dish:
            return jsonify({
                'code': 404,
                'msg': '菜品不存在'
            }), 404
        
        # 检查菜品是否上架
        if not dish.is_shelf:
            return jsonify({
                'code': 400,
                'msg': '该菜品已下架'
            }), 400
        
        # 检查购物车中是否已有该菜品
        cart_item = Cart.query.filter_by(
            student_id=current_user['id'],
            dish_id=dish_id
        ).first()
        
        if cart_item:
            # 更新数量
            cart_item.quantity += quantity
        else:
            # 创建新的购物车项
            cart_item = Cart(
                student_id=current_user['id'],
                dish_id=dish_id,
                quantity=quantity
            )
            db.session.add(cart_item)
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '添加购物车成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'添加购物车失败：{str(e)}'
        }), 500

@student_bp.route('/cart', methods=['GET'])
@jwt_required()
def get_cart():
    try:
        current_user = get_jwt_identity()
        if current_user['type'] != 'student':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        cart_items = Cart.query.filter_by(student_id=current_user['id']).all()
        
        cart_data = []
        for item in cart_items:
            cart_data.append({
                'id': item.id,
                'dish': item.dish.to_dict(),
                'quantity': item.quantity
            })
        
        return jsonify({
            'code': 200,
            'msg': '获取购物车成功',
            'data': cart_data
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取购物车失败：{str(e)}'
        }), 500

@student_bp.route('/cart/<int:cart_id>', methods=['PUT'])
@jwt_required()
def update_cart_item(cart_id):
    try:
        current_user = get_jwt_identity()
        if current_user['type'] != 'student':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        data = request.json
        quantity = data.get('quantity', 1)
        
        cart_item = Cart.query.filter_by(id=cart_id, student_id=current_user['id']).first()
        if not cart_item:
            return jsonify({
                'code': 404,
                'msg': '购物车项不存在'
            }), 404
        
        if quantity < 1:
            db.session.delete(cart_item)
        else:
            cart_item.quantity = quantity
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '更新成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'更新失败：{str(e)}'
        }), 500

@student_bp.route('/cart/<int:cart_id>', methods=['DELETE'])
@jwt_required()
def delete_cart_item(cart_id):
    try:
        current_user = get_jwt_identity()
        if current_user['type'] != 'student':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        cart_item = Cart.query.filter_by(id=cart_id, student_id=current_user['id']).first()
        
        if not cart_item:
            return jsonify({
                'code': 404,
                'msg': '购物车项不存在'
            }), 404
        
        db.session.delete(cart_item)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'删除失败：{str(e)}'
        }), 500

@student_bp.route('/cart/clear', methods=['DELETE'])
@jwt_required()
def clear_cart():
    try:
        current_user = get_jwt_identity()
        if current_user['type'] != 'student':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        cart_items = Cart.query.filter_by(student_id=current_user['id']).all()
        
        for item in cart_items:
            db.session.delete(item)
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '清空购物车成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'清空购物车失败：{str(e)}'
        }), 500

# 创建订单
@student_bp.post('/order/create')
@jwt_required()
def create_student_order():
    identity = get_jwt_identity()
    if identity['type'] != 'student':
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    data = request.get_json()
    merchant_id = data.get('merchant_id')
    address = data.get('address')
    pay_type = data.get('pay_type', 'wechat')
    
    if not merchant_id or not address:
        return jsonify({'code': 400, 'msg': '缺少商户ID或地址'}), 400
    
    try:
        order = create_order(
            student_id=identity['id'],
            merchant_id=merchant_id,
            address=address,
            pay_type=pay_type,
            remark=data.get('remark', '')
        )
        return jsonify({
            'code': 200,
            'msg': '订单创建成功',
            'data': {'order_no': order.order_no, 'pay_amount': order.pay_amount}
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'创建订单失败：{str(e)}'}), 500