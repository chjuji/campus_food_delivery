from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.merchant import Merchant
from models.dish import Dish
from models.order import Order, OrderItem
from models.coupon import Coupon
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
        merchant = None
        try:
            # print(f"[DEBUG] Session内容: {dict(session)}")
            # 首先检查session中是否有登录信息
            if 'merchant_id' in session:
                # print(f"[DEBUG] Session中有merchant_id: {session['merchant_id']}")
                merchant = Merchant.query.get(session['merchant_id'])
                # print(f"[DEBUG] 根据merchant_id查询到商户: {merchant}")
                if merchant:
                    return f(*args, **kwargs)
            
            # 然后检查JWT token
            from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            # print(f"[DEBUG] JWT identity: {identity}")
            
            if identity and ':' in identity:
                user_type, user_id = identity.split(':', 1)
                if user_type == 'merchant':
                    merchant = Merchant.query.get(int(user_id))
                    if merchant:
                        # 将merchant_id添加到session中以便后续使用
                        session['merchant_id'] = int(user_id)
                        return f(*args, **kwargs)
        except Exception as e:
            # 记录异常但不暴露具体错误信息
            print(f"[DEBUG] 认证过程中发生异常: {str(e)}")
            pass
        
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
    # 检查系统是否处于维护中
    from models.platform_config import PlatformConfig
    maintenance_config = PlatformConfig.get_by_key('system_maintenance')
    if maintenance_config and maintenance_config.config_value.lower() == 'true':
        return jsonify({'code': 403, 'msg': '系统正在维护中'}), 200
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
    # 检查系统是否处于维护中
    from models.platform_config import PlatformConfig
    maintenance_config = PlatformConfig.get_by_key('system_maintenance')
    if maintenance_config and maintenance_config.config_value.lower() == 'true':
        return jsonify({'code': 403, 'msg': '系统正在维护中'}), 200
    
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
    # 检查系统是否处于维护中
    from models.platform_config import PlatformConfig
    maintenance_config = PlatformConfig.get_by_key('system_maintenance')
    if maintenance_config and maintenance_config.config_value.lower() == 'true':
        return jsonify({'code': 403, 'msg': '系统正在维护中'}), 200
    
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
    # 检查系统是否处于维护中
    from models.platform_config import PlatformConfig
    maintenance_config = PlatformConfig.get_by_key('system_maintenance')
    if maintenance_config and maintenance_config.config_value.lower() == 'true':
        return jsonify({'success': False, 'message': '系统正在维护中'}), 200
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
@merchant_bp.route('/statistics_data', methods=['GET'])
@api_login_required
def get_merchant_statistics():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    # 获取时间范围参数，默认为1天
    days = request.args.get('days', 1, type=int)
    
    # 计算开始时间
    today = datetime.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 近1天指的是今天（从今天凌晨0点开始）
    # 近N天指的是从N-1天前的凌晨0点到现在（例如近3天是前天、昨天、今天）
    start_time = today_start - timedelta(days=days-1)
    
    # 订单数（已送达）
    total_orders = Order.query.filter_by(
        merchant_id=merchant.id,
        status='已送达'
    ).filter(Order.create_time >= start_time).count()
    
    # 收入（已送达订单的实付金额总和）
    total_income = db.session.query(func.sum(Order.pay_amount)).filter_by(
        merchant_id=merchant.id,
        status='已送达'
    ).filter(Order.create_time >= start_time).scalar() or 0
    
    # 待处理订单数（待接单和制作中）
    pending_orders = Order.query.filter_by(
        merchant_id=merchant.id
    ).filter(Order.status.in_(['待接单', '制作中', '待配送'])).count()
    
    # 售出菜品数（统计指定时间范围内所有已送达订单中的菜品总数）
    total_dishes_sold = db.session.query(func.sum(OrderItem.quantity)).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.merchant_id == merchant.id,
        Order.status == '已送达',
        Order.create_time >= start_time
    ).scalar() or 0
    
    # 今日订单数（今天0点至今）
    today_orders = Order.query.filter_by(
        merchant_id=merchant.id,
        status='已送达'
    ).filter(Order.create_time >= today_start).count()
    
    # 今日收入（今天0点至今）
    today_income = db.session.query(func.sum(Order.pay_amount)).filter_by(
        merchant_id=merchant.id,
        status='已送达'
    ).filter(Order.create_time >= today_start).scalar() or 0
    
    # 在售菜品数（状态为上架的菜品）
    active_dishes = Dish.query.filter_by(
        merchant_id=merchant.id,
        is_shelf=True  # True表示在售
    ).count()
    
    # 小时级销售数据和订单数
    hourly_sales = []
    hourly_orders = []
    
    # 获取今日每小时的销售数据和订单数
    for hour in range(24):
        # 计算当前小时的开始和结束时间
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        
        # 查询当前小时的销售额
        hour_sales = db.session.query(func.sum(Order.pay_amount)).filter_by(
            merchant_id=merchant.id,
            status='已送达'
        ).filter(
            Order.create_time >= hour_start,
            Order.create_time < hour_end
        ).scalar() or 0
        
        # 查询当前小时的订单数
        hour_order_count = Order.query.filter_by(
            merchant_id=merchant.id,
            status='已送达'
        ).filter(
            Order.create_time >= hour_start,
            Order.create_time < hour_end
        ).count()
        
        hourly_sales.append(float(hour_sales))
        hourly_orders.append(hour_order_count)
    
    # 构建统计数据
    statistics = {
        'total_orders': total_orders,
        'total_income': total_income,
        'pending_orders': pending_orders,
        'total_dishes_sold': total_dishes_sold,
        'today_orders': today_orders,
        'today_income': today_income,
        'active_dishes': active_dishes,
        'hourly_sales': hourly_sales,
        'hourly_orders': hourly_orders
    }
    
    return jsonify({'success': True, 'data': statistics})

