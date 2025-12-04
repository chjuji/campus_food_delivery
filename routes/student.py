from flask import Blueprint, request, jsonify, session, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.student import Student
from models.merchant import Merchant
from models.cart import Cart
from models.dish import Dish
from models.coupon import Coupon, UserCoupon
from models.order import Order, OrderItem
from models.complaint import Complaint
from models.address import Address
from models.admin import Admin
import re
from datetime import datetime
from services.auth_service import student_register, student_login
from services.order_service import create_order
from utils.validator import validate_student_register
from utils.file_utils import save_file, allowed_file
from extensions import db
import bcrypt
import os

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

# 辅助函数：验证支付密码是否为6位数字
def validate_pay_password(pay_password):
    return bool(re.match(r'^\d{6}$', pay_password))

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
    if phone and Student.query.filter_by(phone=phone).first():
        return jsonify({'code': 400, 'msg': '手机号已注册'})
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
            'register_time': student.create_time.strftime('%Y-%m-%d %H:%M'),
            'gender': student.gender,
            'wallet': float(student.wallet) if student.wallet else 0.00
        }
    })

# 更新个人信息 - POST方法
@student_bp.post('/profile/update')
@api_login_required
def update_profile():
    # 复用PUT方法的实现
    return update_profile_put()

# 修改密码API端点 - PUT方法（与前端请求兼容）
@student_bp.put('/change-password')
@api_login_required
def change_password_put():
    # 复用POST方法的逻辑
    return change_password_impl()

# 修改密码API端点 - POST方法
@student_bp.post('/change-password')
@api_login_required
def change_password():
    # 复用核心实现逻辑
    return change_password_impl()

# 修改密码核心实现函数
@api_login_required
def change_password_impl():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        # 获取密码数据
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        # 验证必填字段
        if not current_password or not new_password:
            return jsonify({'code': 400, 'msg': '请输入当前密码和新密码'}), 400
        
        # 验证当前密码是否正确
        if not bcrypt.checkpw(current_password.encode('utf-8'), student.password.encode('utf-8')):
            return jsonify({'code': 400, 'msg': '当前密码错误'}), 400
        
        # 验证新密码长度
        if len(new_password) < 8:
            return jsonify({'code': 400, 'msg': '新密码长度不能少于8位'}), 400
        
        # 更新密码
        hashed_pwd = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        student.password = hashed_pwd.decode('utf-8')
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '密码修改成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'修改密码错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '修改密码失败：服务器内部错误'}), 500

