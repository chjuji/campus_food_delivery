from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
import os

# # 初始化数据库
# db = SQLAlchemy()
# 从 extensions 统一导入 db 实例（避免多个 SQLAlchemy 实例导致 metadata 不一致）
from extensions import db
# 初始化JWT
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 初始化插件
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, supports_credentials=True)
    
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

    # 商户端页面
    @app.route('/merchant/login')
    def merchant_login_page():
        return render_template('merchant/login.html')

    @app.route('/merchant/register')
    def merchant_register_page():
        return render_template('merchant/register.html')

    @app.route('/merchant/index')
    def merchant_index_page():
        return render_template('merchant/index.html')

    @app.route('/merchant/dish/add')
    def merchant_add_dish_page():
        return render_template('merchant/add_dish.html')  # 需创建该文件

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
            'models.cart', 'models.comment', 'models.complaint', 'models.coupon'
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