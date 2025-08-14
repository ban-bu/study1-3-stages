import streamlit as st
from PIL import Image, ImageDraw
import requests
from io import BytesIO
import os  # 确保os模块在这里导入
# 移除cairosvg依赖，使用svglib作为唯一的SVG处理库
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVGLIB_AVAILABLE = True
except ImportError:
    SVGLIB_AVAILABLE = False
    st.warning("SVG processing libraries not installed, SVG conversion will not be available")
from openai import OpenAI
from streamlit_image_coordinates import streamlit_image_coordinates
import re
import math
# 导入面料纹理模块
from fabric_texture import apply_fabric_texture
import uuid
import json
# 导入并行处理库
import concurrent.futures
import time
import threading
# 导入阿里云DashScope文生图API
from http import HTTPStatus
from urllib.parse import urlparse, unquote
from pathlib import PurePosixPath
try:
    from dashscope import ImageSynthesis
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    st.warning("DashScope not installed, will use OpenAI DALL-E as fallback")

# API配置信息 - 多个API密钥用于增强并发能力
API_KEYS = [
    "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg",
    "sk-y8x6LH0zdtyQncT0aYdUW7eJZ7v7cuKTp90L7TiK3rPu3fAg", 
    "sk-Kp59pIj8PfqzLzYaAABh2jKsQLB0cUKU3n8l7TIK3rpU61QG",
    "sk-KACPocnavR6poutXUaj7HxsqUrxvcV808S2bv0U9974Ec83g",
    "sk-YknuN0pb6fKBOP6xFOqAdeeqhoYkd1cEl9380vC5HHeC2B30"
]
BASE_URL = "https://api.deepbricks.ai/v1/"

# GPT-4o-mini API配置 - 同样使用多个密钥
GPT4O_MINI_API_KEYS = [
    "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg",
    "sk-y8x6LH0zdtyQncT0aYdUW7eJZ7v7cuKTp90L7TiK3rPu3fAg",
    "sk-Kp59pIj8PfqzLzYaAABh2jKsQLB0cUKU3n8l7TIK3rpU61QG", 
    "sk-KACPocnavR6poutXUaj7HxsqUrxvcV808S2bv0U9974Ec83g",
    "sk-YknuN0pb6fKBOP6xFOqAdeeqhoYkd1cEl9380vC5HHeC2B30"
]
GPT4O_MINI_BASE_URL = "https://api.deepbricks.ai/v1/"

# 阿里云DashScope API配置
DASHSCOPE_API_KEY = "sk-4f82c6e2097440f8adb2ef688c7c7551"

# API密钥轮询计数器
_api_key_counter = 0
_gpt4o_api_key_counter = 0
_api_lock = threading.Lock()

def get_next_api_key():
    """获取下一个DALL-E API密钥（轮询方式）"""
    global _api_key_counter
    with _api_lock:
        key = API_KEYS[_api_key_counter % len(API_KEYS)]
        _api_key_counter += 1
        return key

def get_next_gpt4o_api_key():
    """获取下一个GPT-4o-mini API密钥（轮询方式）"""
    global _gpt4o_api_key_counter
    with _api_lock:
        key = GPT4O_MINI_API_KEYS[_gpt4o_api_key_counter % len(GPT4O_MINI_API_KEYS)]
        _gpt4o_api_key_counter += 1
        return key

