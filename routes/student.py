from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.student import Student
from models.cart import Cart
from models.dish import Dish
from models.coupon import Coupon, UserCoupon
from models.complaint import Complaint
from models.order import Order
from datetime import datetime
from services.auth_service import student_register, student_login
from services.order_service import create_order
from utils.validator import validate_student_register
from extensions import db
import bcrypt

# 检查学生是否已登录的装饰器（API路由用）
def api_login_required(f):
    def decorated_function(*args, **kwargs):
        # 首先检查session中是否有登录信息
        if 'student_id' in session:
            return f(*args, **kwargs)
        
        # 然后检查JWT token
        try:
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            
            if identity and ':' in identity:
                user_type, user_id = identity.split(':', 1)
                if user_type == 'student':
                    # 将student_id添加到session中以便后续使用
                    session['student_id'] = int(user_id)
                    return f(*args, **kwargs)
        except Exception:
            pass
        
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    decorated_function.__name__ = f.__name__
    return decorated_function

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
@api_login_required
def get_profile():
    user_id = session['student_id']
    student = Student.query.get(user_id)
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
@api_login_required
def add_to_cart():
    try:
        current_user = get_jwt_identity()
        # 解析字符串格式的identity "user_type:user_id"
        if isinstance(current_user, str) and ':' in current_user:
            user_type, user_id = current_user.split(':')
            if user_type != 'student':
                return jsonify({'code': 403, 'msg': '权限错误'}), 403
            current_user = {'type': user_type, 'id': int(user_id)}
        else:
            return jsonify({'code': 401, 'msg': '无效的身份信息'}), 401
        
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
@api_login_required
def get_cart():
    try:
        # 直接从session获取学生ID，因为api_login_required装饰器已经确保session中有登录信息
        student_id = session.get('student_id')
        if not student_id:
            return jsonify({'code': 401, 'msg': '未登录或会话已过期'}), 401
        
        # 使用joinedload预加载关联数据，提高性能
        cart_items = Cart.query.filter_by(student_id=student_id).options(
            db.joinedload(Cart.dish).joinedload(Dish.merchant)
        ).all()
        
        cart_data = []
        for item in cart_items:
            # 获取菜品的字典数据
            dish_data = item.dish.to_dict()
            # 添加商家名称到菜品数据中
            if item.dish.merchant:
                dish_data['merchant_name'] = item.dish.merchant.merchant_name
            else:
                dish_data['merchant_name'] = '未知商家'
            
            cart_data.append({
                'id': item.id,
                'dish': dish_data,
                'quantity': item.quantity
            })
        
        return jsonify({
            'code': 200,
            'msg': '获取购物车成功',
            'data': cart_data
        })
    except Exception as e:
        # 添加更详细的错误日志记录
        print(f"购物车API错误详情: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': f'获取购物车失败：{str(e)}'
        }), 500

