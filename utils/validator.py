def validate_student_register(data: dict) -> dict:
    """验证学生注册参数"""
    required = ['student_id', 'phone', 'password', 'name']
    for key in required:
        if key not in data or not data[key]:
            return {'valid': False, 'msg': f'缺少参数：{key}'}
    
    if len(data['student_id']) < 6:
        return {'valid': False, 'msg': '学号长度至少6位'}
    if len(data['phone']) != 11:
        return {'valid': False, 'msg': '手机号必须11位'}
    if len(data['password']) < 8:
        return {'valid': False, 'msg': '密码至少8位'}
    
    return {'valid': True}

def validate_merchant_register(data: dict) -> dict:
    """验证商户注册参数"""
    required = ['merchant_name', 'contact_name', 'contact_phone', 'address']
    for key in required:
        if key not in data or not data[key]:
            return {'valid': False, 'msg': f'缺少参数：{key}'}
    
    if len(data['contact_phone']) != 11:
        return {'valid': False, 'msg': '手机号必须11位'}
    return {'valid': True}