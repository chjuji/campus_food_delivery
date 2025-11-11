from models.student import Student
from models.merchant import Merchant
from utils.password_utils import encrypt_password, verify_password
from utils.jwt_utils import generate_token
from extensions import db

def student_register(data: dict):
    """学生注册业务逻辑"""
    encrypted_pwd = encrypt_password(data['password'])
    new_student = Student(
        student_id=data['student_id'],
        phone=data['phone'],
        password=encrypted_pwd,
        name=data['name']
    )
    db.session.add(new_student)
    db.session.commit()
    return new_student

def student_login(login_id: str, password: str):
    """学生登录（支持学号/手机号），返回具体错误信息"""
    student = Student.query.filter_by(student_id=login_id).first() or \
              Student.query.filter_by(phone=login_id).first()
    if not student:
        return {'error': '用户不存在'}
    if not verify_password(password, student.password):
        return {'error': '密码错误'}
    return {
        'token': generate_token(student.id, 'student'),
        'user_info': {
            'id': student.id,
            'name': student.name,
            'avatar': student.avatar
        }
    }

def merchant_register(data: dict):
    """商户注册（保存加密密码），检查手机号是否已注册"""
    # 检查手机号是否已被注册
    if Merchant.query.filter_by(contact_phone=data['contact_phone']).first():
        return {'error': '手机号已注册'}

    encrypted_pwd = encrypt_password(data['password'])
    new_merchant = Merchant(
        merchant_name=data['merchant_name'],
        contact_name=data['contact_name'],
        contact_phone=data['contact_phone'],
        password=encrypted_pwd,
        address=data['address'],
        license_img=data.get('license_img', ''),
        food_license_img=data.get('food_license_img', '')
    )
    db.session.add(new_merchant)
    db.session.commit()
    return new_merchant

def merchant_login(phone: str, password: str):
    """商户登录，返回具体错误信息"""
    merchant = Merchant.query.filter_by(contact_phone=phone).first()
    if not merchant:
        return {'error': '用户不存在'}
    if not verify_password(password, merchant.password):
        return {'error': '密码错误'}
    return {
        'token': generate_token(merchant.id, 'merchant'),
        'user_info': {
            'id': merchant.id,
            'name': merchant.merchant_name,
            'status': merchant.status
        }
    }