@student_bp.route('/cart/<int:cart_id>', methods=['PUT'])
@api_login_required
def update_cart_item(cart_id):
    try:
        current_user = get_jwt_identity()
        # 解析字符串格式的identity "user_type:user_id"
        if isinstance(current_user, str) and ':' in current_user:
            user_type, user_id = current_user.split(':')
            if user_type != 'student':
                return jsonify({'code': 403, 'msg': '权限错误'}), 403
            current_user = {'type': user_type, 'id': int(user_id)}
        else:
            return jsonify({'code': 401, 'msg': '无效的身份信息'}), 401
        
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
@api_login_required
def delete_cart_item(cart_id):
    try:
        current_user = get_jwt_identity()
        # 解析字符串格式的identity "user_type:user_id"
        if isinstance(current_user, str) and ':' in current_user:
            user_type, user_id = current_user.split(':')
            if user_type != 'student':
                return jsonify({'code': 403, 'msg': '权限错误'}), 403
            current_user = {'type': user_type, 'id': int(user_id)}
        else:
            return jsonify({'code': 401, 'msg': '无效的身份信息'}), 401
        
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
@api_login_required
def clear_cart():
    try:
        current_user = get_jwt_identity()
        # 解析字符串格式的identity "user_type:user_id"
        if isinstance(current_user, str) and ':' in current_user:
            user_type, user_id = current_user.split(':')
            if user_type != 'student':
                return jsonify({'code': 403, 'msg': '权限错误'}), 403
            current_user = {'type': user_type, 'id': int(user_id)}
        else:
            return jsonify({'code': 401, 'msg': '无效的身份信息'}), 401
        
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
# 获取用户可用的优惠券列表
@student_bp.get('/coupons')
@api_login_required
def get_user_coupons():
    student_id = session['student_id']
    
    try:
        # 查询用户未使用且在有效期内的优惠券
        current_time = datetime.now()
        user_coupons = UserCoupon.query.filter_by(
            student_id=student_id,
            is_used=False
        ).join(Coupon).filter(
            Coupon.start_time <= current_time,
            Coupon.end_time >= current_time
        ).all()
        
        coupon_data = []
        for uc in user_coupons:
            coupon = uc.coupon
            coupon_data.append({
                'id': coupon.id,
                'name': coupon.coupon_name,
                'discount_amount': coupon.value,
                'min_spend': coupon.min_spend,
                'expire_date': coupon.end_time.strftime('%Y-%m-%d'),
                'type': coupon.type
            })
        
        return jsonify({
            'code': 200,
            'data': coupon_data
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取优惠券失败：{str(e)}'}), 500

# 获取用户可用的优惠券数量
@student_bp.get('/coupons/count')
@api_login_required
def get_user_coupon_count():
    student_id = session['student_id']
    
    try:
        current_time = datetime.now()
        count = UserCoupon.query.filter_by(
            student_id=student_id,
            is_used=False
        ).join(Coupon).filter(
            Coupon.start_time <= current_time,
            Coupon.end_time >= current_time
        ).count()
        
        return jsonify({
            'code': 200,
            'data': count
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取优惠券数量失败：{str(e)}'}), 500

# 创建订单
@student_bp.get('/orders')
@api_login_required
def get_student_orders():
    try:
        # 获取当前登录学生ID
        student_id = session.get('student_id')
        if not student_id:
            return jsonify({'code': 401, 'msg': '未登录或会话已过期'}), 401
        
        # 获取查询参数
        status = request.args.get('status', 'all')
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        
        # 构建查询
        query = Order.query.filter_by(student_id=student_id)
        
        # 根据状态筛选
        if status != 'all':
            query = query.filter_by(status=status)
        
        # 按创建时间倒序排序
        query = query.order_by(Order.create_time.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)
        
        # 构建响应数据
        orders_data = []
        for order in pagination.items:
            # 构建符合前端期望的订单数据结构
            order_data = {
                'order_id': order.id,  # 前端期望的字段名
                'status': order.status,
                'created_at': order.create_time.isoformat() if order.create_time else None,
                'total_amount': order.total_amount,
                'address': order.address,
                'delivery_fee': 0,  # 假设配送费为0，根据实际情况调整
                'merchant': {
                    'name': '未知商户'  # 这里需要关联查询merchant信息
                },
                'items': []  # 前端期望的订单项数组名
            }
            
            # 构建订单项
            for item in order.order_items:
                item_data = {
                    'dish_name': item.dish.dish_name if item.dish else '未知菜品',
                    'price': item.price,
                    'quantity': item.quantity
                }
                order_data['items'].append(item_data)
            
            orders_data.append(order_data)
        
        return jsonify({
            'code': 200,
            'msg': '获取订单列表成功',
            'data': {
                'items': orders_data,
                'total': pagination.total,
                'page_size': page_size,
                'page': page
            }
        })
    except Exception as e:
        print(f"订单查询API错误：{str(e)}")
        return jsonify({'code': 500, 'msg': f'获取订单失败：{str(e)}'}), 500

@student_bp.post('/order/create')
@api_login_required
def create_student_order():
    user_id = session['student_id']
    identity = {'type': 'student', 'id': user_id}
    
    data = request.get_json()
    merchant_id = data.get('merchant_id')
    address = data.get('address')
    pay_type = data.get('pay_type', 'wechat')
    coupon_id = data.get('coupon_id')
    remark = data.get('remark', '')
    
    # 验证必填参数
    if not merchant_id or not address:
        return jsonify({'code': 400, 'msg': '缺少商户ID或地址'}), 400
    
    # 验证支付方式
    if pay_type not in ['wechat', 'alipay']:
        return jsonify({'code': 400, 'msg': '不支持的支付方式'}), 400
    
    # 验证优惠券是否有效
    valid_coupon = None
    user_coupon = None
    if coupon_id:
        current_time = datetime.now()
        user_coupon = UserCoupon.query.filter_by(
            student_id=identity['id'],
            coupon_id=coupon_id,
            is_used=False
        ).join(Coupon).filter(
            Coupon.start_time <= current_time,
            Coupon.end_time >= current_time
        ).first()
        
        if not user_coupon:
            return jsonify({'code': 400, 'msg': '优惠券无效或已使用'}), 400
        
        valid_coupon = user_coupon.coupon
    
    try:
        # 创建订单
        order = create_order(
            student_id=identity['id'],
            merchant_id=merchant_id,
            address=address,
            pay_type=pay_type,
            remark=remark,
            coupon=valid_coupon
        )
        
        # 注意：create_order函数中已经处理了购物车清空逻辑
        
        # 使用优惠券后更新状态
        if valid_coupon and user_coupon:
            user_coupon.is_used = True
            user_coupon.use_time = datetime.now()
            valid_coupon.used += 1
            db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '订单创建成功',
            'data': {
                'order_id': order.id,
                'order_no': order.order_no,
                'pay_amount': order.pay_amount,
                'total_amount': order.total_amount,
                'discount_amount': order.discount_amount
            }
        })
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'创建订单失败：{str(e)}'}), 500

