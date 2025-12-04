from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.merchant import Merchant
from models.platform_config import PlatformConfig
from extensions import db

admin_bp = Blueprint('admin', __name__)

# 管理员登录（简化：硬编码管理员账号）
@admin_bp.post('/login')
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # 实际应从数据库查询管理员信息
    if username == 'admin' and password == 'admin123':
        from utils.jwt_utils import generate_token
        token = generate_token(0, 'admin')
        print('生成的管理员 token:', token)  # 调试输出
        return jsonify({
            'code': 200,
            'msg': '登录成功',
            'data': {
                'token': token
            }
        })
    return jsonify({'code': 401, 'msg': '账号或密码错误'}), 401

# 管理员首页页面路由（返回HTML）
@admin_bp.route('/index')
@jwt_required()  # 需登录验证
def admin_index():
    return render_template('admin/index.html')

# 已通过商户页面路由（返回HTML）
@admin_bp.route('/approved_merchants')
@jwt_required()  # 需登录验证
def admin_approved_merchants():
    return render_template('admin/index.html')

# 已驳回商户页面路由（返回HTML）
@admin_bp.route('/rejected_merchants')
@jwt_required()  # 需登录验证
def admin_rejected_merchants():
    return render_template('admin/index.html')

# 通用商户列表接口（支持按状态过滤）
@admin_bp.route('/merchants')
@jwt_required()  # 仅管理员可访问
def get_merchants():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 获取状态参数，默认为0（待审核）
        try:
            status = request.args.get('status', 0, type=int)
        except Exception:
            status = 0
        
        # 根据状态查询商户
        merchants = Merchant.query.filter_by(status=status).order_by(Merchant.create_time.desc()).all()
        
        # 转换为JSON可序列化的列表
        data = []
        for merchant in merchants:
            data.append({
                'id': merchant.id,
                'merchant_name': merchant.merchant_name,
                'contact_name': merchant.contact_name,
                'contact_phone': merchant.contact_phone,
                'address': merchant.address,
                'create_time': merchant.create_time.strftime('%Y-%m-%d %H:%M'),  # 格式化时间
                'license_img': merchant.license_img,  # 营业执照图片路径
                'logo': merchant.logo  # 商铺Logo路径
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})

# 待审核商户列表接口（供前端AJAX调用）
# 平台设置接口 - 获取所有配置
@admin_bp.route('/settings')
@jwt_required()
def get_platform_settings():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 获取所有平台配置
        configs = PlatformConfig.get_all()
        
        # 按分类组织配置
        config_dict = {}
        for config in configs:
            if config.category not in config_dict:
                config_dict[config.category] = []
            config_dict[config.category].append(config.to_dict())
        
        return jsonify({
            'code': 200,
            'msg': '获取成功',
            'data': config_dict
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'获取失败：{str(e)}'})

# 平台设置接口 - 更新配置
@admin_bp.route('/update_settings', methods=['POST'])
@jwt_required()
def update_platform_settings():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 获取请求数据
        data = request.json
        if not data or not isinstance(data, list):
            return jsonify({'code': 400, 'msg': '请求数据格式错误'}), 400
        
        updated_count = 0
        
        # 更新配置
        for config_data in data:
            config_key = config_data.get('config_key')
            config_value = config_data.get('config_value')
            
            if not config_key:
                continue
            
            # 查找配置
            config = PlatformConfig.get_by_key(config_key)
            if config:
                # 更新配置值
                config.config_value = config_value
                updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': f'成功更新 {updated_count} 项配置',
            'data': {'updated_count': updated_count}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'更新失败：{str(e)}'})

@admin_bp.route('/pending_merchants')
@jwt_required()  # 仅管理员可访问
def get_pending_merchants():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 查询状态为0（待审核）的商户，按创建时间倒序
        pending_merchants = Merchant.query.filter_by(status=0).order_by(Merchant.create_time.desc()).all()
        
        # 转换为JSON可序列化的列表
        data = []
        for merchant in pending_merchants:
            data.append({
                'id': merchant.id,
                'merchant_name': merchant.merchant_name,
                'contact_name': merchant.contact_name,
                'contact_phone': merchant.contact_phone,
                'address': merchant.address,
                'create_time': merchant.create_time.strftime('%Y-%m-%d %H:%M'),  # 格式化时间
                'license_img': merchant.license_img,  # 营业执照图片路径
                'logo': merchant.logo  # 商铺Logo路径
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})

