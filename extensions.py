from flask_sqlalchemy import SQLAlchemy

# 统一的 SQLAlchemy 实例，模型与 app 都从这里 import db
db = SQLAlchemy()