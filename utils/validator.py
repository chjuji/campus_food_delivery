import re

def validate_student_register(data: dict) -> dict:
    """验证学生注册参数"""
    required = ['student_id', 'phone', 'password', 'name']
    for key in required:
        if key not in data or not data[key]:
            return {'valid': False, 'msg': f'缺少参数：{key}'}
    
    # 学号验证：13位数字
    if not re.match(r'^\d{13}$', data['student_id']):
        return {'valid': False, 'msg': '学号必须是13位数字'}
    
    # 手机号验证：11位数字
    if not re.match(r'^\d{11}$', data['phone']):
        return {'valid': False, 'msg': '手机号必须是11位数字'}
    
    # 密码验证：8-20位，包含字母和数字
    if len(data['password']) < 8 or len(data['password']) > 20:
        return {'valid': False, 'msg': '密码需8-20位'}
    if not (any(char.isalpha() for char in data['password']) and any(char.isdigit() for char in data['password'])):
        return {'valid': False, 'msg': '密码必须包含字母和数字'}
    
    return {'valid': True}

def validate_merchant_register(data: dict) -> dict:
    """验证商户注册参数"""
    required = ['merchant_name', 'contact_name', 'contact_phone', 'address', 'password']
    for key in required:
        if key not in data or not data[key]:
            return {'valid': False, 'msg': f'缺少参数：{key}'}
    
    if len(data['contact_phone']) != 11:
        return {'valid': False, 'msg': '手机号必须11位'}
    
    # 密码验证
    if not validate_password(data['password']):
        return {'valid': False, 'msg': '密码需8-20位，包含字母、数字和特殊符号(!@#$%^&*(),.?":{}|<>[])'}
    
    return {'valid': True}

def validate_password(password: str) -> bool:
    """验证密码格式：8-20位，包含字母、数字和特殊符号"""
    if len(password) < 8 or len(password) > 20:
        return False
    if not any(char.isalpha() for char in password):
        return False
    if not any(char.isdigit() for char in password):
        return False
    if not any(char in '!@#$%^&*(),.?":{}|<>[]' for char in password):
        return False
    return True