# 已通过商户列表接口
@admin_bp.route('/get_approved_merchants')
@jwt_required()  # 仅管理员可访问
def get_approved_merchants():
    # 复用通用接口，设置状态为1（已通过）
    from flask import request
    request.args = request.args.copy()
    request.args['status'] = 1
    return get_merchants()

# 已驳回商户列表接口
@admin_bp.route('/get_rejected_merchants')
@jwt_required()  # 仅管理员可访问
def get_rejected_merchants():
    # 复用通用接口，设置状态为2（已驳回）
    from flask import request
    request.args = request.args.copy()
    request.args['status'] = 2
    return get_merchants()

# 审核商户接口（通过/驳回）
@admin_bp.route('/review_merchant', methods=['POST'])
@jwt_required()
def review_merchant():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        data = request.get_json()
        merchant_id = data.get('id')
        action = data.get('action')  # 'pass' 或 'reject'
        
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return jsonify({'code': 404, 'msg': '商户不存在'})
        
        # 更新状态：1=通过，2=驳回
        merchant.status = 1 if action == 'pass' else 2
        db.session.commit()
        return jsonify({'code': 200, 'msg': '审核已处理'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'操作失败：{str(e)}'})

# 删除商户接口
@admin_bp.route('/delete_merchant', methods=['POST'])
@jwt_required()
def delete_merchant():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        data = request.get_json()
        merchant_id = data.get('id')
        
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return jsonify({'code': 404, 'msg': '商户不存在'})
        
        # 删除商户
        db.session.delete(merchant)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '商户已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'操作失败：{str(e)}'})

# 更新商户状态接口（上架/下架）
@admin_bp.route('/update_merchant_status', methods=['POST'])
@jwt_required()
def update_merchant_status():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        data = request.get_json()
        merchant_id = data.get('id')
        status = data.get('status')  # 1=上架，2=下架
        
        merchant = Merchant.query.get(merchant_id)
        if not merchant:
            return jsonify({'code': 404, 'msg': '商户不存在'})
        
        # 更新状态
        merchant.status = status
        db.session.commit()
        return jsonify({'code': 200, 'msg': '商户状态已更新'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'操作失败：{str(e)}'})

# # 临时调试路由 - 检查商户数据
# @admin_bp.get('/debug/merchants')
# @jwt_required()
# def debug_merchants():
#     identity = get_jwt_identity()
#     if identity['type'] != 'admin':
#         return jsonify({'code': 403, 'msg': '权限错误'}), 403

#     merchants = Merchant.query.filter_by(status=0).all()
    
#     debug_info = []
#     for m in merchants:
#         debug_info.append({
#             'id': m.id,
#             'merchant_name': f"Type: {type(m.merchant_name)}, Value: {m.merchant_name}",
#             'contact_name': f"Type: {type(m.contact_name)}, Value: {m.contact_name}",
#             'contact_phone': f"Type: {type(m.contact_phone)}, Value: {m.contact_phone}",
#             'address': f"Type: {type(m.address)}, Value: {m.address}",
#             'status': m.status
#         })
    
#     return jsonify({'code': 200, 'debug_data': debug_info})

# 新增：获取商户列表（支持按 status 过滤）
# @admin_bp.get('/merchants')
# @jwt_required()
# def list_merchants():
#     identity = get_jwt_identity()
#     if identity['type'] != 'admin':
#         return jsonify({'code': 403, 'msg': '权限错误'}), 403

#     # status 参数可为查询字符串 ?status=0
#     try:
#         status = request.args.get('status', type=int)
#         print(f"status参数值: {status}, 类型: {type(status)}")
#     except Exception:
#         status = None

