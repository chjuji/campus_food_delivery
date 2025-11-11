import os
from config import Config

def allowed_file(filename: str) -> bool:
    """检查文件格式是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def save_file(file, folder_type: str) -> str:
    """保存上传的文件，返回文件路径"""
    if not allowed_file(file.filename):
        raise ValueError("不支持的文件格式")
    
    # 生成唯一文件名
    filename = f"{os.urandom(16).hex()}.{file.filename.rsplit('.', 1)[1].lower()}"
    folder = Config.UPLOAD_FOLDER.get(folder_type)
    if not folder:
        raise ValueError("无效的文件夹类型")
    
    file_path = os.path.join(folder, filename)
    file.save(file_path)
    return f"uploads/{folder_type}/{filename}"  # 返回相对路径