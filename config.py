import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 数据库配置
    # SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{os.getenv('DB_PWD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?charset=utf8mb4" # &password_charset=utf8"
    # SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 使用 SQLite 作为临时数据库
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'campus_food.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY','dev-secret-key-please-change-in-production')
    
    # JWT配置
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY','dev-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = 3600 * 2  # 2小时

    # 静态资源路径
    STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
    UPLOAD_FOLDER = {
        'dish': os.path.join(STATIC_FOLDER, 'uploads/dish'),
        'merchant': os.path.join(STATIC_FOLDER, 'uploads/merchant'),
        'avatar': os.path.join(STATIC_FOLDER, 'uploads/avatar'),
        'system': os.path.join(STATIC_FOLDER, 'uploads/system'),
        'comment': os.path.join(STATIC_FOLDER, 'uploads/comments')
    }

    # 允许的文件格式
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # 平台服务费
    PLATFORM_FEE_RATE = 0.05