from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.merchant import Merchant
from models.dish import Dish
from models.order import Order, OrderItem
from extensions import db, bcrypt
from sqlalchemy import func
from utils.file_utils import save_file
from services.auth_service import merchant_register, merchant_login
from utils.jwt_utils import generate_token
from datetime import datetime, timedelta
import os

merchant_bp = Blueprint('merchant', __name__)

# 检查商户是否已登录的装饰器（页面路由用）
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'merchant_id' not in session:
            return redirect(url_for('merchant.login_page'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# 检查商户是否已登录的装饰器（API路由用）
def api_login_required(f):
    def decorated_function(*args, **kwargs):
        try:
            # 首先检查session中是否有登录信息
            if 'merchant_id' in session:
                return f(*args, **kwargs)
            
            # 然后检查JWT token
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            
            if identity and ':' in identity:
                user_type, user_id = identity.split(':', 1)
                if user_type == 'merchant':
                    # 将merchant_id添加到session中以便后续使用
                    session['merchant_id'] = int(user_id)
                    return f(*args, **kwargs)
        except Exception as e:
            # 记录异常但不暴露具体错误信息
            print(f"JWT验证错误: {str(e)}")
        
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    decorated_function.__name__ = f.__name__
    return decorated_function

def calculate_merchant_status(merchant):
    """根据当前时间和营业时间计算商户的营业状态"""
    if not merchant or not merchant.business_hours:
        print(f"商户信息不完整或无营业时间设置，ID: {merchant.id if merchant else None}")
        return True  # 默认营业中
    
    try:
        # 解析营业时间
        if '-' in merchant.business_hours:
            open_time_str, close_time_str = merchant.business_hours.split('-')
            
            # 验证时间格式
            if ':' not in open_time_str or ':' not in close_time_str:
                raise ValueError("时间格式不正确，应为HH:MM")
                
            # 获取当前时间
            now = datetime.now()
            
            # 解析开始和结束时间
            open_hour, open_minute = map(int, open_time_str.split(':'))
            close_hour, close_minute = map(int, close_time_str.split(':'))
            
            # 验证时间范围
            if not (0 <= open_hour <= 23) or not (0 <= open_minute <= 59) or \
               not (0 <= close_hour <= 23) or not (0 <= close_minute <= 59):
                raise ValueError("时间超出有效范围")
                
            # 创建今天的营业时间对象
            open_time = datetime(now.year, now.month, now.day, open_hour, open_minute)
            close_time = datetime(now.year, now.month, now.day, close_hour, close_minute)
            
            # 处理跨天情况
            if close_time < open_time:
                if now >= open_time or now <= close_time:
                    return True
                else:
                    return False
            else:
                if open_time <= now <= close_time:
                    return True
                else:
                    return False
        else:
            raise ValueError("营业时间格式不正确，应为开始时间-结束时间")
    except Exception as e:
        print(f"计算营业状态时出错: {str(e)}")
        return True  # 出错时默认营业中

# 获取当前登录商户信息
def get_current_merchant():
    """获取当前登录的商户，并自动更新其营业状态"""
    merchant = None
    if 'merchant_id' in session:
        merchant = Merchant.query.get(session['merchant_id'])
    else:
        try:
            # 尝试从JWT token获取商户ID
            from flask_jwt_extended import get_jwt_identity
            identity = get_jwt_identity()
            if identity and isinstance(identity, str) and ':' in identity:
                user_type, user_id = identity.split(':', 1)
                if user_type == 'merchant':
                    merchant = Merchant.query.get(int(user_id))
        except Exception:
            # JWT获取失败时不影响正常流程
            pass
    
    # 自动更新营业状态
    if merchant:
        new_status = calculate_merchant_status(merchant)
        # 只有状态发生变化时才更新数据库，减少不必要的数据库操作
        if merchant.is_open != new_status:
            merchant.is_open = new_status
            try:
                db.session.commit()
                print(f"自动更新商户{merchant.merchant_name}的营业状态为: {new_status}")
            except Exception as e:
                print(f"更新营业状态到数据库失败: {str(e)}")
                db.session.rollback()
    
    return merchant

# 页面路由
@merchant_bp.route('/login', methods=['GET'])
def login_page():
    return render_template('merchant/login.html')

@merchant_bp.route('/register', methods=['GET'])
def register_page():
    return render_template('merchant/register.html')

@merchant_bp.route('/index', methods=['GET'])
@login_required
def merchant_index():
    merchant = get_current_merchant()
    if not merchant:
        return redirect(url_for('merchant.login_page'))
    return render_template('merchant/index.html', merchant_info=merchant)

@merchant_bp.route('/orders', methods=['GET'])
@login_required
def merchant_orders():
    merchant = get_current_merchant()
    if not merchant:
        return redirect(url_for('merchant.login_page'))
    return render_template('merchant/orders.html', merchant_info=merchant)

@merchant_bp.route('/statistics', methods=['GET'])
@login_required
def merchant_statistics():
    merchant = get_current_merchant()
    if not merchant:
        return redirect(url_for('merchant.login_page'))
    return render_template('merchant/statistics.html', merchant_info=merchant)

@merchant_bp.route('/settings', methods=['GET'])
@login_required
def merchant_settings():
    merchant = get_current_merchant()
    if not merchant:
        return redirect(url_for('merchant.login_page'))
    return render_template('merchant/settings.html', merchant_info=merchant)

# 注意：此函数在app.py中通过merchant_profile_page路由直接调用
# 不再需要独立的路由装饰器，避免与API路由冲突
@login_required
def merchant_profile():
    merchant = get_current_merchant()
    if not merchant:
        return redirect(url_for('merchant.login_page'))
    
    # 获取该商户的所有菜品
    dishes = Dish.query.filter_by(merchant_id=merchant.id).all()
    
    return render_template('merchant/profile.html', merchant_info=merchant, dishes=dishes)

# API 路由 - 原始功能保留
# 商户注册
@merchant_bp.post('/register')
def register():
    # 从表单中获取字段（支持 multipart/form-data 上传）
    form = request.form
    files = request.files

    # 简单校验（表单字段）
    required = ['merchant_name', 'contact_name', 'contact_phone', 'password', 'address']
    for key in required:
        if not form.get(key):
            return jsonify({'code': 400, 'msg': f'{key} 为必填项'}), 400

    # 处理文件上传（可选）
    license_path = ''
    logo_path = ''  # 设置默认值，避免未初始化就使用
    food_license_path = ''
    if 'license_img' in files and files['license_img'].filename:
        try:
            license_path = save_file(files['license_img'], 'merchant')
        except Exception as e:
            return jsonify({'code': 400, 'msg': f'营业执照上传失败：{str(e)}'}), 400
    if 'logo' in files and files['logo'].filename:
        try:
            logo_path = save_file(files['logo'], 'merchant')
        except Exception as e:
            return jsonify({'code': 400, 'msg': f'Logo上传失败：{str(e)}'}), 400

    # 组装数据传给服务层
    data = {
        'merchant_name': form.get('merchant_name'),
        'contact_name': form.get('contact_name'),
        'contact_phone': form.get('contact_phone'),
        'password': form.get('password'),
        'address': form.get('address'),
        'license_img': license_path,
        'logo': logo_path
    }

    result = merchant_register(data)
    if isinstance(result, dict) and result.get('error'):
        # 对于错误响应，使用200状态码但包含错误信息，避免前端将其视为网络错误
        # 保持错误消息清晰，特别是手机号已注册的情况
        return jsonify({'code': 400, 'msg': result.get('error')}), 200

    return jsonify({'code': 200, 'msg': '注册成功', 'data': {'id': result.id, 'name': result.merchant_name}})


# 商户登录 - 同时支持两种登录方式
@merchant_bp.post('/login-alt')
def api_login():
    data = request.get_json()
    phone = data.get('contact_phone') or data.get('phone')
    password = data.get('password')
    if not phone or not password:
        return jsonify({'code': 400, 'msg': '请输入手机号和密码'}), 400

    result = merchant_login(phone, password)
    if not result or isinstance(result, dict) and result.get('error'):
        msg = result.get('error') if isinstance(result, dict) else '账号或密码错误'
        return jsonify({'code': 401, 'msg': msg}), 401
    
    # 登录成功后设置session，这样get_current_merchant才能正常工作
    merchant = Merchant.query.filter_by(contact_phone=phone).first()
    if merchant:
        session['merchant_id'] = merchant.id
        
        # 根据当前时间和营业时间设置is_open值
        if merchant.business_hours:
            try:
                # 解析营业时间，格式：09:00-22:00
                open_time_str, close_time_str = merchant.business_hours.split('-')
                # 获取当前时间
                now = datetime.now()
                # 解析开始和结束时间
                open_hour, open_minute = map(int, open_time_str.split(':'))
                close_hour, close_minute = map(int, close_time_str.split(':'))
                # 创建今天的营业时间对象
                open_time = datetime(now.year, now.month, now.day, open_hour, open_minute)
                close_time = datetime(now.year, now.month, now.day, close_hour, close_minute)
                # 判断当前时间是否在营业时间内
                if open_time <= now <= close_time:
                    merchant.is_open = True
                else:
                    merchant.is_open = False
                # 保存到数据库
                db.session.commit()
                # 更新返回结果中的is_open状态
                if isinstance(result, dict):
                    result['is_open'] = merchant.is_open
            except Exception as e:
                # 如果解析失败，保持原有状态
                print(f"解析营业时间失败: {str(e)}")
                db.session.rollback()

    return jsonify({'code': 200, 'msg': '登录成功', 'data': result})

# 网页版登录API
@merchant_bp.route('/login', methods=['POST'])
def merchant_web_login():
    data = request.get_json()
    contact_phone = data.get('contact_phone')  # 使用contact_phone作为登录凭证
    password = data.get('password')
    
    if not contact_phone or not password:
        return jsonify({'code': 400, 'msg': '请输入手机号和密码'})
    
    merchant = Merchant.query.filter_by(contact_phone=contact_phone).first()
    
    if merchant and bcrypt.check_password_hash(merchant.password, password):
        # 检查商户状态
        if merchant.status != 1:
            return jsonify({'code': 403, 'msg': '账号未审核通过或已下架'})
        
        # 根据当前时间和营业时间设置is_open值
        if merchant.business_hours:
            try:
                # 解析营业时间，格式：09:00-22:00
                open_time_str, close_time_str = merchant.business_hours.split('-')
                # 获取当前时间
                now = datetime.now()
                # 解析开始和结束时间
                open_hour, open_minute = map(int, open_time_str.split(':'))
                close_hour, close_minute = map(int, close_time_str.split(':'))
                # 创建今天的营业时间对象
                open_time = datetime(now.year, now.month, now.day, open_hour, open_minute)
                close_time = datetime(now.year, now.month, now.day, close_hour, close_minute)
                # 判断当前时间是否在营业时间内
                if open_time <= now <= close_time:
                    merchant.is_open = True
                else:
                    merchant.is_open = False
                # 保存到数据库
                db.session.commit()
            except Exception as e:
                # 如果解析失败，保持原有状态
                print(f"解析营业时间失败: {str(e)}")
                db.session.rollback()
            
        token = generate_token(merchant.id, 'merchant')
        session['merchant_id'] = merchant.id
        session['merchant_token'] = token
        return jsonify({
            'code': 200,
            'msg': '登录成功',
            'data': {
                'token': token,
                'user_info': {
                    'id': merchant.id,
                    'name': merchant.merchant_name,
                    'status': merchant.status,
                    'logo': merchant.logo,  # 添加logo字段
                    'is_open': merchant.is_open  # 返回当前营业状态
                }
            }
        })
    else:
        return jsonify({'code': 401, 'msg': '手机号或密码错误'})

# 网页版注册API
@merchant_bp.route('/register', methods=['POST'])
def merchant_web_register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    contact = data.get('contact')
    
    # 检查用户名是否已存在
    if Merchant.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})
    
    # 创建新商户
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_merchant = Merchant(
        username=username,
        password=hashed_password,
        name=name,
        contact=contact,
        status='active'
    )
    
    try:
        db.session.add(new_merchant)
        db.session.commit()
        return jsonify({'success': True, 'message': '注册成功，请登录'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '注册失败，请稍后重试'})