# 获取订单列表API
@merchant_bp.route('/orders', methods=['GET'])
@api_login_required
def get_merchant_orders():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    sort = request.args.get('sort', 'latest')
    order_no = request.args.get('order_no', '')
    status = request.args.get('status', '')
    
    # 构建查询
    query = Order.query.filter_by(merchant_id=merchant.id)
    
    # 订单号筛选
    if order_no:
        query = query.filter(Order.order_no.like(f'%{order_no}%'))
    
    # 状态筛选
    if status:
        query = query.filter_by(status=status)
    
    # 排序
    if sort == 'latest':
        query = query.order_by(Order.create_time.desc())
    elif sort == 'amount':
        query = query.order_by(Order.total_amount.desc())
    
    # 分页
    pagination = query.paginate(page=page, per_page=limit, error_out=False)
    
    # 格式化订单数据
    orders = []
    for order in pagination.items:
        order_data = order.to_dict()
        # 添加订单商品信息
        order_data['items'] = []
        for item in order.order_items:
            # 从Dish模型获取菜品名称
            dish = Dish.query.get(item.dish_id)
            dish_name = dish.dish_name if dish else '未知菜品'
            order_data['items'].append({
                'id': item.id,
                'dish_id': item.dish_id,
                'dish_name': dish_name,
                'quantity': item.quantity,
                'price': item.price
            })
        orders.append(order_data)
    
    return jsonify({
        'success': True, 
        'data': orders, 
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    })

# 菜品相关API
@merchant_bp.route('/dishes/popular', methods=['GET'])
@api_login_required
def get_popular_dishes():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    limit = request.args.get('limit', 10, type=int)
    
    # 统计热销菜品：根据订单商品数量统计（仅统计已送达订单）
    from sqlalchemy import func
    
    # 先创建子查询，统计已送达订单中的菜品销量
    sales_subquery = db.session.query(
        OrderItem.dish_id,
        func.sum(OrderItem.quantity).label('total_sales')
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Order.status == '已送达'  # 只统计已送达订单
    ).group_by(
        OrderItem.dish_id
    ).subquery()
    
    # 查询当前商家的所有菜品，按销售量排序
    popular_dishes_query = db.session.query(
        Dish,
        func.coalesce(sales_subquery.c.total_sales, 0).label('total_sales')
    ).outerjoin(
        sales_subquery, Dish.id == sales_subquery.c.dish_id
    ).filter(
        Dish.merchant_id == merchant.id,
        Dish.is_shelf == True
    ).order_by(
        func.coalesce(sales_subquery.c.total_sales, 0).desc()
    ).limit(limit)
    
    popular_dishes = popular_dishes_query.all()
    
    # 格式化返回数据
    dishes = []
    for dish, total_sales in popular_dishes:
        sales = total_sales or 0
        total_amount = sales * dish.price  # 计算总销售额
        
        dishes.append({
            'id': dish.id,
            'dish_name': dish.dish_name,
            'price': dish.price,
            'sales': sales,
            'total_amount': total_amount,
            'img_url': dish.img_url,
            'category': dish.category
        })
    
    return jsonify({'success': True, 'data': dishes})

