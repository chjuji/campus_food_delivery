from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.merchant import Merchant
from models.dish import Dish
from models.order import Order
from extensions import db
from utils.file_utils import save_file
from services.auth_service import merchant_register, merchant_login

merchant_bp = Blueprint('merchant', __name__)

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
    food_license_path = ''
    if 'license_img' in files and files['license_img'].filename:
        try:
            license_path = save_file(files['license_img'], 'merchant')
        except Exception as e:
            return jsonify({'code': 400, 'msg': f'营业执照上传失败：{str(e)}'}), 400
    if 'food_license_img' in files and files['food_license_img'].filename:
        try:
            food_license_path = save_file(files['food_license_img'], 'merchant')
        except Exception as e:
            return jsonify({'code': 400, 'msg': f'食品许可证上传失败：{str(e)}'}), 400

    # 组装数据传给服务层
    data = {
        'merchant_name': form.get('merchant_name'),
        'contact_name': form.get('contact_name'),
        'contact_phone': form.get('contact_phone'),
        'password': form.get('password'),
        'address': form.get('address'),
        'license_img': license_path,
        'food_license_img': food_license_path
    }

    result = merchant_register(data)
    if isinstance(result, dict) and result.get('error'):
        return jsonify({'code': 400, 'msg': result.get('error')}), 400

    return jsonify({'code': 200, 'msg': '注册成功', 'data': {'id': result.id, 'name': result.merchant_name}})


# 商户登录
@merchant_bp.post('/login')
def login():
    data = request.get_json()
    phone = data.get('contact_phone') or data.get('phone')
    password = data.get('password')
    if not phone or not password:
        return jsonify({'code': 400, 'msg': '请输入手机号和密码'}), 400

    result = merchant_login(phone, password)
    if not result or isinstance(result, dict) and result.get('error'):
        msg = result.get('error') if isinstance(result, dict) else '账号或密码错误'
        return jsonify({'code': 401, 'msg': msg}), 401

    return jsonify({'code': 200, 'msg': '登录成功', 'data': result})

# 添加菜品
@merchant_bp.post('/dish/add')
@jwt_required()
def add_dish():
    try:
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'merchant':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        # 获取表单数据（支持文件上传）
        dish_name = request.form.get('dish_name')
        price = request.form.get('price')
        category = request.form.get('category')
        stock = request.form.get('stock', 0)
        description = request.form.get('description', '')
        
        if not (dish_name and price and category):
            return jsonify({'code': 400, 'msg': '缺少菜品信息'}), 400
        
        # 处理图片
        img_url = 'default_dish.jpg'
        if 'dish_img' in request.files:
            try:
                img_url = save_file(request.files['dish_img'], 'dish')
            except Exception as e:
                return jsonify({'code': 400, 'msg': f'图片上传失败：{str(e)}'}), 400
        
        # 创建菜品
        dish = Dish(
            merchant_id=int(user_id),
            dish_name=dish_name,
            price=float(price),
            stock=int(stock),
            category=category,
            img_url=img_url,
            description=description,
            is_shelf=True
        )
        db.session.add(dish)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'msg': '菜品添加成功',
            'data': {'dish_id': dish.id}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'添加菜品失败：{str(e)}'
        }), 500

# 获取商户菜品列表
@merchant_bp.get('/dishes')
@jwt_required()
def get_merchant_dishes():
    try:
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'merchant':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        dishes = Dish.query.filter_by(merchant_id=int(user_id)).order_by(Dish.create_time.desc()).all()
        
        return jsonify({
            'code': 200,
            'msg': '获取菜品列表成功',
            'data': [{
                'id': dish.id,
                'dish_name': dish.dish_name,
                'price': dish.price,
                'category': dish.category,
                'stock': dish.stock,
                'img_url': dish.img_url,
                'description': dish.description,
                'is_shelf': dish.is_shelf,
                'create_time': dish.create_time.isoformat() if dish.create_time else None
            } for dish in dishes]
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取菜品列表失败：{str(e)}'
        }), 500

# 菜品上架/下架
@merchant_bp.post('/dish/<int:dish_id>/shelf')
@jwt_required()
def toggle_dish_shelf(dish_id):
    try:
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'merchant':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        dish = Dish.query.filter_by(id=dish_id, merchant_id=int(user_id)).first()
        
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
@jwt_required()
def delete_dish(dish_id):
    try:
        identity_str = get_jwt_identity()
        # 解析身份字符串格式 "user_type:user_id"
        if ':' not in identity_str:
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        user_type, user_id = identity_str.split(':', 1)
        if user_type != 'merchant':
            return jsonify({'code': 403, 'msg': '权限错误'}), 403
        
        dish = Dish.query.filter_by(id=dish_id, merchant_id=int(user_id)).first()
        
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
@jwt_required()
def accept_order(order_id):
    identity_str = get_jwt_identity()
    # 解析身份字符串格式 "user_type:user_id"
    if ':' not in identity_str:
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    user_type, user_id = identity_str.split(':', 1)
    if user_type != 'merchant':
        return jsonify({'code': 403, 'msg': '权限错误'}), 403
    
    from models.order import Order
    order = Order.query.filter_by(id=order_id, merchant_id=int(user_id)).first()
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