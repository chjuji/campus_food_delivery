from flask import Blueprint, jsonify, request
from models.dish import Dish
from models.merchant import Merchant

common_bp = Blueprint('common', __name__)

# 获取分类列表
@common_bp.get('/categories')
def get_categories():
    # 由于没有Category模型，提供硬编码的分类数据
    categories = [
        { 'id': 1, 'name': '快餐便当' },
        { 'id': 2, 'name': '奶茶饮品' },
        { 'id': 3, 'name': '特色小吃' },
        { 'id': 4, 'name': '水果生鲜' }
    ]
    return jsonify({'code': 200, 'data': categories})

# 获取商户列表
@common_bp.get('/merchants')
def get_merchants():
    merchants = Merchant.query.filter_by(status=1).all()  # 只显示已通过审核的
    data = [{
        'id': m.id,
        'name': m.merchant_name,
        'address': m.address,
        'contact_phone': m.contact_phone,
        'logo': m.logo,  # 添加Logo字段
        'description': getattr(m, 'description', ''),  # 添加描述字段
        'month_sales': 0  # 添加月售字段，暂时设为0
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

# 获取菜品评论
@common_bp.get('/dish_comments/<int:dish_id>')
def get_dish_comments(dish_id):
    try:
        from models.order import OrderItem, Order
        from models.comment import Comment
        
        # 1. 通过dish_id查找所有相关的订单项
        order_items = OrderItem.query.filter_by(dish_id=dish_id).all()
        
        # 2. 提取这些订单项对应的order_ids
        order_ids = [item.order_id for item in order_items]
        if not order_ids:
            return jsonify({'code': 200, 'data': []})
        
        # 3. 查询这些订单的评论
        comments = Comment.query.filter(Comment.order_id.in_(order_ids)).order_by(Comment.create_time.desc()).all()
        
        # 4. 构建返回数据
        comment_list = []
        for comment in comments:
            order_no = '-'  # 默认显示'-'
            if comment.order_id:
                # 查询订单信息获取订单号
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
                'img_urls': comment.img_urls.split(',') if comment.img_urls else [],
                'create_time': comment.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'merchant_reply': comment.merchant_reply,
                'reply_time': comment.reply_time.strftime('%Y-%m-%d %H:%M:%S') if comment.reply_time else None
            })
        
        return jsonify({'code': 200, 'data': comment_list})
    except Exception as e:
        print(f"获取菜品评论失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'获取评论失败: {str(e)}'}), 500



# 根据菜品类别获取菜品列表
@common_bp.get('/dishes_by_category')
def get_dishes_by_category():
    category = request.args.get('category')
    if not category:
        return jsonify({'code': 400, 'msg': '缺少category参数'}), 400
    
    # 查询该类别下的所有上架菜品
    dishes = Dish.query.filter_by(category=category, is_shelf=True).all()
    
    # 构建菜品列表，包含商户名称
    data = []
    for dish in dishes:
        # 获取对应的商户信息
        merchant = Merchant.query.get(dish.merchant_id)
        if merchant:
            data.append({
                'id': dish.id,
                'name': dish.dish_name,
                'price': dish.price,
                'category': dish.category,
                'img_url': dish.img_url,
                'description': dish.description,
                'merchant_id': dish.merchant_id,
                'merchant_name': merchant.merchant_name,
                'sales': 0  # 暂时设为0，实际应该从订单项目中统计
            })
    
    return jsonify({'code': 200, 'data': data})

# 获取所有菜品
@common_bp.get('/all_dishes')
def get_all_dishes():
    # 查询所有上架菜品
    dishes = Dish.query.filter_by(is_shelf=True).all()
    
    # 构建菜品列表，包含商户名称
    data = []
    for dish in dishes:
        # 获取对应的商户信息
        merchant = Merchant.query.get(dish.merchant_id)
        if merchant:
            data.append({
                'id': dish.id,
                'name': dish.dish_name,
                'price': dish.price,
                'category': dish.category,
                'img_url': dish.img_url,
                'description': dish.description,
                'merchant_id': dish.merchant_id,
                'merchant_name': merchant.merchant_name,
                'sales': 0  # 暂时设为0，实际应该从订单项目中统计
            })
    
    return jsonify({'code': 200, 'data': data})