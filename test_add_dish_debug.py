import requests
import json

# 测试添加菜品功能，显示详细错误信息
base_url = "http://121.48.197.187:5000"

# 首先需要创建一个商户账号
def test_merchant_register():
    """测试商户注册"""
    url = f"{base_url}/api/merchant/register"
    
    # 准备表单数据
    import random
    phone_number = f"138{random.randint(10000000, 99999999):08d}"
    data = {
        'merchant_name': '测试商户',
        'contact_name': '测试联系人',
        'contact_phone': phone_number,
        'password': '123456',
        'address': '测试地址'
    }
    
    try:
        response = requests.post(url, data=data)
        print("注册响应:", response.status_code)
        print("注册响应内容:", response.text)
        
        if response.status_code == 200:
            result = response.json()
            if result['code'] == 200:
                print("✅ 商户注册成功")
                return phone_number  # 返回手机号供后续使用
        return None
    except Exception as e:
        print(f"注册失败: {e}")
        return None

# 测试商户登录
def test_merchant_login(phone_number):
    """测试商户登录"""
    url = f"{base_url}/api/merchant/login"
    data = {
        "phone": phone_number,  # 使用刚注册的商户手机号
        "password": "123456"
    }
    
    try:
        response = requests.post(url, json=data)
        print("登录响应状态码:", response.status_code)
        print("登录响应内容:", response.text)
        
        if response.status_code == 200:
            result = response.json()
            if result['code'] == 200:
                print("✅ 登录成功")
                return result['data']['token']
        return None
    except Exception as e:
        print(f"登录失败: {e}")
        return None

def test_add_dish(token):
    """测试添加菜品"""
    url = f"{base_url}/api/merchant/dish/add"
    
    # 准备表单数据
    data = {
        'dish_name': '测试菜品',
        'price': '25.5',
        'category': '快餐',
        'stock': '10',
        'description': '这是一个测试菜品'
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    try:
        response = requests.post(url, data=data, headers=headers)
        print("添加菜品响应状态码:", response.status_code)
        print("添加菜品响应内容:", response.text)
        
        if response.status_code == 200:
            result = response.json()
            if result['code'] == 200:
                print("✅ 添加菜品成功")
                return True
            else:
                print(f"❌ 添加菜品失败: {result['msg']}")
                return False
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 添加菜品异常: {e}")
        return False

# 运行测试
if __name__ == "__main__":
    print("开始测试添加菜品功能...")
    
    # 先注册商户
    print("\n1. 测试商户注册...")
    phone_number = test_merchant_register()
    
    if phone_number:
        # 测试登录
        print("\n2. 测试商户登录...")
        token = test_merchant_login(phone_number)
        
        if token:
            print(f"登录成功，token: {token[:20]}...")
            
            # 测试添加菜品
            print("\n3. 测试添加菜品...")
            success = test_add_dish(token)
            
            if success:
                print("\n✅ 添加菜品功能正常")
            else:
                print("\n❌ 添加菜品功能异常")
        else:
            print("\n❌ 登录失败，无法测试添加菜品功能")
    else:
        print("\n❌ 商户注册失败，无法继续测试")