import bcrypt

def encrypt_password(password: str) -> str:
    """加密密码"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, encrypted_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode('utf-8'), encrypted_password.encode('utf-8'))