# 登出API
@merchant_bp.route('/logout', methods=['POST'])
def merchant_logout():
    session.pop('merchant_id', None)
    session.pop('merchant_token', None)
    return jsonify({'success': True, 'message': '登出成功'})

# 统计数据API
@merchant_bp.route('/statistics', methods=['GET'])
@api_login_required
def get_merchant_statistics():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    # 模拟统计数据
    statistics = {
        'today_orders': 0,
        'today_sales': 0,
        'total_orders': 0,
        'total_sales': 0,
        'active_dishes': 0,
        'pending_orders': 0
    }
    
    return jsonify({'success': True, 'data': statistics})

# 获取订单列表API
@merchant_bp.route('/orders', methods=['GET'])
@api_login_required
def get_merchant_orders():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    limit = request.args.get('limit', 10, type=int)
    sort = request.args.get('sort', 'latest')
    
    # 模拟订单数据
    orders = []
    
    return jsonify({'success': True, 'data': orders, 'total': 0})

# 菜品相关API
@merchant_bp.route('/dishes/popular', methods=['GET'])
@api_login_required
def get_popular_dishes():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    limit = request.args.get('limit', 10, type=int)
    
    # 模拟热门菜品数据
    dishes = []
    
    return jsonify({'success': True, 'data': dishes})

