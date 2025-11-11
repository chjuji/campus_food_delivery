from flask import Blueprint, jsonify
from models.dish import Dish
from models.merchant import Merchant

common_bp = Blueprint('common', __name__)

# 获取商户列表
@common_bp.get('/merchants')
def get_merchants():
    merchants = Merchant.query.filter_by(status=1).all()  # 只显示已通过审核的
    data = [{
        'id': m.id,
        'name': m.merchant_name,
        'address': m.address,
        'contact_phone': m.contact_phone
    } for m in merchants]
    return jsonify({'code': 200, 'data': data})

# 获取菜品列表
@common_bp.get('/dishes/<int:merchant_id>')
def get_dishes(merchant_id):
    dishes = Dish.query.filter_by(merchant_id=merchant_id, is_shelf=True).all()
    data = [{
        'id': d.id,
        'name': d.dish_name,
        'price': d.price,
        'category': d.category,
        'img_url': d.img_url,
        'description': d.description
    } for d in dishes]
    return jsonify({'code': 200, 'data': data})