# 上传头像
@student_bp.post('/avatar')
@api_login_required
def upload_avatar():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        # 检查是否有文件上传
        if 'avatar' not in request.files:
            return jsonify({'code': 400, 'msg': '没有选择文件'}), 400
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'code': 400, 'msg': '没有选择文件'}), 400
        
        # 确保上传目录存在
        from config import Config
        avatar_folder = Config.UPLOAD_FOLDER.get('avatar')
        if not os.path.exists(avatar_folder):
            os.makedirs(avatar_folder)

        # 删除原头像文件
        original_avatar = student.avatar
        if original_avatar:
            original_avatar_path = os.path.join(avatar_folder, original_avatar)
            if os.path.exists(original_avatar_path):
                try:
                    os.remove(original_avatar_path)
                except Exception as e:
                    print(f'删除原头像失败: {str(e)}')

        # 保存文件
        try:
            file_path = save_file(file, 'avatar')
            # 更新学生头像路径
            student.avatar = file_path.split('/')[-1]  # 只保存文件名
            db.session.commit()
            return jsonify({'code': 200, 'msg': '头像上传成功'})
        except ValueError as e:
            return jsonify({'code': 400, 'msg': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        print(f'头像上传错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '头像上传失败：服务器内部错误'}), 500

# 更新个人信息 - PUT方法（支持前端使用PUT请求）
@student_bp.put('/profile')
@api_login_required
def update_profile_put():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        # 更新用户信息
        if 'name' in data:
            student.name = data['name'].strip()
        if 'phone' in data:
            student.phone = data['phone'].strip()
        if 'gender' in data:
            student.gender = data['gender']
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '个人信息更新成功',
            'data': {
                'student_id': student.student_id,
                'name': student.name,
                'phone': student.phone,
                'gender': student.gender
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f'更新个人信息错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '更新个人信息失败：服务器内部错误'}), 500

# 获取地址列表
@student_bp.get('/addresses')
@api_login_required
def get_addresses():
    try:
        user_id = session['student_id']
        addresses = Address.query.filter_by(student_id=user_id).order_by(Address.is_default.desc(), Address.create_time.desc()).all()
        
        address_list = []
        for addr in addresses:
            address_list.append({
                'id': addr.id,
                'recipient': addr.recipient,
                'phone': addr.phone,
                'province': addr.province,
                'city': addr.city,
                'district': addr.district,
                'detail_address': addr.detail_address,
                'is_default': addr.is_default,
                'full_address': f'{addr.province}{addr.city}{addr.district}{addr.detail_address}'
            })
        
        return jsonify({
            'code': 200,
            'data': address_list
        })
    except Exception as e:
        print(f'获取地址列表错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '获取地址列表失败：服务器内部错误'}), 500

# 添加地址
@student_bp.post('/addresses')
@api_login_required
def add_address():
    try:
        user_id = session['student_id']
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['recipient', 'phone', 'province', 'city', 'district', 'detail_address']
        field_names = {
            'recipient': '收货人姓名',
            'phone': '联系电话',
            'province': '省份',
            'city': '城市',
            'district': '区县',
            'detail_address': '详细地址'
        }
        
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({'code': 400, 'msg': f'{field_names[field]}不能为空'}), 400
        
        # 验证电话号码格式
        if not re.match(r'^1[3-9]\d{9}$', data['phone'].strip()):
            return jsonify({'code': 400, 'msg': '请输入正确的11位手机号码'}), 400
        
        # 验证姓名长度
        if len(data['recipient'].strip()) > 50:
            return jsonify({'code': 400, 'msg': '收货人姓名不能超过50个字符'}), 400
        
        # 验证地址字段长度
        max_lengths = {
            'province': 50,
            'city': 50,
            'district': 50,
            'detail_address': 200
        }
        
        for field, max_len in max_lengths.items():
            if len(data[field].strip()) > max_len:
                return jsonify({'code': 400, 'msg': f'{field_names[field]}不能超过{max_len}个字符'}), 400
        
        # 如果设置为默认地址，先将其他地址设为非默认
        if data.get('is_default', False):
            Address.query.filter_by(student_id=user_id).update({'is_default': False})
        
        # 创建地址
        address = Address(
            student_id=user_id,
            recipient=data['recipient'].strip(),
            phone=data['phone'].strip(),
            province=data['province'].strip(),
            city=data['city'].strip(),
            district=data['district'].strip(),
            detail_address=data['detail_address'].strip(),
            is_default=data.get('is_default', False)
        )
        
        db.session.add(address)
        db.session.commit()
        
        # 构建完整地址信息
        full_address = f'{address.province}{address.city}{address.district}{address.detail_address}'
        
        return jsonify({
            'code': 200,
            'msg': '地址添加成功',
            'data': {
                'id': address.id,
                'recipient': address.recipient,
                'phone': address.phone,
                'province': address.province,
                'city': address.city,
                'district': address.district,
                'detail_address': address.detail_address,
                'is_default': address.is_default,
                'full_address': full_address,
                'create_time': address.create_time.strftime('%Y-%m-%d %H:%M:%S') if address.create_time else None
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f'添加地址错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '添加地址失败：服务器内部错误'}), 500

# 检查支付密码状态
@student_bp.get('/check-pay-password')
@api_login_required
def check_pay_password_status():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        has_pay_password = student.pay_password is not None
        
        return jsonify({
            'code': 200,
            'data': {
                'has_pay_password': has_pay_password
            }
        })
    except Exception as e:
        print(f'检查支付密码状态错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '检查支付密码状态失败：服务器内部错误'}), 500

# 设置初始支付密码
@student_bp.post('/set-pay-password')
@api_login_required
def set_pay_password():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        # 检查是否已经设置了支付密码
        if student.pay_password:
            return jsonify({'code': 400, 'msg': '支付密码已设置，请直接修改'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        pay_password = data.get('pay_password')
        login_password = data.get('login_password')
        
        # 验证输入
        if not pay_password or not login_password:
            return jsonify({'code': 400, 'msg': '请输入支付密码和登录密码'}), 400
        
        # 验证支付密码格式
        if not validate_pay_password(pay_password):
            return jsonify({'code': 400, 'msg': '支付密码必须为6位数字'}), 400
        
        # 验证登录密码
        if not bcrypt.checkpw(login_password.encode('utf-8'), student.password.encode('utf-8')):
            return jsonify({
                'code': 400, 
                'msg': '登录密码错误',
                'data': {'error_type': 'login_password'}
            }), 400
        
        # 加密支付密码并保存
        hashed_pay_password = bcrypt.hashpw(pay_password.encode('utf-8'), bcrypt.gensalt())
        student.pay_password = hashed_pay_password.decode('utf-8')
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '支付密码设置成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'设置支付密码错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '设置支付密码失败：服务器内部错误'}), 500

# 修改支付密码
@student_bp.post('/change-pay-password')
@api_login_required
def change_pay_password():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        # 检查是否已设置支付密码
        if not student.pay_password:
            return jsonify({'code': 400, 'msg': '请先设置支付密码'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        old_pay_password = data.get('old_pay_password')
        new_pay_password = data.get('new_pay_password')
        
        # 验证输入
        if not old_pay_password or not new_pay_password:
            return jsonify({'code': 400, 'msg': '请输入原支付密码和新支付密码'}), 400
        
        # 验证原支付密码
        if not bcrypt.checkpw(old_pay_password.encode('utf-8'), student.pay_password.encode('utf-8')):
            return jsonify({
                'code': 400,
                'msg': '原支付密码错误',
                'data': {'error_type': 'old_pay_password'}
            }), 400
        
        # 验证新支付密码格式
        if not validate_pay_password(new_pay_password):
            return jsonify({'code': 400, 'msg': '新支付密码必须为6位数字'}), 400
        
        # 加密并更新支付密码
        hashed_pay_password = bcrypt.hashpw(new_pay_password.encode('utf-8'), bcrypt.gensalt())
        student.pay_password = hashed_pay_password.decode('utf-8')
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '支付密码修改成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'修改支付密码错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '修改支付密码失败：服务器内部错误'}), 500

# 钱包充值
@student_bp.post('/wallet/recharge')
@api_login_required
def wallet_recharge():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        # 获取充值金额
        recharge_amount = data.get('amount')
        if recharge_amount is None:
            return jsonify({'code': 400, 'msg': '请输入有效的充值金额'}), 400
        
        # 验证充值金额上限
        if recharge_amount > 10000:
            return jsonify({'code': 400, 'msg': '单次充值金额不能超过10000元'}), 400
        
        # 更新钱包余额
        student.wallet = float(student.wallet) + recharge_amount
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '充值成功',
            'data': {
                'new_balance': float(student.wallet)
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f'钱包充值错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '充值失败：服务器内部错误'}), 500

# 钱包支付验证
@student_bp.post('/wallet/pay')
@api_login_required
def wallet_pay():
    try:
        user_id = session['student_id']
        student = Student.query.get(user_id)
        if not student:
            return jsonify({'code': 404, 'msg': '用户不存在'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '请求数据不能为空'}), 400
        
        # 获取支付密码和金额
        password = data.get('password')
        amount = data.get('amount')
        
        if not password or amount is None:
            return jsonify({'code': 400, 'msg': '请输入支付密码和金额'}), 400
        
        # 验证支付密码格式（6位数字）
        if not validate_pay_password(password):
            return jsonify({'code': 400, 'msg': '支付密码必须为6位数字'}), 400
        
        # 验证支付密码
        if not bcrypt.checkpw(password.encode('utf-8'), student.pay_password.encode('utf-8')):
            return jsonify({'code': 400, 'msg': '支付密码错误'}), 400
        
        # 检查钱包余额
        if float(student.wallet) < amount:
            return jsonify({'code': 400, 'msg': '钱包余额不足'}), 400
        
        # 扣除钱包金额
        student.wallet = float(student.wallet) - amount
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '支付成功',
            'data': {
                'new_balance': float(student.wallet)
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f'钱包支付错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '支付失败：服务器内部错误'}), 500

# 获取配送费
@student_bp.route('/delivery-fee', methods=['GET'])
def get_delivery_fee():
    """获取配送费"""
    try:
        # 从Admin表获取配送费
        admin_config = Admin.get_config()
        delivery_fee = float(admin_config.delivery_fee)
        return jsonify({'code': 200, 'data': {'delivery_fee': delivery_fee}})
    except Exception as e:
        print(f'获取配送费错误：{str(e)}')
        # 如果出错，返回默认配送费5元
        return jsonify({'code': 200, 'data': {'delivery_fee': 5.0}})

# 更新地址
@student_bp.put('/addresses/<int:address_id>')
@api_login_required
def update_address(address_id):
    try:
        user_id = session['student_id']
        address = Address.query.filter_by(id=address_id, student_id=user_id).first()
        
        if not address:
            return jsonify({'code': 404, 'msg': '地址不存在'}), 404
        
        data = request.get_json()
        
        # 如果设置为默认地址，先将其他地址设为非默认
        if data.get('is_default', False):
            Address.query.filter_by(student_id=user_id).update({'is_default': False})
        
        # 更新地址信息
        if 'recipient' in data:
            address.recipient = data['recipient'].strip()
        if 'phone' in data:
            address.phone = data['phone'].strip()
        if 'province' in data:
            address.province = data['province'].strip()
        if 'city' in data:
            address.city = data['city'].strip()
        if 'district' in data:
            address.district = data['district'].strip()
        if 'detail_address' in data:
            address.detail_address = data['detail_address'].strip()
        if 'is_default' in data:
            address.is_default = data['is_default']
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '地址更新成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'更新地址错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '更新地址失败：服务器内部错误'}), 500

# 删除地址
@student_bp.delete('/addresses/<int:address_id>')
@api_login_required
def delete_address(address_id):
    try:
        user_id = session['student_id']
        address = Address.query.filter_by(id=address_id, student_id=user_id).first()
        
        if not address:
            return jsonify({'code': 404, 'msg': '地址不存在'}), 404
        
        db.session.delete(address)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '地址删除成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'删除地址错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '删除地址失败：服务器内部错误'}), 500

# 设置默认地址
@student_bp.post('/addresses/<int:address_id>/default')
@api_login_required
def set_default_address(address_id):
    try:
        user_id = session['student_id']
        address = Address.query.filter_by(id=address_id, student_id=user_id).first()
        
        if not address:
            return jsonify({'code': 404, 'msg': '地址不存在'}), 404
        
        # 将所有地址设为非默认
        Address.query.filter_by(student_id=user_id).update({'is_default': False})
        # 设置当前地址为默认
        address.is_default = True
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '设置默认地址成功'
        })
    except Exception as e:
        db.session.rollback()
        print(f'设置默认地址错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '设置默认地址失败：服务器内部错误'}), 500

# 添加购物车
@student_bp.route('/cart/add', methods=['POST'])
@api_login_required
def add_to_cart():
    try:
        # 从session中获取学生ID（api_login_required装饰器已经验证并设置了session['student_id']）
        if 'student_id' not in session:
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        
        student_id = session['student_id']
        
        # 获取和验证请求数据
        data = request.json or {}
        dish_id = data.get('dish_id')
        quantity = data.get('quantity', 1)
        
        # 验证菜品ID
        if not dish_id:
            return jsonify({'code': 400, 'msg': '缺少菜品ID'}), 400
            
        try:
            dish_id = int(dish_id)
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'msg': '菜品ID格式错误'}), 400
        
        # 验证数量
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return jsonify({'code': 400, 'msg': '数量必须大于0'}), 400
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'msg': '数量格式错误'}), 400
        
        # 使用数据库事务
        try:
            # 检查菜品是否存在
            dish = Dish.query.get(dish_id)
            if not dish:
                return jsonify({'code': 404, 'msg': '菜品不存在'}), 404
            
            # 检查菜品是否上架
            if not dish.is_shelf:
                return jsonify({'code': 400, 'msg': '该菜品已下架'}), 400
            
            # 检查购物车中是否已有该菜品
            cart_item = Cart.query.filter_by(
                student_id=student_id,
                dish_id=dish_id
            ).first()
            
            if cart_item:
                # 更新数量
                cart_item.quantity += quantity
            else:
                # 创建新的购物车项
                cart_item = Cart(
                    student_id=student_id,
                    dish_id=dish_id,
                    quantity=quantity
                )
                db.session.add(cart_item)
            
            # 提交事务
            db.session.commit()
            
            return jsonify({
                'code': 200,
                'msg': '添加购物车成功',
                'data': {
                    'dish_id': dish_id,
                    'quantity': cart_item.quantity
                }
            })
        except Exception as db_error:
            db.session.rollback()
            # 记录详细错误信息但返回通用错误给用户
            print(f"数据库错误: {str(db_error)}")
            return jsonify({
                'code': 500,
                'msg': '添加购物车失败：数据库操作异常'
            }), 500
    except Exception as e:
        # 捕获所有其他异常
        print(f"添加购物车异常: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': '添加购物车失败：服务器内部错误'
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
            'data': {'items': cart_data}
        })
    except Exception as e:
        # 添加更详细的错误日志记录
        print(f"购物车API错误详情: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': f'获取购物车失败：{str(e)}'
        }), 500

