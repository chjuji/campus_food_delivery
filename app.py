from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
import os

# # 初始化数据库
# db = SQLAlchemy()
# 从 extensions 统一导入 db 实例（避免多个 SQLAlchemy 实例导致 metadata 不一致）
from extensions import db, bcrypt, scheduler
# 初始化JWT
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 在调用前定义setup_scheduler_tasks函数
    def setup_scheduler_tasks():
        """设置定时任务"""
        from models.merchant import Merchant
        from routes.merchant import calculate_merchant_status
        from datetime import datetime
        
        def update_merchants_status():
            """每隔60秒更新所有商户的营业状态"""
            try:
                with app.app_context():
                    # 获取所有商户
                    merchants = Merchant.query.all()
                    # print(f"[{datetime.now()}] 定时任务开始，找到 {len(merchants)} 个商户")
                    
                    updated_count = 0
                    for merchant in merchants:
                        # print(f"[{datetime.now()}] 正在处理商户ID: {merchant.id}, 当前状态: {'营业中' if merchant.is_open else '已关闭'}, 营业时间: {merchant.business_hours or '未设置'}")
                        # 计算新的营业状态
                        new_is_open = calculate_merchant_status(merchant)
                        
                        # 如果状态发生变化，更新数据库
                        if merchant.is_open != new_is_open:
                            merchant.is_open = new_is_open
                            updated_count += 1
                            # print(f"[{datetime.now()}] 商户ID {merchant.id} 状态更新为: {'营业中' if new_is_open else '已关闭'}")
                    
                    # 提交所有更改
                    db.session.commit()
                
                # if updated_count > 0:
                    # print(f"[{datetime.now()}] 定时任务完成，更新了 {updated_count} 个商户的营业状态")
            except Exception as e:
                print(f"[{datetime.now()}] 定时任务执行失败: {str(e)}")
                # 如果有异常，回滚事务
                with app.app_context():
                    db.session.rollback()
        
        # 添加定时任务
        scheduler.add_job(
            func=update_merchants_status,
            trigger='interval',
            seconds=60,
            id='update_merchants_status',
            misfire_grace_time=900,
            replace_existing=True
        )
        print("定时任务 'update_merchants_status' 已添加")
    
    # 初始化插件
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, supports_credentials=True)
    
    # 初始化定时任务调度器
    # if not scheduler.running:
    # 在Flask调试模式下，会启动两个进程支持热重载，导致调度器被初始化两次
    # 使用进程ID检查确保只有一个进程初始化调度器
    import os
    # 检查是否为Flask的主进程（第一个进程）
    # 当Flask以debug=True运行时，会创建一个主进程和一个重载进程
    # 主进程的特征是有WERKZEUG_RUN_MAIN环境变量或该变量值为'true'
    is_main_process = os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
    
    # 只有当调度器未运行且是主进程时才初始化调度器
    if not scheduler.running and is_main_process:
        scheduler.init_app(app)
        # 在应用上下文中启动调度器
        with app.app_context():
            scheduler.start()
            print("APScheduler 初始化成功")
            # 设置定时任务
            setup_scheduler_tasks()
    elif not is_main_process:
        print("非主进程，跳过调度器初始化，避免重复执行定时任务")
    
    # 创建上传目录
    for folder in Config.UPLOAD_FOLDER.values():
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    # 注册蓝图
    from routes.student import student_bp
    from routes.merchant import merchant_bp
    from routes.admin import admin_bp
    from routes.order import order_bp
    from routes.common import common_bp
    
    app.register_blueprint(student_bp, url_prefix='/api/student')
    app.register_blueprint(merchant_bp, url_prefix='/api/merchant')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(order_bp, url_prefix='/api/order')
    app.register_blueprint(common_bp, url_prefix='/api/common')

    # 补充页面路由：访问URL时返回对应的HTML页面
    from flask import render_template  # 导入渲染模板的函数

    # 学生端页面
    @app.route('/student/login')
    def student_login_page():
        return render_template('student/login.html')  # 对应templates/student/login.html

    @app.route('/student/register')
    def student_register_page():
        return render_template('student/register.html')

    @app.route('/student/index')
    def student_index_page():
        return render_template('student/index.html')

    @app.route('/student/cart')
    def student_cart_page():
        return render_template('student/cart.html')

    @app.route('/student/orders')
    def student_orders_page():
        return render_template('student/orders.html')

    @app.route('/student/profile')
    def student_profile_page():
        return render_template('student/profile.html')

    @app.route('/student/complaints')
    def student_complaints_page():
        return render_template('student/complaints.html')

    # 商户端页面
    @app.route('/merchant/login')
    def merchant_login_page():
        return render_template('merchant/login.html')

    @app.route('/merchant/register')
    def merchant_register_page():
        return render_template('merchant/register.html')

    @app.route('/merchant/index')
    def merchant_index_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/index.html', merchant_info=merchant_info)

    @app.route('/merchant/orders')
    def merchant_orders_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/orders.html', merchant_info=merchant_info)

    @app.route('/merchant/dishes')
    def merchant_dishes_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/dishes.html', merchant_info=merchant_info)
    
    # 商户端其他页面路由
    @app.route('/merchant/profile')
    def merchant_profile_page():
        # 从merchant.py导入merchant_profile函数
        from routes.merchant import merchant_profile
        return merchant_profile()

    @app.route('/merchant/statistics')
    def merchant_statistics_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/statistics.html', merchant_info=merchant_info)

    @app.route('/merchant/settings')
    def merchant_settings_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/settings.html', merchant_info=merchant_info)

    @app.route('/merchant/dish/add_dish')
    def merchant_add_dish_page():
        # 传递空的merchant_info对象，避免模板渲染错误
        merchant_info = {}
        return render_template('merchant/add_dish.html', merchant_info=merchant_info)

    # 管理员端页面
    @app.route('/admin/login')
    def admin_login_page():
        return render_template('admin/login.html')

    @app.route('/admin/index')
    def admin_index_page():
        return render_template('admin/index.html')
    

    
    
    
    # 创建数据库表：先导入所有模型模块，然后交由 db.create_all()
    with app.app_context():
        import importlib
        model_modules = [
            'models.student', 'models.merchant', 'models.order', 'models.dish',
            'models.cart', 'models.comment', 'models.complaint', 'models.coupon',
            'models.platform_config'
        ]
        for m in model_modules:
            try:
                importlib.import_module(m)
                # print(f'已导入模块: {m}')
            except Exception as e:
                print(f'导入模型模块 {m} 失败: {e}')

        try:
            # 在同一 db 实例上创建所有表（若不存在）
            db.create_all()
            from sqlalchemy import inspect
            # print('已创建/存在的数据库表（engine）:', inspect(db.engine).get_table_names())
            
            # 初始化平台配置数据
            try:
                # 检查是否存在platform_config表
                inspector = inspect(db.engine)
                if 'platform_config' in inspector.get_table_names():
                    from models.platform_config import PlatformConfig
                    
                    # 检查是否已有配置数据
                    if PlatformConfig.query.count() == 0:
                        # 初始化默认配置数据
                        default_configs = [
                            # 基本信息配置
                            {'config_key': 'platform_name', 'config_value': '校园餐饮平台', 'config_type': 'string', 'description': '平台名称', 'category': 'basic'},
                            {'config_key': 'contact_phone', 'config_value': '1234567890', 'config_type': 'string', 'description': '联系电话', 'category': 'basic'},
                            {'config_key': 'platform_logo', 'config_value': '', 'config_type': 'string', 'description': '平台Logo', 'category': 'basic'},
                            {'config_key': 'contact_email', 'config_value': 'admin@campusfood.com', 'config_type': 'string', 'description': '联系邮箱', 'category': 'basic'},
                            {'config_key': 'platform_desc', 'config_value': '为校园师生提供便捷的餐饮服务', 'config_type': 'string', 'description': '平台描述', 'category': 'basic'},
                            
                            # 订单设置
                            {'config_key': 'min_order_amount', 'config_value': '20', 'config_type': 'number', 'description': '最低起送金额', 'category': 'order'},
                            {'config_key': 'default_delivery_fee', 'config_value': '5', 'config_type': 'number', 'description': '默认配送费', 'category': 'order'},
                            
                            # 系统设置
                            {'config_key': 'system_maintenance', 'config_value': 'false', 'config_type': 'boolean', 'description': '系统维护中', 'category': 'system'},
                            {'config_key': 'cache_expiration', 'config_value': '300', 'config_type': 'number', 'description': '缓存过期时间(秒)', 'category': 'system'}
                        ]
                        
                        # 批量插入默认配置
                        for config_data in default_configs:
                            config = PlatformConfig(**config_data)
                            db.session.add(config)
                        
                        db.session.commit()
                        print('平台默认配置数据初始化完成')
            except Exception as e:
                print('初始化平台配置数据时出错：', e)
                db.session.rollback()
            
            # # 检查商户表是否有新增字段
            # inspector = inspect(db.engine)
            # merchant_columns = [col['name'] for col in inspector.get_columns('merchant')]
            
            # # 如果缺少新增字段，使用ALTER TABLE添加字段，避免数据丢失
            # new_columns = ['description', 'business_hours', 'is_open']
            # missing_columns = [col for col in new_columns if col not in merchant_columns]
            
            # if missing_columns:
            #     print(f'检测到商户表缺少字段: {missing_columns}')
            #     print('正在更新数据库结构...')
                
            #     # 使用SQLAlchemy的DDL语句添加缺失字段
            #     from sqlalchemy import text
                
            #     for column in missing_columns:
            #         if column == 'description':
            #             # 添加TEXT类型的description字段
            #             db.session.execute(text("ALTER TABLE merchant ADD COLUMN description TEXT"))
            #         elif column == 'business_hours':
            #             # 添加VARCHAR(50)类型的business_hours字段
            #             db.session.execute(text("ALTER TABLE merchant ADD COLUMN business_hours VARCHAR(50)"))
            #         elif column == 'is_open':
            #             # 添加BOOLEAN类型的is_open字段，默认值为True
            #             db.session.execute(text("ALTER TABLE merchant ADD COLUMN is_open BOOLEAN DEFAULT TRUE"))
                
            #     db.session.commit()
            #     print('数据库结构更新完成')
                
        except Exception as e:
            print('创建表时出错：', e)
    
    # 下面是之前用于绕过 metadata 不一致的逐表创建逻辑，暂时注释保留以便观察：
    # import inspect as pyinspect
    # for m in model_modules:
    #     try:
    #         mod = importlib.import_module(m)
    #         classes = [obj for _, obj in pyinspect.getmembers(mod, pyinspect.isclass)]
    #         for cls in classes:
    #             table = getattr(cls, '__table__', None)
    #             if table is not None:
    #                 try:
    #                     table.create(bind=db.engine, checkfirst=True)
    #                 except Exception as e:
    #                     print(f'创建表 {table.name} 失败: {e}')

    # # 创建数据库表
    # with app.app_context():
    #     import importlib
    #     import inspect as pyinspect
    #     model_modules = [
    #         'models.student', 'models.merchant', 'models.order', 'models.dish',
    #         'models.cart', 'models.comment', 'models.complaint', 'models.coupon'
    #     ]

    #     # 打印 db.metadata id 便于调试
    #     try:
    #         print('db.metadata id:', id(db.metadata))
    #     except Exception:
    #         pass

    #     # 逐个导入并检查模块内类，同时尝试按表逐个创建（绕过 metadata 不一致问题）
    #     for m in model_modules:
    #         try:
    #             mod = importlib.import_module(m)
    #             print(f'已导入模块: {m}')

    #             classes = [obj for _, obj in pyinspect.getmembers(mod, pyinspect.isclass)]
    #             for cls in classes:
    #                 table = getattr(cls, '__table__', None)
    #                 if table is not None:
    #                     print(f'  发现模型类: {cls.__name__}, 表名: {table.name}, table.metadata id: {id(table.metadata)}')
    #                     try:
    #                         # 直接在当前 engine 上创建该表（若已存在则跳过）
    #                         table.create(bind=db.engine, checkfirst=True)
    #                         print(f'    已创建/确认表存在: {table.name}')
    #                     except Exception as e:
    #                         print(f'    创建表 {table.name} 失败: {e}')
    #         except Exception as e:
    #             print(f'导入模型模块 {m} 失败: {e}')

    #     # 最后打印 engine 中已有的表名用于验证
    #     try:
    #         from sqlalchemy import inspect
    #         print('已创建/存在的数据库表（engine）:', inspect(db.engine).get_table_names())
    #     except Exception as e:
    #         print('检查 engine 表名时出错：', e)
    
    # 首页路由（测试用） -> 渲染 templates/home/index.html
    @app.route('/')
    def index():
        return render_template('home/index.html')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)