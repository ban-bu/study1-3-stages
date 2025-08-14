from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageOps
import os
import streamlit as st
import numpy as np
import random

def generate_fabric_texture(image, fabric_type, intensity=0.5):
    """
    生成程序化面料纹理并应用到图像
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型字符串
    intensity - 纹理强度，默认值调整为0.5
    
    返回:
    应用了纹理的图像
    """
    width, height = image.size
    
    # 根据面料类型调整纹理强度
    fabric_intensity = {
        "Cotton": 0.6,         # 棉布纹理较明显
        "Polyester": 0.4,      # 聚酯纤维较平滑
        "Linen": 0.7,          # 亚麻布纹理很明显
        "Jersey": 0.5,         # 针织面料中等纹理
        "Bamboo": 0.55,        # 竹纤维中等偏上
        "Cotton-Polyester Blend": 0.5  # 混纺中等
    }.get(fabric_type, intensity)
    
    # 调整纹理强度系数，确保不会覆盖底色但效果更明显
    actual_intensity = fabric_intensity * 0.35  # 从0.25提高到0.35，增强约40%
    
    # 检测T恤颜色的深浅
    # 取样20个随机点并计算平均亮度
    is_dark_shirt = False
    sample_count = 0
    brightness_sum = 0
    
    for _ in range(100):  # 取100个点的样本
        x = np.random.randint(0, width)
        y = np.random.randint(0, height)
        try:
            pixel = image.getpixel((x, y))
            if len(pixel) == 4:  # RGBA
                r, g, b, a = pixel
                if a > 0 and (r + g + b) / 3 > 60:  # 非边缘且非透明区域
                    brightness_sum += (r + g + b) / 3
                    sample_count += 1
        except:
            continue
    
    # 如果样本数量足够，计算平均亮度
    if sample_count > 20:
        avg_brightness = brightness_sum / sample_count
        # 根据平均亮度决定是否是深色T恤
        is_dark_shirt = avg_brightness < 128
    
    # 创建纹理图像（透明）
    texture = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(texture)
    
    # 根据T恤颜色调整纹理颜色
    # 增强alpha通道值，使纹理效果更明显但仍然适度
    if is_dark_shirt:
        # 深色T恤的纹理颜色 - 使用浅色，适度不透明度
        texture_colors = {
            "Cotton": (220, 220, 220, int(45 * actual_intensity)),      # 增强alpha值
            "Polyester": (230, 230, 230, int(40 * actual_intensity)),   # 增强alpha值
            "Linen": (235, 230, 220, int(50 * actual_intensity)),       # 增强alpha值
            "Jersey": (210, 210, 210, int(50 * actual_intensity)),      # 增强alpha值
            "Bamboo": (225, 225, 215, int(45 * actual_intensity)),      # 增强alpha值
            "default": (220, 220, 220, int(40 * actual_intensity))      # 增强alpha值
        }
    else:
        # 浅色T恤的纹理颜色 - 使用深色，适度不透明度
        texture_colors = {
            "Cotton": (150, 150, 150, int(40 * actual_intensity)),      # 增强alpha值
            "Polyester": (140, 140, 140, int(35 * actual_intensity)),   # 增强alpha值
            "Linen": (160, 155, 145, int(45 * actual_intensity)),       # 增强alpha值
            "Jersey": (140, 140, 140, int(45 * actual_intensity)),      # 增强alpha值
            "Bamboo": (180, 180, 170, int(40 * actual_intensity)),      # 增强alpha值
            "default": (160, 160, 160, int(35 * actual_intensity))      # 增强alpha值
        }
    
    # 获取当前面料的纹理颜色
    texture_color = texture_colors.get(fabric_type, texture_colors["default"])
    
    # 根据面料类型生成不同的纹理
    if fabric_type == "Cotton":
        # 棉布：密集随机点模式
        for _ in range(width * height // 50):  # 增加点的数量
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 4)  # 增加最大点大小
            draw.ellipse([x, y, x+size, y+size], fill=texture_color)
            
    elif fabric_type == "Polyester":
        # 聚酯纤维：更多光滑的纹理线条
        for _ in range(width // 2):  # 增加线条数量
            x1 = np.random.randint(0, width)
            y1 = np.random.randint(0, height)
            x2 = x1 + np.random.randint(-30, 30)
            y2 = y1 + np.random.randint(-30, 30)
            draw.line([x1, y1, x2, y2], fill=texture_color, width=1)
    
    elif fabric_type == "Linen":
        # 亚麻布：更明显的交叉纹理线
        for i in range(0, width, 4):  # 减小间距增加密度
            draw.line([i, 0, i, height], fill=texture_color, width=1)
        for i in range(0, height, 4):
            draw.line([0, i, width, i], fill=texture_color, width=1)
    
    elif fabric_type == "Jersey":
        # 针织面料：更密集的网格
        for y in range(0, height, 3):  # 减小间距
            for x in range(0, width, 3):
                if (x + y) % 6 == 0:  # 增加点的密度
                    size = 2  # 增加点的大小
                    draw.ellipse([x, y, x+size, y+size], fill=texture_color)
    
    elif fabric_type == "Bamboo":
        # 竹纤维：更明显的竖条纹
        for i in range(0, width, 6):  # 减小间距
            draw.line([i, 0, i, height], fill=texture_color, width=2)
            # 添加一些水平的细线
            if i % 18 == 0:
                for j in range(0, height, 20):
                    draw.line([0, j, width, j], fill=texture_color, width=1)
            
    else:  # Cotton-Polyester Blend 或其他
        # 增强混合纹理
        for _ in range(width * height // 100):  # 增加点的数量
            x = np.random.randint(0, width)
            y = np.random.randint(0, height)
            size = np.random.randint(1, 4)
            draw.ellipse([x, y, x+size, y+size], fill=texture_color)
        for i in range(0, width, 10):  # 减小线间距
            draw.line([i, 0, i, height], fill=texture_color, width=1)
    
    # 减少模糊程度，使纹理更加锐利
    texture = texture.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # 创建两个纹理图层，增加视觉深度
    texture2 = texture.copy()
    texture2 = texture2.filter(ImageFilter.GaussianBlur(radius=1.5))
    
    # 创建保存原图像的副本
    result = image.copy()
    
    # ----- 改进的纹理应用方法 -----
    # 使用多阶段纹理应用，确保边缘保留清晰
    
    # 1. 识别T恤区域（非透明部分）和边缘区域（暗色区域）
    # 创建三个掩码: 
    # - 整个T恤区域的掩码
    # - 边缘区域的掩码
    # - 只有面料（非边缘）区域的掩码
    tshirt_mask = Image.new("L", (width, height), 0)  # 整个T恤
    edge_mask = Image.new("L", (width, height), 0)    # 边缘
    fabric_mask = Image.new("L", (width, height), 0)  # 面料区域
    
    tshirt_draw = ImageDraw.Draw(tshirt_mask)
    edge_draw = ImageDraw.Draw(edge_mask)
    fabric_draw = ImageDraw.Draw(fabric_mask)
    
    # 边缘检测参数
    edge_threshold = 40  # 更低的值能更好地捕捉边缘
    fabric_threshold = 100  # 明确的面料区域
    
    # 扫描图像以识别不同区域
    for y in range(height):
        for x in range(width):
            try:
                pixel = image.getpixel((x, y))
                if len(pixel) == 4:  # RGBA
                    r, g, b, a = pixel
                    if a > 0:  # 非透明像素 - T恤区域
                        brightness = (r + g + b) / 3
                        
                        # 整个T恤区域掩码
                        tshirt_draw.point((x, y), fill=255)
                        
                        # 边缘区域 - 暗色
                        if brightness <= edge_threshold:
                            edge_draw.point((x, y), fill=255)
                        
                        # 面料区域 - 非边缘
                        if brightness > edge_threshold:
                            # 根据亮度调整纹理强度
                            # 对于深色T恤，增加纹理强度
                            if is_dark_shirt:
                                intensity_factor = min(1.0, 0.7 + brightness / 500)  # 确保深色T恤的纹理较强
                            else:
                                intensity_factor = min(1.0, brightness / 255)
                            fabric_draw.point((x, y), fill=int(255 * intensity_factor))
                else:  # RGB
                    r, g, b = pixel
                    brightness = (r + g + b) / 3
                    
                    # 同样处理RGB像素
                    tshirt_draw.point((x, y), fill=255)
                    
                    if brightness <= edge_threshold:
                        edge_draw.point((x, y), fill=255)
                    
                    if brightness > edge_threshold:
                        # 对于深色T恤，增加纹理强度
                        if is_dark_shirt:
                            intensity_factor = min(1.0, 0.7 + brightness / 500)
                        else:
                            intensity_factor = min(1.0, brightness / 255)
                        fabric_draw.point((x, y), fill=int(255 * intensity_factor))
            except:
                continue
    
    # 扩大边缘区域，确保边缘完全被保护
    edge_mask = edge_mask.filter(ImageFilter.MaxFilter(3))
    
    # 确保面料区域不包含边缘区域
    for y in range(height):
        for x in range(width):
            if edge_mask.getpixel((x, y)) > 0:
                fabric_draw.point((x, y), fill=0)
    
    # 2. 仅将纹理应用于面料区域
    # 为了更好的视觉效果，稍微模糊面料掩码以平滑过渡
    fabric_mask = fabric_mask.filter(ImageFilter.GaussianBlur(radius=1))
    
    # 修改纹理应用方式 - 使用加法混合模式而非直接替换
    # 创建一个临时数组来存储原始图像颜色
    original_data = np.array(result)
    
    # 创建一个临时图像进行纹理应用
    temp_result = result.copy()
    temp_result.paste(texture, (0, 0), fabric_mask)
    texture_data = np.array(temp_result)
    
    # 计算混合后的图像数据 - 减少原始颜色保留比例，使纹理更明显
    blend_factor = 0.9  # 保留90%的原始颜色，使用10%的纹理效果
    
    # 对强度较低的像素使用不同的混合策略，保留更多颜色信息
    final_image_data = np.zeros_like(original_data)
    for i in range(3):  # RGB通道
        # 使用亮度增强的混合模式
        # 这使纹理更像是"叠加"在原有颜色上，而不是取代它
        final_image_data[:,:,i] = np.clip(
            original_data[:,:,i] * blend_factor + 
            texture_data[:,:,i] * (1 - blend_factor) * 0.9,  # 将纹理贡献从0.8提升到0.9
            0, 255
        ).astype(np.uint8)
    
    # 确保alpha通道保持不变
    final_image_data[:,:,3] = original_data[:,:,3]
    
    # 创建最终图像
    result = Image.fromarray(final_image_data)
    
    # 确保边缘保持完全不变
    # 获取原始图像的边缘部分
    edge_region = image.copy()
    
    # 将原始边缘区域粘贴回结果图像，完全覆盖可能受到纹理影响的边缘
    result.paste(edge_region, (0, 0), edge_mask)
    
    return result

# 导出apply_fabric_texture函数作为主接口，使用程序生成的纹理
def apply_fabric_texture(image, fabric_type, intensity=0.5):
    """
    应用面料纹理到T恤图像的主接口函数
    
    参数:
    image - PIL图像对象
    fabric_type - 面料类型
    intensity - 纹理强度，默认值调整为0.5
    """
    try:
        # 确保输入图像为RGBA模式
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        
        # 创建一个透明度掩码，只对非透明区域应用纹理
        width, height = image.size
        alpha_mask = Image.new("L", (width, height), 0)
        
        # 设置透明度掩码 - 只在非透明区域应用纹理
        for y in range(height):
            for x in range(width):
                pixel = image.getpixel((x, y))
                if len(pixel) == 4 and pixel[3] > 0:  # 非完全透明区域
                    alpha_mask.putpixel((x, y), 255)
        
        # 生成纹理
        textured_image = generate_fabric_texture(image, fabric_type, intensity)
        
        # 创建最终图像
        final_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        
        # 使用alpha掩码组合原图与纹理图
        for y in range(height):
            for x in range(width):
                orig_pixel = image.getpixel((x, y))
                if orig_pixel[3] == 0:  # 完全透明区域保持不变
                    final_image.putpixel((x, y), (0, 0, 0, 0))
                else:  # 非透明区域使用纹理图像
                    textured_pixel = textured_image.getpixel((x, y))
                    final_image.putpixel((x, y), textured_pixel)
        
        return final_image
    except Exception as e:
        st.error(f"应用纹理时出错: {e}")
        return image  # 如果出错，返回原始图像