# 获取投诉列表
@student_bp.route('/complaints', methods=['GET'])
@api_login_required
def get_complaints():
    try:
        # 获取用户ID
        if 'student_id' in session:
            user_id = session['student_id']
        else:
            # 尝试从JWT中获取
            current_user = get_jwt_identity()
            if isinstance(current_user, str) and ':' in current_user:
                user_type, user_id = current_user.split(':')
                if user_type != 'student':
                    return jsonify({'code': 403, 'msg': '权限错误'}), 403
                user_id = int(user_id)
            else:
                return jsonify({'code': 401, 'msg': '用户身份验证失败'}), 401
        
        # 获取查询参数
        page = int(request.args.get('page', 1))
        status = request.args.get('status', 'all')
        page_size = 10
        
        # 构建查询
        query = Complaint.query.filter_by(student_id=user_id)
        
        # 根据状态筛选 - 注意：数据库中存储的是中文状态
        status_map = {
            'pending': '待处理',
            'processing': '处理中',
            'resolved': '已解决'
        }
        if status != 'all' and status in status_map:
            query = query.filter_by(status=status_map[status])
        
        # 分页查询
        total = query.count()
        complaints = query.order_by(Complaint.create_time.desc())\
                          .offset((page - 1) * page_size)\
                          .limit(page_size)\
                          .all()
        
        # 格式化数据 - 将中文状态映射回英文状态以便前端使用
        complaint_list = []
        reverse_status_map = {'待处理': 'pending', '处理中': 'processing', '已解决': 'resolved'}
        
        for complaint in complaints:
            # 确保create_time不为None
            create_time_str = ''
            if complaint.create_time:
                create_time_str = complaint.create_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 将中文状态转换为英文状态
            english_status = reverse_status_map.get(complaint.status, 'unknown')
            
            complaint_list.append({
                'id': complaint.id,
                'content': complaint.content or '',
                'order_id': complaint.order_id,  # 与模型字段名保持一致
                'created_at': create_time_str,
                'status': english_status,
                'response': complaint.handle_result or ''
            })
        
        return jsonify({
            'code': 200,
            'msg': '获取投诉列表成功',
            'data': {
                'items': complaint_list,
                'total': total,
                'page': page,
                'page_size': page_size
            }
        })
    except ValueError as ve:
        # 处理参数转换错误
        return jsonify({'code': 400, 'msg': f'参数错误：{str(ve)}'}), 400
    except Exception as e:
        # 添加更详细的错误日志信息
        print(f'获取投诉列表错误：{str(e)}')
        return jsonify({'code': 500, 'msg': f'获取投诉列表失败：服务器内部错误'}), 500