@merchant_bp.route('/orders/<int:order_id>', methods=['GET'])
@api_login_required
def get_merchant_order_detail(order_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    order = Order.query.filter_by(id=order_id, merchant_id=merchant.id).first()
    if not order:
        return jsonify({'success': False, 'message': '订单不存在'})
    
    # 获取订单商品
    order_items = OrderItem.query.filter_by(order_id=order_id).all()
    items = []
    for item in order_items:
        # 从Dish模型获取菜品名称
        dish = Dish.query.get(item.dish_id)
        dish_name = dish.dish_name if dish else '未知菜品'
        
        items.append({
            'id': item.id,
            'dish_name': dish_name,
            'price': item.price,
            'quantity': item.quantity,
            'dish_id': item.dish_id
        })
    
    # 从PlatformConfig表获取配送费
    from models.platform_config import PlatformConfig
    config = PlatformConfig.get_by_key('default_delivery_fee')
    delivery_fee = float(config.config_value) if config else 5.0  # 默认5元
    
    # 构造返回数据
    order_data = {
        'id': order.id,
        'order_no': order.order_no,
        'student_id': order.student_id,
        'status': order.status,
        'total_amount': order.total_amount,
        'pay_amount': order.pay_amount,
        'discount_amount': order.discount_amount,
        'delivery_fee': delivery_fee,  # 从PlatformConfig表获取的配送费
        'address': order.address,
        'remark': order.remark,
        'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else None,
        'pay_time': order.pay_time.strftime('%Y-%m-%d %H:%M:%S') if order.pay_time else None,
        'finish_time': order.finish_time.strftime('%Y-%m-%d %H:%M:%S') if order.finish_time else None,
        'items': items
    }
    
    return jsonify({
        'success': True,
        'data': order_data
    })

@merchant_bp.route('/orders/<int:order_id>/status', methods=['PUT'])
@api_login_required
def update_order_status(order_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    data = request.get_json()
    new_status = data.get('status')
    
    from models.order import Order
    order = Order.query.filter_by(id=order_id, merchant_id=merchant.id).first()
    if not order:
        return jsonify({'success': False, 'message': '订单不存在'})
    
    # 状态验证和转换
    valid_statuses = ['待支付', '待接单', '待配送', '已送达', '已取消']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'message': '无效的订单状态'})
    
    # 状态转换逻辑
    status_transitions = {
        '待支付': ['待接单', '已取消'],
        '待接单': ['待配送', '已取消'],
        '待配送': ['已送达'],
        '已送达': [],
        '已取消': []
    }
    
    if new_status not in status_transitions.get(order.status, []):
        return jsonify({'success': False, 'message': '状态转换不允许'})
    
    # 更新状态
    order.status = new_status
    db.session.commit()
    
    # 发送通知
    from services.notification_service import send_order_notification
    send_order_notification(order.student.phone, order.order_no, new_status)
    
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
        # 计算销量：只统计状态为"已送达"的订单
        sales = db.session.query(func.count(OrderItem.id))\
            .join(Order, Order.id == OrderItem.order_id)\
            .filter(OrderItem.dish_id == dish.id, Order.status == '已送达')\
            .scalar() or 0
        
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
            'logo': merchant.logo if merchant.logo else 'uploads/merchant/default.svg',
            'address': merchant.address,
            'status': merchant.status,
            'service_fee': merchant.service_fee,
            'wallet': merchant.wallet,
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
        'logo': getattr(merchant, 'logo', '') if getattr(merchant, 'logo', '') else 'uploads/merchant/default.svg'  # 添加默认logo
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
                
                # 删除旧Logo文件（如果存在且不是默认Logo）
                if merchant.logo:
                    # 商户Logo没有默认值，所以只要存在就删除
                    old_logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', merchant.logo)
                    if os.path.exists(old_logo_path):
                        os.remove(old_logo_path)
                        print(f'旧Logo文件已删除: {old_logo_path}')
                
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
        # 确保shelf是布尔值
        if isinstance(shelf, str):
            shelf = shelf.lower() == 'true'
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
        return jsonify({'success': False, 'message': '订单不存在'}), 404
    if order.status != '待接单':
        return jsonify({'success': False, 'message': '订单状态错误'}), 400
    
    order.status = '待配送'
    db.session.commit()
    
    # 发送通知
    from services.notification_service import send_order_notification
    send_order_notification(order.student.phone, order.order_no, '待配送')
    
    return jsonify({'success': True, 'message': '接单成功'})