#     query = Merchant.query
#     if status is not None:
#         query = query.filter_by(status=status)
#     merchants = query.order_by(Merchant.create_time.desc()).all()

#     data = []
#     for m in merchants:
#         data.append({
#             'id': m.id,
#             'merchant_name': m.merchant_name,
#             'contact_name': m.contact_name,
#             'contact_phone': m.contact_phone,
#             'address': m.address,
#             'license_img': getattr(m, 'license_img', ''),
#             'logo': getattr(m, 'logo', ''),
#             'status': m.status,
#             'create_time': m.create_time.strftime('%Y-%m-%d %H:%M') if m.create_time else ''
#         })

#     return jsonify({'code': 200, 'data': data})

# def list_merchants():
#     print("进入 list_merchants 路由")  # 调试信息
#     identity = get_jwt_identity()
#     if identity['type'] != 'admin':
#         return jsonify({'code': 403, 'msg': '权限错误'}), 403

#     try:
#         # status 参数可为查询字符串 ?status=0
#         try:
#             status = request.args.get('status', type=int)
#         except Exception:
#             status = None

#         print(f"查询商户列表，状态: {status}")  # 调试信息

#         query = Merchant.query
#         if status is not None:
#             query = query.filter_by(status=status)
#         merchants = query.order_by(Merchant.create_time.desc()).all()

#         print(f"找到 {len(merchants)} 个商户")  # 调试信息

#         data = []
#         for m in merchants:
#             # 逐个处理商户数据，捕获可能的序列化错误
#             try:
#                 merchant_data = {
#                     'id': m.id,
#                     'merchant_name': str(m.merchant_name) if m.merchant_name else '',  # 确保是字符串
#                     'contact_name': str(m.contact_name) if m.contact_name else '',
#                     'contact_phone': str(m.contact_phone) if m.contact_phone else '',
#                     'address': str(m.address) if m.address else '',
#                     'license_img': str(getattr(m, 'license_img', '')) if getattr(m, 'license_img', '') else '',
#                     'logo': str(getattr(m, 'logo', '')) if getattr(m, 'logo', '') else '',
#                     'status': int(m.status) if m.status is not None else 0,
#                     'create_time': m.create_time.strftime('%Y-%m-%d %H:%M') if m.create_time else ''
#                 }
#                 data.append(merchant_data)
#             except Exception as e:
#                 print(f"处理商户 {m.id} 数据时出错: {str(e)}")
#                 continue

#         print("成功序列化数据")  # 调试信息
#         return jsonify({'code': 200, 'data': data})
    
#     except Exception as e:
#         # 添加详细的错误信息
#         import traceback
#         error_details = traceback.format_exc()
#         print(f"获取商户列表错误: {str(e)}")
#         print(f"详细错误: {error_details}")
#         return jsonify({
#             'code': 500, 
#             'msg': f'服务器错误: {str(e)}',
#             'debug': error_details
#         }), 500

# # 审核商户
# @admin_bp.post('/merchant/review/<int:merchant_id>')
# @jwt_required()
# def review_merchant(merchant_id):
#     identity = get_jwt_identity()
#     if identity['type'] != 'admin':
#         return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
#     data = request.get_json()
#     status = data.get('status')  # 1-通过 2-拒绝
#     if status not in [1, 2]:
#         return jsonify({'code': 400, 'msg': '状态错误'}), 400
    
#     merchant = Merchant.query.get(merchant_id)
#     if not merchant:
#         return jsonify({'code': 404, 'msg': '商户不存在'}), 404
    
#     merchant.status = status
#     db.session.commit()
    
#     return jsonify({
#         'code': 200,
#         'msg': '审核成功'
#     })