def make_background_transparent(image, threshold=100):
    """
    将图像的白色/浅色背景转换为透明背景
    
    Args:
        image: PIL图像对象，RGBA模式
        threshold: 背景色识别阈值，数值越大识别的背景范围越大
    
    Returns:
        处理后的PIL图像对象，透明背景
    """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # 获取图像数据
    data = image.getdata()
    new_data = []
    
    # 分析四个角落的颜色来确定背景色
    width, height = image.size
    corner_pixels = [
        image.getpixel((0, 0)),           # 左上角
        image.getpixel((width-1, 0)),     # 右上角
        image.getpixel((0, height-1)),    # 左下角
        image.getpixel((width-1, height-1)) # 右下角
    ]
    
    # 计算平均背景颜色（假设四个角都是背景）
    bg_r = sum(p[0] for p in corner_pixels) // 4
    bg_g = sum(p[1] for p in corner_pixels) // 4
    bg_b = sum(p[2] for p in corner_pixels) // 4
    
    print(f"检测到的背景颜色: RGB({bg_r}, {bg_g}, {bg_b})")
    
    # 遍历所有像素
    transparent_count = 0
    for item in data:
        r, g, b, a = item
        
        # 计算当前像素与背景色的差异
        diff = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
        
        # 另外检查是否是浅色（可能是背景）
        brightness = (r + g + b) / 3
        is_light = brightness > 180  # 亮度大于180认为是浅色
        
        # 检查是否接近灰白色
        gray_similarity = abs(r - g) + abs(g - b) + abs(r - b)
        is_grayish = gray_similarity < 30  # 颜色差异小说明是灰色系
        
        # 如果差异小于阈值或者是浅色灰白色，认为是背景，设为透明
        if diff < threshold or (is_light and is_grayish):
            new_data.append((r, g, b, 0))  # 完全透明
            transparent_count += 1
        else:
            # 否则保持原像素
            new_data.append((r, g, b, a))
    
    print(f"透明化了 {transparent_count} 个像素，占总像素的 {transparent_count/(image.size[0]*image.size[1])*100:.1f}%")
    
    # 创建新图像
    transparent_image = Image.new('RGBA', image.size)
    transparent_image.putdata(new_data)
    
    return transparent_image

# 自定义SVG转PNG函数，不依赖外部库
def convert_svg_to_png(svg_content):
    """
    将SVG内容转换为PNG格式的PIL图像对象
    使用svglib库来处理，不再依赖cairosvg
    """
    try:
        if SVGLIB_AVAILABLE:
            # 使用svglib将SVG内容转换为PNG
            from io import BytesIO
            svg_bytes = BytesIO(svg_content)
            drawing = svg2rlg(svg_bytes)
            png_bytes = BytesIO()
            renderPM.drawToFile(drawing, png_bytes, fmt="PNG")
            png_bytes.seek(0)
            return Image.open(png_bytes).convert("RGBA")
        else:
            st.error("SVG conversion libraries not available. Please install svglib and reportlab.")
            return None
    except Exception as e:
        st.error(f"Error converting SVG to PNG: {str(e)}")
        return None

# 设置三种推荐级别的配置
RECOMMENDATION_CONDITIONS = {
    "low": {"count": 1, "name": "Low Recommendation"},
    "medium": {"count": 5, "name": "Medium Recommendation"},
    "high": {"count": 10, "name": "High Recommendation"}
}

# 条件顺序（每个参与者依次体验这三种条件）
CONDITION_ORDER = ["low", "medium", "high"]