@student_bp.route('/cart/<int:dish_id>', methods=['PUT'])
@api_login_required
def update_cart_item(dish_id):
    try:
        # 从session中获取学生ID（api_login_required装饰器已经验证并设置了session['student_id']）
        if 'student_id' not in session:
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        
        student_id = session['student_id']
        
        data = request.json
        quantity = data.get('quantity', 1)
        
        cart_item = Cart.query.filter_by(dish_id=dish_id, student_id=student_id).first()
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

@student_bp.route('/cart/<int:dish_id>', methods=['DELETE'])
@api_login_required
def delete_cart_item(dish_id):
    try:
        # 从session中获取学生ID（api_login_required装饰器已经验证并设置了session['student_id']）
        if 'student_id' not in session:
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        
        student_id = session['student_id']
        
        cart_item = Cart.query.filter_by(dish_id=dish_id, student_id=student_id).first()
        
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
        # 从session中获取学生ID（api_login_required装饰器已经验证并设置了session['student_id']）
        if 'student_id' not in session:
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        
        student_id = session['student_id']
        
        cart_items = Cart.query.filter_by(student_id=student_id).all()
        
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
@student_bp.get('/orders/<int:order_id>')
@api_login_required
def get_student_order_detail(order_id):
    try:
        # 获取当前登录学生ID
        student_id = session.get('student_id')
        if not student_id:
            return jsonify({'code': 401, 'msg': '未登录或会话已过期'}), 401
        
        # 查找订单
        order = Order.query.filter_by(id=order_id, student_id=student_id).options(
            db.joinedload(Order.merchant),
            db.joinedload(Order.order_items).joinedload(OrderItem.dish)
        ).first()
        
        if not order:
            return jsonify({'code': 404, 'msg': '订单不存在'}), 404
        
        # 从Admin表获取配送费
        admin_config = Admin.get_config()
        delivery_fee = float(admin_config.delivery_fee)
        
        # 构建响应数据
        order_data = {
            'order_id': order.id,
            'order_no': order.order_no,
            'status': order.status,
            'created_at': order.create_time.isoformat() if order.create_time else None,
            'pay_time': order.pay_time.isoformat() if order.pay_time else None,
            'finish_time': order.finish_time.isoformat() if order.finish_time else None,
            'total_amount': order.total_amount,
            'pay_amount': order.pay_amount,
            'discount_amount': order.discount_amount,
            'address': order.address,
            'remark': order.remark,
            'delivery_fee': delivery_fee,  # 从Admin表获取配送费
            'merchant': {
                'name': order.merchant.merchant_name if order.merchant else '未知商户'
            },
            'items': []
        }
        
        # 构建订单项
        for item in order.order_items:
            item_data = {
                'dish_name': item.dish.dish_name if item.dish else '未知菜品',
                'price': item.price,
                'quantity': item.quantity
            }
            order_data['items'].append(item_data)
        
        return jsonify({
            'code': 200,
            'msg': '获取订单详情成功',
            'data': order_data
        })
    except Exception as e:
        print(f"订单详情API错误：{str(e)}")
        return jsonify({'code': 500, 'msg': f'获取订单详情失败：{str(e)}'}), 500

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
        
        # 构建查询，关联查询商户信息
        query = Order.query.filter_by(student_id=student_id).options(
            db.joinedload(Order.merchant)
        )
        
            # 根据状态筛选
        if status != 'all':
            # 状态值映射，将前端英文状态转换为数据库中文状态
            status_map = {
                'pending': '待支付',
                'preparing': '待接单',
                'delivering': '待配送', # 数据库中存的是待配送
                'delivered': '已送达',
                'cancelled': '已取消'
            }
            # 使用映射后的状态值，如果没有映射则使用原始值
            db_status = status_map.get(status, status)
            query = query.filter_by(status=db_status)
        
        # 按创建时间倒序排序
        query = query.order_by(Order.create_time.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)
        
        # 从Admin表获取配送费（只获取一次，提高性能）
        admin_config = Admin.get_config()
        delivery_fee = float(admin_config.delivery_fee)
        
        # 构建响应数据
        orders_data = []
        for order in pagination.items:
            # 构建符合前端期望的订单数据结构
            order_data = {
                'order_id': order.id,  # 前端期望的字段名
                'order_no': order.order_no,
                'status': order.status,
                'created_at': order.create_time.isoformat() if order.create_time else None,
                'pay_time': order.pay_time.isoformat() if order.pay_time else None,
                'finish_time': order.finish_time.isoformat() if order.finish_time else None,
                'total_amount': order.total_amount,
                'pay_amount': order.pay_amount,
                'discount_amount': order.discount_amount,
                'address': order.address,
                'remark': order.remark,
                'delivery_fee': delivery_fee,  # 从Admin表获取配送费
                'merchant': {
                    'name': order.merchant.merchant_name if order.merchant else '未知商户'
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
    address_id = data.get('address_id')
    coupon_id = data.get('coupon_id')
    remark = data.get('remark', '')
    cart_item_ids = data.get('cart_item_ids', [])
    status = data.get('status', '待支付')
    
    # 验证必填参数
    if not merchant_id or not address_id:
        return jsonify({'code': 400, 'msg': '缺少商户ID或地址ID'}), 400
    
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
            address_id=address_id,
            remark=remark,
            coupon=valid_coupon,
            cart_item_ids=cart_item_ids,
            status=status
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

# 取消订单
@student_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@api_login_required
def cancel_order(order_id):
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
        
        # 查找订单
        order = Order.query.filter_by(id=order_id, student_id=user_id).first()
        if not order:
            return jsonify({'code': 404, 'msg': '订单不存在'}), 404
        
        # 如果订单状态是待接单，需要退款
        if order.status == '待接单':
            # 获取学生和商户信息
            student = Student.query.get(user_id)
            merchant = Merchant.query.get(order.merchant_id)
            
            if not student or not merchant:
                return jsonify({'code': 404, 'msg': '用户或商户不存在'}), 404
            
            # 获取订单支付金额并转换为Decimal类型
            from decimal import Decimal
            refund_amount = Decimal(str(order.pay_amount))
            
            # 从商户钱包扣除金额
            merchant.wallet -= refund_amount
            if merchant.wallet < 0:
                return jsonify({'code': 500, 'msg': '商户钱包余额不足，无法退款'}), 500
            
            # 将金额退还给学生
            student.wallet += refund_amount
        
        # 将订单状态改为已取消
        order.status = '已取消'
        db.session.commit()
        
        return jsonify({'code': 200, 'msg': '订单已取消'})
    except Exception as e:
        db.session.rollback()
        print(f'取消订单错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '取消订单失败：服务器内部错误'}), 500

# 删除订单
@student_bp.route('/orders/<int:order_id>/delete', methods=['DELETE'])
@api_login_required
def delete_order(order_id):
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
        
        # 查找订单
        order = Order.query.filter_by(id=order_id, student_id=user_id).first()
        if not order:
            return jsonify({'code': 404, 'msg': '订单不存在'}), 404
        
        # 删除关联的订单项
        OrderItem.query.filter_by(order_id=order_id).delete()
        
        # 删除订单
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({'code': 200, 'msg': '订单已删除'})
    except Exception as e:
        db.session.rollback()
        print(f'删除订单错误：{str(e)}')
        return jsonify({'code': 500, 'msg': '删除订单失败：服务器内部错误'}), 500

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

# 登出
@student_bp.post('/logout')
def logout():
    session.pop('student_id', None)
    return jsonify({'code': 200, 'msg': '登出成功'})


