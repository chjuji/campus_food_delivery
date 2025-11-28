from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_apscheduler import APScheduler

# 统一的 SQLAlchemy 实例，模型与 app 都从这里 import db
db = SQLAlchemy()

# 统一的 Bcrypt 实例，用于密码加密
bcrypt = Bcrypt()

# 统一的 APScheduler 实例，用于定时任务
scheduler = APScheduler()