# 学生用户管理接口
@admin_bp.route('/students')
@jwt_required()  # 仅管理员可访问
def get_students():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 导入Student模型
        from models.student import Student
        
        # 获取过滤参数
        is_active = request.args.get('is_active', type=int)
        
        # 构建查询
        query = Student.query
        if is_active is not None:
            # 转换为布尔值
            is_active_bool = is_active == 1
            query = query.filter_by(is_active=is_active_bool)
        
        # 按注册时间倒序排序
        students = query.order_by(Student.create_time.desc()).all()
        
        # 转换为JSON可序列化的列表
        data = []
        for student in students:
            data.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': student.name,
                'phone': student.phone,
                'avatar': student.avatar,
                'create_time': student.create_time.strftime('%Y-%m-%d %H:%M'),  # 格式化时间
                'is_active': student.is_active
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})

# 更新学生账户状态（激活/禁用）
@admin_bp.route('/update_student_status', methods=['POST'])
@jwt_required()
def update_student_status():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 导入Student模型
        from models.student import Student
        
        data = request.get_json()
        student_id = data.get('id')
        is_active = data.get('is_active')  # True=激活，False=禁用
        
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'code': 404, 'msg': '学生用户不存在'})
        
        # 更新状态
        student.is_active = is_active
        db.session.commit()
        return jsonify({'code': 200, 'msg': '状态更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'msg': f'操作失败：{str(e)}'})

# 查看投诉
@admin_bp.get('/complaints')
@jwt_required()
def get_complaints():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 查询所有投诉
        from models.complaint import Complaint
        complaints = Complaint.query.order_by(Complaint.create_time.desc()).all()
        
        # 转换为JSON可序列化的列表
        data = []
        for complaint in complaints:
            data.append({
                'id': complaint.id,
                'order_id': complaint.order_id,
                'student_id': complaint.student_id,
                'content': complaint.content,
                'status': complaint.status,
                'create_time': complaint.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'handle_time': complaint.handle_time.strftime('%Y-%m-%d %H:%M:%S') if complaint.handle_time else None
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})

# 订单统计接口
@admin_bp.route('/orders')
@jwt_required()
def get_order_statistics():
    try:
        # 验证管理员权限
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'admin':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 获取时间参数
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # 导入Order模型
        from models.order import Order
        from datetime import datetime, timedelta
        
        # 构建查询
        query = Order.query
        
        # 添加时间过滤
        if start_date:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Order.create_time >= start_datetime)
        if end_date:
            # 结束日期设为当天的23:59:59
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1, seconds=-1)
            query = query.filter(Order.create_time <= end_datetime)
        
        # 执行查询
        orders = query.all()
        
        # 统计数据
        total_orders = len(orders)
        completed_orders = sum(1 for order in orders if order.status == '已完成')
        cancelled_orders = sum(1 for order in orders if order.status == '已取消')
        total_sales = sum(order.pay_amount for order in orders if order.status == '已完成')
        
        # 按状态分组统计
        status_count = {}
        for order in orders:
            status_count[order.status] = status_count.get(order.status, 0) + 1
        

        
        # 按商户统计销售
        merchant_sales = {}
        for order in orders:
            if order.status == '已完成':
                merchant_sales[order.merchant_id] = merchant_sales.get(order.merchant_id, 0) + order.pay_amount
        
        # 获取订单列表（用于表格展示）
        order_list = []
        for order in orders:
            order_list.append({
                'id': order.id,
                'order_no': order.order_no,
                'student_id': order.student_id,
                'merchant_id': order.merchant_id,
                'total_amount': order.total_amount,
                'pay_amount': order.pay_amount,
                'discount_amount': order.discount_amount,

                'status': order.status,
                'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # 返回统计数据
        return jsonify({
            'code': 200,
            'data': {
                'summary': {
                    'total_orders': total_orders,
                    'completed_orders': completed_orders,
                    'cancelled_orders': cancelled_orders,
                    'pending_orders': status_count.get('待处理', 0),
                    'processing_orders': status_count.get('处理中', 0),
                    'delivered_orders': status_count.get('已送达', 0),
                    'total_sales': round(total_sales, 2),
                    'average_order_value': round(total_sales / completed_orders, 2) if completed_orders > 0 else 0
                },
                'status_count': status_count,
                'merchant_sales': merchant_sales,
                'orders': order_list
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})