@merchant_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@api_login_required
def update_order_status(order_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    data = request.get_json()
    new_status = data.get('status')
    
    return jsonify({'success': True, 'message': '订单状态已更新'})

@merchant_bp.route('/dishes', methods=['GET'])
@api_login_required
def get_dishes():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    
    # 根据商户ID筛选菜品
    query = Dish.query.filter_by(merchant_id=merchant.id)
    
    # 获取总数
    total = query.count()
    
    # 分页查询
    paginated = query.paginate(page=page, per_page=page_size, error_out=False)
    
    # 构建菜品列表
    dish_list = []
    for dish in paginated.items:
        # 计算销量（简化版，实际应该从订单项目中统计）
        sales = db.session.query(func.count(OrderItem.id)).filter_by(dish_id=dish.id).scalar() or 0
        
        dish_list.append({
            'id': dish.id,
            'merchant_id': dish.merchant_id,
            'dish_name': dish.dish_name,
            'price': dish.price,
            'stock': dish.stock,
            'category': dish.category,
            'img_url': dish.img_url,
            'description': dish.description,
            'is_shelf': dish.is_shelf,
            'sales': sales,
            'create_time': dish.create_time.isoformat() if dish.create_time else None
        })
    
    return jsonify({
        'code': 200,
        'data': {
            'dishes': dish_list,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': paginated.pages
        }
    })

# 删除重复的路由定义，保留第526行的add_dish()函数

@merchant_bp.route('/dishes/<int:dish_id>', methods=['GET'])
@api_login_required
def get_dish_detail(dish_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    
    # 查询菜品是否存在且属于当前商户
    dish = Dish.query.filter_by(id=dish_id, merchant_id=merchant.id).first()
    
    if not dish:
        return jsonify({'code': 404, 'msg': '菜品不存在'}), 404
    
    # 返回菜品详情
    return jsonify({
        'code': 200,
        'data': {
            'id': dish.id,
            'dish_name': dish.dish_name,
            'price': dish.price,
            'stock': dish.stock,
            'category': dish.category,
            'img_url': dish.img_url,
            'description': dish.description,
            'is_shelf': dish.is_shelf
        }
    })

@merchant_bp.route('/dishes/<int:dish_id>', methods=['PUT'])
@api_login_required
def update_dish(dish_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    
    try:
        # 查询菜品是否存在且属于当前商户
        dish = Dish.query.filter_by(id=dish_id, merchant_id=merchant.id).first()
        
        if not dish:
            return jsonify({'code': 404, 'msg': '菜品不存在'}), 404
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': '无效的请求数据'}), 400
        
        # 更新菜品信息
        if 'dish_name' in data and data['dish_name']:
            dish.dish_name = data['dish_name'].strip()
        
        if 'price' in data:
            try:
                dish.price = float(data['price'])
            except (ValueError, TypeError):
                return jsonify({'code': 400, 'msg': '价格格式不正确'}), 400
        
        if 'stock' in data:
            try:
                dish.stock = int(data['stock'])
            except (ValueError, TypeError):
                return jsonify({'code': 400, 'msg': '库存格式不正确'}), 400
        
        if 'category' in data and data['category']:
            dish.category = data['category'].strip()
        
        if 'description' in data:
            dish.description = data['description'].strip()
        
        if 'is_shelf' in data:
            dish.is_shelf = bool(data['is_shelf'])
        
        # 提交到数据库
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '菜品更新成功',
            'data': {
                'id': dish.id,
                'dish_name': dish.dish_name,
                'price': dish.price,
                'stock': dish.stock,
                'category': dish.category,
                'img_url': dish.img_url,
                'description': dish.description,
                'is_shelf': dish.is_shelf
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'更新失败：{str(e)}'
        }), 500

@merchant_bp.route('/dishes/<int:dish_id>', methods=['DELETE'])
@api_login_required
def delete_dish_api(dish_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    # 模拟删除菜品
    return jsonify({'success': True, 'message': '菜品删除成功'})

# 个人资料API
@merchant_bp.route('/profile', methods=['GET'])
@api_login_required
def get_merchant_profile():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    return jsonify({
        'code': 200,
        'data': {
            'id': merchant.id,
            'merchant_name': merchant.merchant_name,
            'contact_name': merchant.contact_name,
            'contact_phone': merchant.contact_phone,
            'license_img': merchant.license_img,
            'logo': merchant.logo,
            'address': merchant.address,
            'status': merchant.status,
            'service_fee': merchant.service_fee,
            'create_time': merchant.create_time.isoformat() if merchant.create_time else None
        }
    })

@merchant_bp.route('/profile', methods=['PUT'])
@api_login_required
def update_merchant_profile():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的请求数据'}), 400
        
        # 更新个人信息字段
        if 'merchant_name' in data and data['merchant_name']:
            merchant.merchant_name = data['merchant_name'].strip()
        
        if 'contact_name' in data and data['contact_name']:
            merchant.contact_name = data['contact_name'].strip()
            
        if 'contact_phone' in data and data['contact_phone']:
            merchant.contact_phone = data['contact_phone'].strip()
            
        if 'address' in data and data['address']:
            merchant.address = data['address'].strip()
        
        # 提交到数据库
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '个人信息更新成功',
            'data': {
                'merchant_name': merchant.merchant_name,
                'contact_name': merchant.contact_name,
                'contact_phone': merchant.contact_phone,
                'address': merchant.address
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'更新失败：{str(e)}'
        }), 500

# 设置API - 修改路径避免冲突
@merchant_bp.route('/settings/data', methods=['GET'])
@api_login_required
def get_merchant_settings():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    # 获取并验证is_open字段
    raw_is_open = getattr(merchant, 'is_open', True)
    # 确保返回布尔类型，处理可能的非布尔值
    is_open_bool = bool(raw_is_open) if raw_is_open is not None else True
    
    settings_data = {
        'merchant_name': merchant.merchant_name,
        'description': getattr(merchant, 'description', ''),
        'contact_phone': merchant.contact_phone,
        'business_hours': getattr(merchant, 'business_hours', ''),
        'is_open': is_open_bool,  # 确保返回布尔类型
        'status': merchant.status,
        'logo': getattr(merchant, 'logo', '')  # 添加logo字段
    }
    
    print(f"获取商户设置 - ID: {merchant.id}, 名称: {merchant.merchant_name}, is_open: {is_open_bool}, 营业时间: {settings_data['business_hours']}")
    
    return jsonify({'success': True, 'data': settings_data})

# 更新设置API
@merchant_bp.route('/settings', methods=['PUT'])
@api_login_required
def update_merchant_settings():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        # 检查请求是否包含文件，使用form而不是json
        data = request.form
        
        # 更新设置字段
        if 'merchant_name' in data and data['merchant_name']:
            merchant.merchant_name = data['merchant_name'].strip()
        
        if 'description' in data:
            merchant.description = data['description'].strip()
            
        if 'contact_phone' in data and data['contact_phone']:
            merchant.contact_phone = data['contact_phone'].strip()
        
        # 处理Logo文件上传
        if 'logo' in request.files and request.files['logo']:
            try:
                from utils.file_utils import save_file
                logo_file = request.files['logo']
                logo_path = save_file(logo_file, 'merchant')
                merchant.logo = logo_path
                print(f'Logo保存成功: {logo_path}')
            except Exception as e:
                print(f'Logo保存失败: {str(e)}')
                # Logo保存失败不应影响其他设置的保存
                pass
            
        if 'business_hours' in data:
                merchant.business_hours = data['business_hours'].strip()
                print(f"更新营业时间: {merchant.business_hours}")
                # 当营业时间更新时，根据新的营业时间和当前时间重新计算is_open
                if merchant.business_hours:
                    try:
                        # 解析营业时间，格式：09:00-22:00
                        if '-' in merchant.business_hours:
                            open_time_str, close_time_str = merchant.business_hours.split('-')
                            
                            # 验证时间格式
                            if ':' not in open_time_str or ':' not in close_time_str:
                                raise ValueError("时间格式不正确，应为HH:MM")
                                
                            # 获取当前时间
                            now = datetime.now()
                            print(f"当前时间: {now}")
                            
                            # 解析开始和结束时间
                            open_hour, open_minute = map(int, open_time_str.split(':'))
                            close_hour, close_minute = map(int, close_time_str.split(':'))
                            
                            # 验证时间范围
                            if not (0 <= open_hour <= 23) or not (0 <= open_minute <= 59) or \
                               not (0 <= close_hour <= 23) or not (0 <= close_minute <= 59):
                                raise ValueError("时间超出有效范围")
                                
                            # 创建今天的营业时间对象
                            open_time = datetime(now.year, now.month, now.day, open_hour, open_minute)
                            close_time = datetime(now.year, now.month, now.day, close_hour, close_minute)
                            
                            # 处理跨天情况（例如：22:00-02:00）
                            if close_time < open_time:
                                # 如果结束时间早于开始时间，说明跨天
                                if now >= open_time or now <= close_time:
                                    merchant.is_open = True
                                else:
                                    merchant.is_open = False
                            else:
                                # 正常当天情况
                                if open_time <= now <= close_time:
                                    merchant.is_open = True
                                else:
                                    merchant.is_open = False
                                    
                            print(f"营业时间: {open_time_str} - {close_time_str}")
                            print(f"计算后is_open状态: {merchant.is_open}")
                        else:
                            raise ValueError("营业时间格式不正确，应为开始时间-结束时间")
                    except Exception as e:
                        # 如果解析失败，设置默认状态为营业中
                        print(f"解析营业时间失败: {str(e)}")
                        merchant.is_open = True  # 默认营业中
                        print(f"设置默认is_open状态为: {merchant.is_open}")
        
        # 移除手动设置is_open的逻辑，完全由系统根据营业时间自动管理
        # 不再接受前端传入的is_open参数，确保状态自动计算的准确性
        
        # 提交到数据库
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '设置更新成功',
            'data': {
                'merchant_name': merchant.merchant_name,
                'description': merchant.description,
                'contact_phone': merchant.contact_phone,
                'business_hours': merchant.business_hours,
                'is_open': merchant.is_open
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'更新失败：{str(e)}'
        }), 500

@merchant_bp.route('/set_password', methods=['PUT'])
@api_login_required
def update_merchant_password():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        # 获取请求数据
        data = request.get_json()
        current_password = data.get('currentPassword')
        new_password = data.get('newPassword')
        
        # 验证必要字段
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': '请提供当前密码和新密码'})
        
        # 验证当前密码是否正确
        if not bcrypt.check_password_hash(merchant.password, current_password):
            return jsonify({'success': False, 'message': '当前密码不正确'})
        
        # 检查新密码长度
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': '新密码长度不能少于6位'})
        
        # 使用bcrypt加密新密码
        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        # 更新数据库
        merchant.password = hashed_password
        db.session.commit()
        
        return jsonify({'success': True, 'message': '密码修改成功'})
    except Exception as e:
        # 发生异常时回滚
        db.session.rollback()
        return jsonify({'success': False, 'message': f'修改失败: {str(e)}'})

# 添加菜品
@merchant_bp.post('/dish/add')
@api_login_required
def add_dish():
    try:
        merchant = get_current_merchant()
        if not merchant:
            return jsonify({'code': 401, 'msg': '未登录'}), 401
        
        # 获取表单数据（支持文件上传）
        dish_name = request.form.get('dish_name')
        price = request.form.get('price')
        category = request.form.get('category')
        stock = request.form.get('stock', 0)
        description = request.form.get('description', '')
        is_shelf = request.form.get('is_shelf', 'true').lower() in ['true', '1', 'on', 'checked', 'yes']
        
        # 验证必要字段
        if not (dish_name and price and category):
            return jsonify({'code': 400, 'msg': '缺少必要信息：菜品名称、价格、分类'}), 400
        
        try:
            price_val = float(price)
            stock_val = int(stock) if stock else 0
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'msg': '价格或库存格式不正确'}), 400
        
        # 处理图片
        img_url = 'default_dish.jpg'
        if 'dish_img' in request.files and request.files['dish_img'].filename:
            try:
                img_url = save_file(request.files['dish_img'], 'dish')
            except Exception as e:
                return jsonify({'code': 400, 'msg': f'图片上传失败：{str(e)}'}), 400
        
        # 创建菜品
        dish = Dish(
            merchant_id=merchant.id,
            dish_name=dish_name.strip(),
            price=price_val,
            stock=stock_val,
            category=category.strip(),
            img_url=img_url,
            description=description.strip() if description else '',
            is_shelf=is_shelf
        )
        
        db.session.add(dish)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '菜品添加成功',
            'data': {
                'dish_id': dish.id,
                'dish_name': dish.dish_name,
                'is_shelf': dish.is_shelf
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'添加菜品失败：{str(e)}'
        }), 500

