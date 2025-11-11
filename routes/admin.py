from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.merchant import Merchant
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
                'food_license_img': merchant.food_license_img  # 食品经营许可证路径
            })
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'查询失败：{str(e)}'})

# 待审核商户列表接口（供前端AJAX调用）
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
                'food_license_img': merchant.food_license_img  # 食品经营许可证路径
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
#             'food_license_img': getattr(m, 'food_license_img', ''),
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
#                     'food_license_img': str(getattr(m, 'food_license_img', '')) if getattr(m, 'food_license_img', '') else '',
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

# 查看投诉
@admin_bp.get('/complaints')
@jwt_required()
def get_complaints():
    # 验证管理员权限
    identity_str = get_jwt_identity()
    # 解析身份字符串格式 "user_type:user_id"
    if ':' not in identity_str:
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    user_type, user_id = identity_str.split(':', 1)
    if user_type != 'admin':
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    from models.complaint import Complaint
    complaints = Complaint.query.all()
    data = [{
        'id': c.id,
        'student_id': c.student_id,
        'content': c.content,
        'status': c.status,
        'create_time': c.create_time.strftime('%Y-%m-%d %H:%M')
    } for c in complaints]
    
    return jsonify({'code': 200, 'data': data})