# 提交投诉
@student_bp.route('/complaints', methods=['POST'])
@api_login_required
def submit_complaint():
    try:
        # 获取用户ID
        if 'student_id' in session:
            user_id = session['student_id']
        else:
            # 尝试从JWT中获取
            current_user = get_jwt_identity()
            if isinstance(current_user, str) and ':' in current_user:
                user_type, user_id = current_user.split(':')
                if user_type != 'student':
                    return jsonify({'code': 403, 'msg': '权限错误'}), 403
                user_id = int(user_id)
            else:
                return jsonify({'code': 401, 'msg': '用户身份验证失败'}), 401
        
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
            
        content = data.get('content', '').strip()
        order_id = data.get('order_id')  # 前端使用order_id参数名，后端保持一致
        print(f'提交投诉 - 内容长度: {len(content)}, 订单ID: {order_id}')
        
        # 验证数据
        if not content:
            return jsonify({'code': 400, 'msg': '投诉内容不能为空'}), 400
        
        if len(content) < 10:
            return jsonify({'code': 400, 'msg': '投诉内容至少需要10个字符'}), 400
        
        # 确保order_id为整数或None
        if order_id and not isinstance(order_id, int):
            try:
                order_id = int(order_id)
            except ValueError:
                return jsonify({'code': 400, 'msg': '无效的订单ID'}), 400
        
        # 创建投诉记录
        complaint = Complaint(
            student_id=user_id,
            order_id=order_id,
            content=content,
            status='待处理'
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '投诉提交成功'
        })
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': f'参数错误：{str(ve)}'}), 400
    except Exception as e:
        db.session.rollback()
        print(f'提交投诉错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '提交投诉失败：服务器内部错误'}), 500

# 删除投诉
@student_bp.route('/complaints/<int:complaint_id>', methods=['DELETE'])
@api_login_required
def delete_complaint(complaint_id):
    try:
        # 获取用户ID
        if 'student_id' in session:
            user_id = session['student_id']
        else:
            # 尝试从JWT中获取
            current_user = get_jwt_identity()
            if isinstance(current_user, str) and ':' in current_user:
                user_type, user_id = current_user.split(':')
                if user_type != 'student':
                    return jsonify({'code': 403, 'msg': '权限错误'}), 403
                user_id = int(user_id)
            else:
                return jsonify({'code': 401, 'msg': '用户身份验证失败'}), 401
        
        # 查找投诉记录
        complaint = Complaint.query.filter_by(
            id=complaint_id,
            student_id=user_id
        ).first()
        
        if not complaint:
            return jsonify({'code': 404, 'msg': '投诉记录不存在'}), 404
        
        # 只有待处理状态的投诉才能删除
        if complaint.status != '待处理':
            return jsonify({'code': 400, 'msg': '只有待处理的投诉才能删除'}), 400
        
        # 删除投诉记录
        db.session.delete(complaint)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '投诉删除成功'
        })
    except ValueError as ve:
        db.session.rollback()
        return jsonify({'code': 400, 'msg': f'参数错误：{str(ve)}'}), 400
    except Exception as e:
        db.session.rollback()
        print(f'删除投诉错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '删除投诉失败：服务器内部错误'}), 500