# 删除重复的路由定义，保留第323行的get_dishes()函数
# 该函数已实现分页功能并返回符合前端期望的格式

# 菜品上架/下架
@merchant_bp.post('/dish/<int:dish_id>/shelf')
@api_login_required
def toggle_dish_shelf(dish_id):
    try:
        merchant = get_current_merchant()
        
        # 查询菜品是否存在且属于当前商户
        dish = Dish.query.filter_by(id=dish_id, merchant_id=merchant.id).first()
        
        if not dish:
            return jsonify({
                'code': 404,
                'msg': '菜品不存在'
            }), 404
        
        shelf = request.json.get('shelf', True)
        dish.is_shelf = shelf
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '操作成功',
            'data': {
                'id': dish.id,
                'dish_name': dish.dish_name,
                'is_shelf': dish.is_shelf
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'操作失败：{str(e)}'
        }), 500

# 删除菜品
@merchant_bp.delete('/dish/<int:dish_id>')
@api_login_required
def delete_dish(dish_id):
    try:
        merchant = get_current_merchant()
        
        # 查询菜品是否存在且属于当前商户
        dish = Dish.query.filter_by(id=dish_id, merchant_id=merchant.id).first()
        
        if not dish:
            return jsonify({
                'code': 404,
                'msg': '菜品不存在'
            }), 404
        
        # 检查菜品是否在订单中
        from models.order import OrderItem
        order_item = OrderItem.query.filter_by(dish_id=dish_id).first()
        if order_item:
            return jsonify({
                'code': 400,
                'msg': '该菜品已被订购，无法删除'
            }), 400
        
        db.session.delete(dish)
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

# 接单
@merchant_bp.post('/order/accept/<int:order_id>')
@api_login_required
def accept_order(order_id):
    merchant = get_current_merchant()
    
    from models.order import Order
    order = Order.query.filter_by(id=order_id, merchant_id=merchant.id).first()
    if not order:
        return jsonify({'code': 404, 'msg': '订单不存在'}), 404
    if order.status != '待接单':
        return jsonify({'code': 400, 'msg': '订单状态错误'}), 400
    
    order.status = '待配送'
    db.session.commit()
    
    # 发送通知
    from services.notification_service import send_order_notification
    send_order_notification(order.student.phone, order.order_no, '待配送')
    
    return jsonify({'code': 200, 'msg': '接单成功'})