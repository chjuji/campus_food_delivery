from flask_jwt_extended import create_access_token

def generate_token(user_id: int, user_type: str) -> str:
    """生成JWT Token（包含用户ID和类型）"""
    # return create_access_token(identity={"id": user_id, "type": user_type})
    # 使用字符串格式的identity，格式为 "user_type:user_id"
    identity = f"{user_type}:{user_id}"
    return create_access_token(identity=identity)
    # 422问题原因： Flask-JWT-Extended要求JWT的subject必须是字符串类型，但原来的代码使用了字典作为identity：这导致了"Subject must be a string"错误。