def get_ai_design_suggestions(user_preferences=None):
    """Get design suggestions from GPT-4o-mini with more personalized features"""
    client = OpenAI(api_key=get_next_gpt4o_api_key(), base_url=GPT4O_MINI_BASE_URL)
    
    # Default prompt if no user preferences provided
    if not user_preferences:
        user_preferences = "casual fashion t-shirt design"
    
    # Construct the prompt
    prompt = f"""
    As a design consultant, please provide personalized design suggestions for a "{user_preferences}" style.
    
    Please provide the following design suggestions in JSON format:

    1. Color: Select the most suitable color for this style (provide name and hex code)
    2. Fabric: Select the most suitable fabric type (Cotton, Polyester, Cotton-Polyester Blend, Jersey, Linen, or Bamboo)
    3. Text: A suitable phrase or slogan that matches the style (keep it concise and impactful)
    4. Logo: A brief description of a logo element that would complement the design

    Return your response as a valid JSON object with the following structure:
    {{
        "color": {{
            "name": "Color name",
            "hex": "#XXXXXX"
        }},
        "fabric": "Fabric type",
        "text": "Suggested text or slogan",
        "logo": "Logo/graphic description"
    }}
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional design consultant. Provide design suggestions in JSON format exactly as requested."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 查找JSON格式的内容
                json_match = re.search(r'```json\s*(.*?)\s*```', suggestion_text, re.DOTALL)
                if json_match:
                    suggestion_json = json.loads(json_match.group(1))
                else:
                    # 尝试直接解析整个内容
                    suggestion_json = json.loads(suggestion_text)
                
                return suggestion_json
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return {"error": f"Failed to parse design suggestions: {str(e)}"}
        else:
            return {"error": "Failed to get AI design suggestions. Please try again later."}
    except Exception as e:
        return {"error": f"Error getting AI design suggestions: {str(e)}"}

def generate_vector_image(prompt, background_color=None):
    """Generate a vector-style logo with transparent background using DashScope API"""
    
    # 构建矢量图logo专用的提示词
    vector_style_prompt = f"""创建一个矢量风格的logo设计: {prompt}
    要求:
    1. 简洁的矢量图风格，线条清晰
    2. 必须是透明背景，不能有任何白色或彩色背景
    3. 专业的logo设计，适合印刷到T恤上
    4. 高对比度，颜色鲜明
    5. 几何形状简洁，不要过于复杂
    6. 不要包含文字或字母
    7. 不要显示T恤或服装模型
    8. 纯粹的图形标志设计
    9. 矢量插画风格，扁平化设计
    10. 重要：背景必须完全透明，不能有任何颜色填充
    11. 请生成PNG格式的透明背景图标
    12. 图标应该是独立的，没有任何背景元素"""
    

    
    # 优先使用DashScope API
    if DASHSCOPE_AVAILABLE:
        try:
            print(f'----使用DashScope生成矢量logo，提示词: {vector_style_prompt}----')
            rsp = ImageSynthesis.call(
                api_key=DASHSCOPE_API_KEY,
                model="wanx2.0-t2i-turbo",
                prompt=vector_style_prompt,
                n=1,
                size='1024*1024'
            )
            print('DashScope响应: %s' % rsp)
            
            if rsp.status_code == HTTPStatus.OK:
                # 下载生成的图像
                for result in rsp.output.results:
                    image_resp = requests.get(result.url)
                    if image_resp.status_code == 200:
                        # 加载图像并转换为RGBA模式
                        img = Image.open(BytesIO(image_resp.content)).convert("RGBA")
                        print(f"DashScope生成的logo尺寸: {img.size}")
                        
                        # 后处理：将白色背景转换为透明（使用更高的阈值）
                        img_processed = make_background_transparent(img, threshold=120)
                        print(f"背景透明化处理完成")
                        return img_processed
                    else:
                        st.error(f"下载图像失败, 状态码: {image_resp.status_code}")
            else:
                print('DashScope调用失败, status_code: %s, code: %s, message: %s' %
                      (rsp.status_code, rsp.code, rsp.message))
                st.error(f"DashScope API调用失败: {rsp.message}")
                
        except Exception as e:
            st.error(f"DashScope API调用错误: {e}")
            print(f"DashScope错误: {e}")
    
    # 如果DashScope不可用，直接返回None
    if not DASHSCOPE_AVAILABLE:
        st.error("DashScope API不可用，无法生成logo。请确保已正确安装dashscope库。")
        return None
    
    # DashScope失败时也直接返回None，不使用备选方案
    st.error("DashScope API调用失败，无法生成logo。请检查网络连接或API密钥。")
    return None

def change_shirt_color(image, color_hex, apply_texture=False, fabric_type=None):
    """Change T-shirt color with optional fabric texture"""
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    threshold = 200
    
    for item in data:
        # 判断是否是白色/浅色区域 (RGB值都很高)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold and item[3] > 0:
            # 保持原透明度，改变颜色
            new_color = (color_rgb[0], color_rgb[1], color_rgb[2], item[3])
            new_data.append(new_color)
        else:
            # 保持其他颜色不变
            new_data.append(item)
    
    # 更新图像数据
    colored_image.putdata(new_data)
    
    # 如果需要应用纹理
    if apply_texture and fabric_type:
        return apply_fabric_texture(colored_image, fabric_type)
    
    return colored_image

def apply_text_to_shirt(image, text, color_hex="#FFFFFF", font_size=80):
    """Apply text to T-shirt image"""
    if not text:
        return image
    
    # 创建副本避免修改原图
    result_image = image.copy().convert("RGBA")
    img_width, img_height = result_image.size
    
    # 创建透明的文本图层
    text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    
    # 尝试加载字体
    from PIL import ImageFont
    import platform
    
    font = None
    try:
        system = platform.system()
        
        # 根据不同系统尝试不同的字体路径
        if system == 'Windows':
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/ARIAL.TTF",
                "C:/Windows/Fonts/calibri.ttf",
            ]
        elif system == 'Darwin':  # macOS
            font_paths = [
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        else:  # Linux或其他
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ]
        
        # 尝试加载每个字体
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
    except Exception as e:
        print(f"Error loading font: {e}")
    
    # 如果加载失败，使用默认字体
    if font is None:
        try:
            font = ImageFont.load_default()
        except:
            print("Could not load default font")
            return result_image
    
    # 将十六进制颜色转换为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    text_color = color_rgb + (255,)  # 添加不透明度
    
    # 计算文本位置 (居中)
    text_bbox = text_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = (img_width - text_width) // 2
    text_y = (img_height // 3) - (text_height // 2)  # 放在T恤上部位置
    
    # 绘制文本
    text_draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    # 组合图像
    result_image = Image.alpha_composite(result_image, text_layer)
    
    return result_image

def apply_logo_to_shirt(shirt_image, logo_image, position="center", size_percent=60, background_color=None):
    """Apply logo to T-shirt image with better blending to reduce shadows"""
    if logo_image is None:
        return shirt_image
    
    # 创建副本避免修改原图
    result_image = shirt_image.copy().convert("RGBA")
    img_width, img_height = result_image.size
    
    # 定义T恤前胸区域
    chest_width = int(img_width * 0.95)
    chest_height = int(img_height * 0.6)
    chest_left = (img_width - chest_width) // 2
    chest_top = int(img_height * 0.2)
    
    # 提取logo前景
    logo_with_bg = logo_image.copy().convert("RGBA")
    
    # 调整Logo大小
    logo_size_factor = size_percent / 100
    logo_width = int(chest_width * logo_size_factor * 0.7)
    logo_height = int(logo_width * logo_with_bg.height / logo_with_bg.width)
    logo_resized = logo_with_bg.resize((logo_width, logo_height), Image.LANCZOS)
    
    # 根据位置确定坐标
    position = position.lower() if isinstance(position, str) else "center"
    
    if position == "top-center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + 10
    elif position == "center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30  # 略微偏下
    else:  # 默认中间
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30
    
    # 对于透明背景的logo，直接使用alpha通道作为蒙版
    if logo_resized.mode == 'RGBA':
        # 使用alpha通道作为蒙版
        logo_mask = logo_resized.split()[-1]  # 获取alpha通道
        print(f"使用RGBA模式logo的alpha通道作为蒙版")
    else:
        # 如果不是RGBA模式，创建传统的基于颜色差异的蒙版
        logo_mask = Image.new("L", logo_resized.size, 0)  # 创建一个黑色蒙版（透明）
        
        # 如果提供了背景颜色，使用它来判断什么是背景
        if background_color:
            bg_color_rgb = tuple(int(background_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        else:
            # 默认假设白色是背景
            bg_color_rgb = (255, 255, 255)
        
        # 遍历像素，创建蒙版
        for y in range(logo_resized.height):
            for x in range(logo_resized.width):
                pixel = logo_resized.getpixel((x, y))
                if len(pixel) >= 3:  # 至少有RGB值
                    # 计算与背景颜色的差异
                    r_diff = abs(pixel[0] - bg_color_rgb[0])
                    g_diff = abs(pixel[1] - bg_color_rgb[1])
                    b_diff = abs(pixel[2] - bg_color_rgb[2])
                    diff = r_diff + g_diff + b_diff
                    
                    # 如果差异大于阈值，则认为是前景
                    if diff > 60:  # 可以调整阈值
                        # 根据差异程度设置不同的透明度
                        transparency = min(255, diff)
                        logo_mask.putpixel((x, y), transparency)
    
    # 对于透明背景的logo，使用PIL的alpha合成功能
    if logo_resized.mode == 'RGBA':
        # 检查logo是否真的有透明像素
        has_transparency = False
        for pixel in logo_resized.getdata():
            if len(pixel) == 4 and pixel[3] < 255:  # 有alpha通道且不完全不透明
                has_transparency = True
                break
        
        print(f"Logo模式: {logo_resized.mode}, 有透明像素: {has_transparency}")
        
        if has_transparency:
            # 直接使用PIL的alpha合成，这样处理透明背景更准确
            print(f"将透明背景logo应用到T恤位置: ({logo_x}, {logo_y})")
            result_image.paste(logo_resized, (logo_x, logo_y), logo_resized)
        else:
            # 如果没有透明像素，先处理背景透明化
            print("Logo没有透明像素，进行背景透明化处理")
            transparent_logo = make_background_transparent(logo_resized, threshold=120)
            result_image.paste(transparent_logo, (logo_x, logo_y), transparent_logo)
    else:
        # 对于非透明背景的logo，使用传统的像素级混合方法
        shirt_region = result_image.crop((logo_x, logo_y, logo_x + logo_width, logo_y + logo_height))
        
        # 合成logo和T恤区域，使用蒙版确保只有logo的非背景部分被使用
        for y in range(logo_height):
            for x in range(logo_width):
                mask_value = logo_mask.getpixel((x, y))
                if mask_value > 20:  # 有一定的不透明度
                    # 获取logo像素
                    logo_pixel = logo_resized.getpixel((x, y))
                    # 获取T恤对应位置的像素
                    shirt_pixel = shirt_region.getpixel((x, y))
                    
                    # 根据透明度混合像素
                    alpha = mask_value / 255.0
                    blended_pixel = (
                        int(logo_pixel[0] * alpha + shirt_pixel[0] * (1 - alpha)),
                        int(logo_pixel[1] * alpha + shirt_pixel[1] * (1 - alpha)),
                        int(logo_pixel[2] * alpha + shirt_pixel[2] * (1 - alpha)),
                        255  # 完全不透明
                    )
                    
                    # 更新T恤区域的像素
                    shirt_region.putpixel((x, y), blended_pixel)
        
        # 将修改后的区域粘贴回T恤
        result_image.paste(shirt_region, (logo_x, logo_y))
    
    return result_image

def generate_complete_design(design_prompt, variation_id=None):
    """Generate complete T-shirt design based on prompt"""
    if not design_prompt:
        return None, {"error": "Please enter a design prompt"}
    
    # 获取AI设计建议
    design_suggestions = get_ai_design_suggestions(design_prompt)
    
    if "error" in design_suggestions:
        return None, design_suggestions
    
    # 加载原始T恤图像
    try:
        from utils import get_base_shirt_path
        original_image_path = get_base_shirt_path()
        
        if not os.path.exists(original_image_path):
            return None, {"error": "Could not find base T-shirt image"}
        
        # 加载原始白色T恤图像
        original_image = Image.open(original_image_path).convert("RGBA")
    except Exception as e:
        return None, {"error": f"Error loading T-shirt image: {str(e)}"}
    
    try:
        # 使用AI建议的颜色和面料
        color_hex = design_suggestions.get("color", {}).get("hex", "#FFFFFF")
        color_name = design_suggestions.get("color", {}).get("name", "Custom Color")
        fabric_type = design_suggestions.get("fabric", "Cotton")
        
        # 1. 应用颜色和纹理
        colored_shirt = change_shirt_color(
            original_image,
            color_hex,
            apply_texture=True,
            fabric_type=fabric_type
        )
        
        # 2. 生成Logo
        logo_description = design_suggestions.get("logo", "")
        logo_image = None
        
        if logo_description:
            # 修改Logo提示词，生成透明背景的矢量图logo
            logo_prompt = f"""Create a professional vector logo design: {logo_description}. 
            Requirements: 
            1. Simple professional design
            2. IMPORTANT: Transparent background (PNG format)
            3. Clear and distinct graphic with high contrast
            4. Vector-style illustration suitable for T-shirt printing
            5. Must not include any text, numbers or color name, only logo graphic
            6. IMPORTANT: Do NOT include any mockups or product previews
            7. IMPORTANT: Create ONLY the logo graphic itself
            8. NO META REFERENCES - do not show the logo applied to anything
            9. Design should be a standalone graphic symbol/icon only
            10. CRITICAL: Clean vector art style with crisp lines and solid colors"""
            
            # 生成透明背景的矢量logo
            logo_image = generate_vector_image(logo_prompt)
        
        # 最终设计 - 不添加文字
        final_design = colored_shirt
        
        # 应用Logo (如果有)
        if logo_image:
            # 应用透明背景的logo到T恤
            final_design = apply_logo_to_shirt(colored_shirt, logo_image, "center", 60)
        
        return final_design, {
            "color": {"hex": color_hex, "name": color_name},
            "fabric": fabric_type,
            "logo": logo_description,
            "design_index": 0 if variation_id is None else variation_id  # 使用design_index替代variation_id
        }
    
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        return None, {"error": f"Error generating design: {str(e)}\n{traceback_str}"}

def generate_single_design(design_index):
    try:
        # 为每个设计添加轻微的提示词变化，确保设计多样性
        design_variations = [
            "",  # 原始提示词
            "modern and minimalist",
            "colorful and vibrant",
            "vintage and retro",
            "elegant and simple"
        ]
        
        # 选择合适的变化描述词
        variation_desc = ""
        if design_index < len(design_variations):
            variation_desc = design_variations[design_index]
        
        # 创建变化的提示词
        if variation_desc:
            # 将变化描述词添加到原始提示词
            varied_prompt = f"{design_prompt}, {variation_desc}"
        else:
            varied_prompt = design_prompt
        
        # 完整的独立流程 - 每个设计独立获取AI建议、生成图片，确保颜色一致性
        # 使用独立提示词生成完全不同的设计
        design, info = generate_complete_design(varied_prompt)
        
        # 添加设计索引到信息中以便排序
        if info and isinstance(info, dict):
            info["design_index"] = design_index
        
        return design, info
    except Exception as e:
        print(f"Error generating design {design_index}: {e}")
        return None, {"error": f"Failed to generate design {design_index}"}

def generate_multiple_designs(design_prompt, count=1):
    """Generate multiple T-shirt designs in parallel - independent designs rather than variations"""
    if count <= 1:
        # If only one design is needed, generate directly without parallel processing
        base_design, base_info = generate_complete_design(design_prompt)
        if base_design:
            return [(base_design, base_info)]
        else:
            return []
    
    designs = []
    
    # Create thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(count, 5)) as executor:
        # Submit all tasks
        future_to_id = {executor.submit(generate_single_design, i): i for i in range(count)}
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_id):
            design_id = future_to_id[future]
            try:
                design, info = future.result()
                if design:
                    designs.append((design, info))
            except Exception as e:
                print(f"Design {design_id} generated an exception: {e}")
    
    # Sort by design index
    designs.sort(key=lambda x: x[1].get("design_index", 0) if x[1] and "design_index" in x[1] else 0)
    
    return designs

def show_high_recommendation_without_explanation():
    st.title("👕 AI Recommendation Experiment Platform")
    st.markdown("### Study1-Let AI Design Your T-shirt")
    
    # 初始化会话状态变量
    if 'user_prompt' not in st.session_state:
        st.session_state.user_prompt = ""
    if 'final_design' not in st.session_state:
        st.session_state.final_design = None
    if 'design_info' not in st.session_state:
        st.session_state.design_info = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
    if 'should_generate' not in st.session_state:
        st.session_state.should_generate = False
    
    # Condition management state variables
    if 'current_condition_index' not in st.session_state:
        st.session_state.current_condition_index = 0
    if 'current_condition' not in st.session_state:
        st.session_state.current_condition = CONDITION_ORDER[0]
    if 'completed_conditions' not in st.session_state:
        st.session_state.completed_conditions = []
    
    if 'generated_designs' not in st.session_state:
        st.session_state.generated_designs = []
    if 'selected_design_index' not in st.session_state:
        st.session_state.selected_design_index = 0
    
    # Get current condition information
    current_condition = st.session_state.current_condition
    current_config = RECOMMENDATION_CONDITIONS[current_condition]
    condition_progress = st.session_state.current_condition_index + 1
    total_conditions = len(CONDITION_ORDER)
    
    # Display experiment progress and current condition information
    st.markdown(f"""
    <div style="padding: 15px; background-color: #e3f2fd; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #2196f3;">
    <h4 style="margin: 0 0 10px 0; color: #1976d2;">Experiment Progress: {condition_progress}/{total_conditions}</h4>
    <p style="margin: 0; font-size: 16px;"><strong>Current Condition:</strong> {current_config['name']} - AI will generate {current_config['count']} T-shirt design options for you</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display completed conditions
    if st.session_state.completed_conditions:
        completed_text = ", ".join([RECOMMENDATION_CONDITIONS[cond]['name'] for cond in st.session_state.completed_conditions])
        st.markdown(f"""
        <div style="padding: 10px; background-color: #e8f5e8; border-radius: 5px; margin-bottom: 15px;">
        <p style="margin: 0; color: #2e7d32;"><strong>✅ Completed Conditions:</strong> {completed_text}</p>
        </div>
        """, unsafe_allow_html=True)
    if 'original_tshirt' not in st.session_state:
        # Load original white T-shirt image
        try:
            from utils import get_base_shirt_path
            original_image_path = get_base_shirt_path()
            
            if os.path.exists(original_image_path):
                st.session_state.original_tshirt = Image.open(original_image_path).convert("RGBA")
            else:
                st.error("Could not find base T-shirt image")
                st.session_state.original_tshirt = None
        except Exception as e:
            st.error(f"Error loading T-shirt image: {str(e)}")
            st.session_state.original_tshirt = None
    
    # Create two-column layout
    design_col, input_col = st.columns([3, 2])
    
    with design_col:
        # Create placeholder area for T-shirt design display
        design_area = st.empty()
        
        # Display current T-shirt design status in design area
        if st.session_state.final_design is not None:
            with design_area.container():
                st.markdown("### Your Custom T-shirt Design")
                st.image(st.session_state.final_design, use_container_width=True)
        elif len(st.session_state.generated_designs) > 0:
            with design_area.container():
                st.markdown("### Generated Design Options")
                
                # Create multiple columns to display designs
                design_count = len(st.session_state.generated_designs)
                if design_count > 3:
                    # Display in two rows
                    row1_cols = st.columns(min(3, design_count))
                    row2_cols = st.columns(min(3, max(0, design_count - 3)))
                    
                    # Display first row
                    for i in range(min(3, design_count)):
                        with row1_cols[i]:
                            design, _ = st.session_state.generated_designs[i]
                            st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            # Display design
                            st.image(design, use_container_width=True)
                    
                    # Display second row
                    for i in range(3, design_count):
                        with row2_cols[i-3]:
                            design, _ = st.session_state.generated_designs[i]
                            st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            # Display design
                            st.image(design, use_container_width=True)
                else:
                    # Display in single row
                    cols = st.columns(design_count)
                    for i in range(design_count):
                        with cols[i]:
                            design, _ = st.session_state.generated_designs[i]
                            st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            # Display design
                            st.image(design, use_container_width=True)
                

        else:
            # Display original blank T-shirt
            with design_area.container():
                st.markdown("### T-shirt Design Preview")
                if st.session_state.original_tshirt is not None:
                    st.image(st.session_state.original_tshirt, use_container_width=True)
                else:
                    st.info("Could not load original T-shirt image, please refresh the page")
    
    with input_col:
        # Design prompt and recommendation level selection area
        st.markdown("### Design Options")
        
        # # Remove recommendation level selection button and display current level information instead
        # if DEFAULT_DESIGN_COUNT == 1:
        #     level_text = "Low - will generate 1 design"
        # elif DEFAULT_DESIGN_COUNT == 3:
        #     level_text = "Medium - will generate 3 designs"
        # else:  # 5 or other values
        #     level_text = "High - will generate 5 designs"
            
        # st.markdown(f"""
        # <div style="padding: 10px; background-color: #f0f2f6; border-radius: 5px; margin-bottom: 20px;">
        # <p style="margin: 0; font-size: 16px; font-weight: bold;">Current recommendation level: {level_text}</p>
        # </div>
        # """, unsafe_allow_html=True)
        
        # Prompt input area
        st.markdown("#### Describe your desired T-shirt design:")
        
        # Add brief description
        st.markdown(f"""
        <div style="margin-bottom: 15px; padding: 10px; background-color: #f0f2f6; border-radius: 5px;">
        <p style="margin: 0; font-size: 14px;">Enter keyword to describe your ideal T-shirt design. In this condition, AI will generate {current_config['count']} design options for you.</p>
        <p style="margin: 5px 0 0 0; font-size: 13px; color: #666;">
        <strong>Experiment Instructions:</strong> You need to experience three different recommendation levels (Low: 1, Medium: 5, High: 10 designs) in sequence. Please try generating designs at least once for each condition.
        </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Initialize keywords state
        if 'keywords' not in st.session_state:
            st.session_state.keywords = ""
        
        # Keywords input box
        keywords = st.text_input("Enter design keyword", value=st.session_state.keywords, 
                              placeholder="please only input one word", key="input_keywords")
        
        # Generate design button
        generate_col = st.empty()
        with generate_col:
            generate_button = st.button(f"🎨 Generate T-shirt Design ({current_config['count']} designs)", key="generate_design", use_container_width=True)
        
        # Add condition switching buttons
        if len(st.session_state.generated_designs) > 0:
            st.markdown("---")
            st.markdown("#### Condition Navigation")
            
            if st.session_state.current_condition_index < len(CONDITION_ORDER) - 1:
                next_button = st.button("➡️ Next Condition", key="next_condition", use_container_width=True)
            else:
                finish_button = st.button("🎉 Finish Experiment", key="finish_experiment", use_container_width=True)
        
        # Create progress and message areas below input box
        progress_area = st.empty()
        message_area = st.empty()
        
        # Generate design button event handling
        if generate_button:
            # Save user input keywords
            st.session_state.keywords = keywords
            
            # Check if keywords were entered
            if not keywords:
                st.error("Please enter at least one keyword")
            else:
                # Use user input keywords directly as prompt
                user_prompt = keywords
                
                # Save user input
                st.session_state.user_prompt = user_prompt
                
                # Use current condition's design count
                design_count = current_config['count']
                
                # Clear previous designs
                st.session_state.final_design = None
                st.session_state.generated_designs = []
                
                try:
                    # Display generation progress
                    with design_area.container():
                        st.markdown("### Generating T-shirt Designs")
                        if st.session_state.original_tshirt is not None:
                            st.image(st.session_state.original_tshirt, use_container_width=True)
                    
                    # Create progress bar and status messages below input box
                    progress_bar = progress_area.progress(0)
                    message_area.info(f"AI is generating {design_count} unique designs for you. This may take about a minute. Please do not refresh the page or close the browser. Thank you for your patience! ♪(･ω･)ﾉ")
                    # Record start time
                    start_time = time.time()
                    
                    # Collect generated designs
                    designs = []
                    
                    # Safe function for generating single design
                    def generate_single_safely(design_index):
                        try:
                            return generate_complete_design(user_prompt, design_index)
                        except Exception as e:
                            message_area.error(f"Error generating design: {str(e)}")
                            return None, {"error": f"Failed to generate design: {str(e)}"}
                    
                    # For single design, generate directly
                    if design_count == 1:
                        design, info = generate_single_safely(0)
                        if design:
                            designs.append((design, info))
                        progress_bar.progress(100)
                        message_area.success("Design generation complete!")
                    else:
                        # Use parallel processing for multiple designs
                        completed_count = 0
                        
                        # Progress update function
                        def update_progress():
                            nonlocal completed_count
                            completed_count += 1
                            progress = int(100 * completed_count / design_count)
                            progress_bar.progress(progress)
                            message_area.info(f"Generated {completed_count}/{design_count} designs...")
                        
                        # Use thread pool to generate multiple designs in parallel
                        with concurrent.futures.ThreadPoolExecutor(max_workers=design_count) as executor:
                            # Submit all tasks
                            future_to_id = {executor.submit(generate_single_safely, i): i for i in range(design_count)}
                            
                            # Collect results
                            for future in concurrent.futures.as_completed(future_to_id):
                                design_id = future_to_id[future]
                                try:
                                    design, info = future.result()
                                    if design:
                                        designs.append((design, info))
                                except Exception as e:
                                    message_area.error(f"Design {design_id} generation failed: {str(e)}")
                                
                                # Update progress
                                update_progress()
                        
                        # Sort designs by ID
                        designs.sort(key=lambda x: x[1].get("design_index", 0) if x[1] and "design_index" in x[1] else 0)
                    
                    # Record end time
                    end_time = time.time()
                    generation_time = end_time - start_time
                    
                    # Store generated designs
                    if designs:
                        st.session_state.generated_designs = designs
                        st.session_state.selected_design_index = 0
                        message_area.success(f"Generated {len(designs)} designs in {generation_time:.1f} seconds!")
                    else:
                        message_area.error("Could not generate any designs. Please try again.")
                    
                    # Re-render design area to display newly generated designs
                    st.rerun()
                except Exception as e:
                    import traceback
                    message_area.error(f"An error occurred: {str(e)}")
                    st.error(traceback.format_exc())
        
        # Handle condition switching
        if len(st.session_state.generated_designs) > 0:
            # Handle next condition button
            if 'next_button' in locals() and next_button:
                if st.session_state.current_condition_index < len(CONDITION_ORDER) - 1:
                    # Mark current condition as completed
                    current_condition = st.session_state.current_condition
                    if current_condition not in st.session_state.completed_conditions:
                        st.session_state.completed_conditions.append(current_condition)
                    
                    # Switch to next condition
                    st.session_state.current_condition_index += 1
                    st.session_state.current_condition = CONDITION_ORDER[st.session_state.current_condition_index]
                    
                    # Clear current design state, prepare for new condition
                    st.session_state.generated_designs = []
                    st.session_state.final_design = None
                    st.session_state.user_prompt = ""
                    st.session_state.keywords = ""
                    
                    st.success(f"Switched to {RECOMMENDATION_CONDITIONS[st.session_state.current_condition]['name']}!")
                    st.rerun()
            
            # Handle finish experiment button
            if 'finish_button' in locals() and finish_button:
                st.balloons()
                st.success("🎉 Congratulations! You have completed all experimental conditions!")
    