# 获取商户优惠券列表
@merchant_bp.route('/coupons', methods=['GET'])
@api_login_required
def get_merchant_coupons():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        coupons = Coupon.query.filter_by(merchant_id=merchant.id).order_by(Coupon.create_time.desc()).all()
        
        coupon_list = []
        for coupon in coupons:
            coupon_list.append({
                'id': coupon.id,
                'coupon_name': coupon.coupon_name,
                'type': coupon.type,
                'value': coupon.value,
                'min_spend': coupon.min_spend,
                'total': coupon.total,
                'used': coupon.used,
                'start_time': coupon.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': coupon.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'create_time': coupon.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': coupon.is_active
            })
        
        return jsonify({'success': True, 'data': coupon_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取优惠券失败：{str(e)}'}), 500

# 获取单个优惠券详情
@merchant_bp.route('/coupons/<int:coupon_id>', methods=['GET'])
@api_login_required
def get_coupon_detail(coupon_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        coupon = Coupon.query.filter_by(id=coupon_id, merchant_id=merchant.id).first()
        if not coupon:
            return jsonify({'success': False, 'message': '优惠券不存在'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': coupon.id,
                'coupon_name': coupon.coupon_name,
                'type': coupon.type,
                'value': coupon.value,
                'min_spend': coupon.min_spend,
                'total': coupon.total,
                'used': coupon.used,
                'start_time': coupon.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': coupon.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'create_time': coupon.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': coupon.is_active
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取优惠券详情失败：{str(e)}'}), 500

# 创建优惠券
@merchant_bp.route('/coupons', methods=['POST'])
@api_login_required
def create_coupon():
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        data = request.get_json()
        coupon_name = data.get('coupon_name')
        type = data.get('type')
        value = data.get('value')
        min_spend = data.get('min_spend', 0)
        total = data.get('total')
        start_time = datetime.strptime(data.get('start_time'), '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(data.get('end_time'), '%Y-%m-%d %H:%M:%S')
        
        if not all([coupon_name, type, value, total, start_time, end_time]):
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        # 如果是无门槛券，强制将使用门槛设置为0
        if type == '无门槛':
            min_spend = 0
        
        new_coupon = Coupon(
            merchant_id=merchant.id,
            coupon_name=coupon_name,
            type=type,
            value=value,
            min_spend=min_spend,
            total=total,
            start_time=start_time,
            end_time=end_time
        )
        
        db.session.add(new_coupon)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '优惠券创建成功', 'data': {'id': new_coupon.id}})
    except ValueError as e:
        return jsonify({'success': False, 'message': f'时间格式错误：{str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建优惠券失败：{str(e)}'}), 500

# 更新优惠券
@merchant_bp.route('/coupons/<int:coupon_id>', methods=['PUT'])
@api_login_required
def update_coupon(coupon_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        coupon = Coupon.query.filter_by(id=coupon_id, merchant_id=merchant.id).first()
        if not coupon:
            return jsonify({'success': False, 'message': '优惠券不存在'}), 404
        
        data = request.get_json()
        coupon_name = data.get('coupon_name')
        type = data.get('type')
        value = data.get('value')
        min_spend = data.get('min_spend')
        total = data.get('total')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if coupon_name:
            coupon.coupon_name = coupon_name
        if type:
            coupon.type = type
            # 如果改为无门槛券，强制将使用门槛设置为0
            if type == '无门槛':
                coupon.min_spend = 0
        if value is not None:
            coupon.value = value
        if min_spend is not None and coupon.type != '无门槛':
            coupon.min_spend = min_spend
        if total is not None:
            coupon.total = total
        if start_time:
            coupon.start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if end_time:
            coupon.end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '优惠券更新成功'})
    except ValueError as e:
        return jsonify({'success': False, 'message': f'时间格式错误：{str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新优惠券失败：{str(e)}'}), 500

# 删除优惠券
@merchant_bp.route('/coupons/<int:coupon_id>', methods=['DELETE'])
@api_login_required
def delete_coupon(coupon_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        coupon = Coupon.query.filter_by(id=coupon_id, merchant_id=merchant.id).first()
        if not coupon:
            return jsonify({'success': False, 'message': '优惠券不存在'}), 404
        
        db.session.delete(coupon)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '优惠券删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'删除优惠券失败：{str(e)}'}), 500

# 更新优惠券激活状态
@merchant_bp.route('/coupons/<int:coupon_id>/status', methods=['PUT'])
@api_login_required
def update_coupon_status(coupon_id):
    merchant = get_current_merchant()
    if not merchant:
        return jsonify({'success': False, 'message': '未登录'})
    
    try:
        # 获取请求数据
        data = request.json
        is_active = data.get('is_active', False)
        
        # 查找优惠券
        coupon = Coupon.query.filter_by(id=coupon_id, merchant_id=merchant.id).first()
        if not coupon:
            return jsonify({'success': False, 'message': '优惠券不存在'}), 404
        
        # 更新激活状态
        coupon.is_active = is_active
        db.session.commit()
        
        return jsonify({'success': True, 'message': '优惠券状态更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新优惠券状态失败：{str(e)}'}), 500


@merchant_bp.route('/complaints', methods=['GET'])
@api_login_required
def get_merchant_complaints():
    """获取商户的投诉列表"""
    try:
        # 获取当前登录商户
        merchant = Merchant.query.get(session['merchant_id'])
        if not merchant:
            return jsonify({'success': False, 'message': '商户不存在'}), 404

        # 获取状态筛选参数
        status = request.args.get('status', 'all')

        # 查询该商户的投诉
        from models.complaint import Complaint
        query = Complaint.query.filter_by(merchant_id=merchant.id)
        
        # 状态筛选
        if status != 'all':
            query = query.filter_by(status=status)
            
        complaints = query.order_by(Complaint.create_time.desc()).all()

        # 构建返回数据
        complaint_list = []
        for complaint in complaints:
            order_no = '-'  # 默认显示'-'
            if complaint.order_id:
                # 查询订单信息获取订单号
                from models.order import Order
                order = Order.query.get(complaint.order_id)
                if order:
                    order_no = order.order_no
            
            complaint_list.append({
                'id': complaint.id,
                'order_id': complaint.order_id,
                'order_no': order_no,
                'content': complaint.content,
                'img_urls': complaint.formatted_img_urls,
                'status': complaint.status,
                'create_time': complaint.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'handle_time': complaint.handle_time.strftime('%Y-%m-%d %H:%M:%S') if complaint.handle_time else None,
                'handle_result': complaint.handle_result
            })

        return jsonify({'success': True, 'data': complaint_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取投诉列表失败：{str(e)}'}), 500

@merchant_bp.route('/comments', methods=['GET'])
@api_login_required
def get_merchant_comments():
    """获取商户的评论列表"""
    try:
        # 获取当前登录商户
        merchant = Merchant.query.get(session['merchant_id'])
        if not merchant:
            return jsonify({'success': False, 'message': '商户不存在'}), 404

        # 查询该商户的评论
        from models.comment import Comment
        comments = Comment.query.filter_by(merchant_id=merchant.id)
        comments = comments.order_by(Comment.create_time.desc()).all()

        # 构建返回数据
        comment_list = []
        for comment in comments:
            order_no = '-'  # 默认显示'-'
            if comment.order_id:
                # 查询订单信息获取订单号
                from models.order import Order
                order = Order.query.get(comment.order_id)
                if order:
                    order_no = order.order_no
            
            comment_list.append({
                'id': comment.id,
                'order_id': comment.order_id,
                'order_no': order_no,
                'content': comment.content,
                'dish_score': comment.dish_score,
                'service_score': comment.service_score,
                'img_urls': comment.formatted_img_urls,
                'create_time': comment.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'merchant_reply': comment.merchant_reply,
                'reply_time': comment.reply_time.strftime('%Y-%m-%d %H:%M:%S') if comment.reply_time else None
            })

        return jsonify({'success': True, 'data': comment_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取评论列表失败：{str(e)}'}), 500


@merchant_bp.route('/comments/<int:comment_id>/reply', methods=['POST'])
@api_login_required
def reply_comment(comment_id):
    """
    回复评论
    """
    try:
        # 获取当前登录商户
        merchant = Merchant.query.get(session['merchant_id'])
        if not merchant:
            return jsonify({'success': False, 'message': '商户不存在'}), 404

        # 获取回复内容
        reply_content = request.form.get('reply_content')
        if not reply_content:
            return jsonify({'success': False, 'message': '回复内容不能为空'}), 400
        
        if len(reply_content.strip()) < 5:
            return jsonify({'success': False, 'message': '回复内容不能少于5个字符'}), 400
        
        if len(reply_content) > 200:
            return jsonify({'success': False, 'message': '回复内容不能超过200个字符'}), 400
        
        # 检查是否包含敏感词或不当内容
        sensitive_words = ['垃圾', '差评', '恶心', '投诉']
        for word in sensitive_words:
            if word in reply_content:
                return jsonify({'success': False, 'message': '回复内容包含不当词汇，请修改后再提交'}), 400

        # 查询评论
        from models.comment import Comment
        comment = Comment.query.filter_by(id=comment_id, merchant_id=merchant.id).first()
        if not comment:
            return jsonify({'success': False, 'message': '评论不存在'}), 404

        # 更新评论回复
        comment.merchant_reply = reply_content
        comment.reply_time = datetime.now()
        db.session.commit()

        return jsonify({'success': True, 'message': '回复成功'})
    except Exception as e:
        # 添加详细的错误日志，方便调试
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] 回复评论时出错: {str(e)}")
        print(f"[ERROR] 详细堆栈信息: {error_trace}")
        return jsonify({'success': False, 'message': f'回复失败：{str(e)}', 'trace': error_trace}), 500


@merchant_bp.route('/complaints/<int:complaint_id>/accept', methods=['POST'])
@api_login_required
def accept_complaint(complaint_id):
    """
    接受投诉，将状态从待处理改为处理中
    """
    try:
        # 获取当前登录商户
        merchant = Merchant.query.get(session['merchant_id'])
        if not merchant:
            return jsonify({'success': False, 'message': '商户不存在'}), 404

        # 查询投诉记录
        from models.complaint import Complaint
        complaint = Complaint.query.filter_by(id=complaint_id, merchant_id=merchant.id).first()
        if not complaint:
            return jsonify({'success': False, 'message': '投诉记录不存在'}), 404

        # 检查当前状态是否为待处理
        if complaint.status != '待处理':
            return jsonify({'success': False, 'message': '只有待处理的投诉才能接受'}), 400

        # 更新状态为处理中
        complaint.status = '处理中'
        db.session.commit()

        return jsonify({'success': True, 'message': '投诉已接受，状态已更新为处理中'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'接受投诉失败：{str(e)}'}), 500


@merchant_bp.route('/complaints/<int:complaint_id>/resolve', methods=['POST'])
@api_login_required
def resolve_complaint(complaint_id):
    """
    解决投诉，将状态从处理中改为已解决
    """
    try:
        # 获取当前登录商户
        merchant = Merchant.query.get(session['merchant_id'])
        if not merchant:
            return jsonify({'success': False, 'message': '商户不存在'}), 404

        # 查询投诉记录
        from models.complaint import Complaint
        complaint = Complaint.query.filter_by(id=complaint_id, merchant_id=merchant.id).first()
        if not complaint:
            return jsonify({'success': False, 'message': '投诉记录不存在'}), 404

        # 检查当前状态是否为处理中
        if complaint.status != '处理中':
            return jsonify({'success': False, 'message': '只有处理中的投诉才能解决'}), 400

        # 获取处理结果
        from flask import request
        data = request.get_json()
        handle_result = data.get('handle_result', '')

        # 更新状态为已解决，并记录处理结果和处理时间
        from datetime import datetime
        complaint.status = '已解决'
        complaint.handle_result = handle_result
        complaint.handle_time = datetime.now()
        db.session.commit()

        return jsonify({'success': True, 'message': '投诉已解决，状态已更新为已解决'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'解决投诉失败：{str(e)}'}), 500