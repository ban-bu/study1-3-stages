"""
实用工具函数模块
包含文件路径处理和其他共享功能
"""

import os

def get_resource_path(filename):
    """
    获取资源文件的完整路径，支持多种可能的位置
    
    Args:
        filename (str): 文件名
        
    Returns:
        str: 文件的完整路径
    """
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    possible_paths = [
        os.path.join(current_dir, filename),
        os.path.join(current_dir, "assets", filename),
        os.path.join(current_dir, "images", filename),
        os.path.join(current_dir, "static", filename),
        filename  # 相对路径作为后备
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 如果都找不到，返回原始文件名
    return filename

def get_base_shirt_path():
    """
    获取基础T恤图片的路径
    
    Returns:
        str: white_shirt.png的完整路径
    """
    return get_resource_path("white_shirt.png")
