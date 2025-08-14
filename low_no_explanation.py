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

# API配置信息 - 实际使用时应从主文件传入或使用环境变量
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"

# GPT-4o-mini API配置
GPT4O_MINI_API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
GPT4O_MINI_BASE_URL = "https://api.deepbricks.ai/v1/"

# 从svg_utils导入SVG转换函数
from svg_utils import convert_svg_to_png

def get_ai_design_suggestions(user_preferences=None):
    """Get design suggestions from GPT-4o-mini with more personalized features"""
    client = OpenAI(api_key=GPT4O_MINI_API_KEY, base_url=GPT4O_MINI_BASE_URL)
    
    # Default prompt if no user preferences provided
    if not user_preferences:
        user_preferences = "casual fashion t-shirt design"
    
    # Construct the prompt
    prompt = f"""
    As a T-shirt design consultant, please provide personalized design suggestions for a "{user_preferences}" style T-shirt.
    
    Please provide the following design suggestions in JSON format:

    1. Color: Select the most suitable color for this style (provide name and hex code)
    2. Fabric: Select the most suitable fabric type (Cotton, Polyester, Cotton-Polyester Blend, Jersey, Linen, or Bamboo)
    3. Text: A suitable phrase or slogan that matches the style (keep it concise and impactful)
    4. Logo: A brief description of a logo/graphic element that would complement the design

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
                {"role": "system", "content": "You are a professional T-shirt design consultant. Provide design suggestions in JSON format exactly as requested."},
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

def generate_vector_image(prompt):
    """Generate an image based on the prompt"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None

    if resp and len(resp.data) > 0 and resp.data[0].url:
        image_url = resp.data[0].url
        try:
            image_resp = requests.get(image_url)
            if image_resp.status_code == 200:
                content_type = image_resp.headers.get("Content-Type", "")
                if "svg" in content_type.lower():
                    # 使用集中的SVG处理函数
                    return convert_svg_to_png(image_resp.content)
                else:
                    return Image.open(BytesIO(image_resp.content)).convert("RGBA")
            else:
                st.error(f"Failed to download image, status code: {image_resp.status_code}")
        except Exception as download_err:
            st.error(f"Error requesting image: {download_err}")
    else:
        st.error("Could not get image URL from API response.")
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

def apply_logo_to_shirt(shirt_image, logo_image, position="center", size_percent=30):
    """Apply logo to T-shirt image"""
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
    
    # 调整Logo大小
    logo_size_factor = size_percent / 100
    logo_width = int(chest_width * logo_size_factor * 0.5)
    logo_height = int(logo_width * logo_image.height / logo_image.width)
    logo_resized = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
    
    # 根据位置确定坐标
    position = position.lower() if isinstance(position, str) else "center"
    
    if position == "top-center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + 10
    elif position == "center":
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30  # 略微偏下
    else:  # 默认中间
        logo_x, logo_y = chest_left + (chest_width - logo_width) // 2, chest_top + (chest_height - logo_height) // 2 + 30
    
    # 创建临时图像用于粘贴logo
    temp_image = Image.new("RGBA", result_image.size, (0, 0, 0, 0))
    temp_image.paste(logo_resized, (logo_x, logo_y), logo_resized)
    
    # 组合图像
    result_image = Image.alpha_composite(result_image, temp_image)
    
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
        # 如果提供了变体ID，为不同变体生成不同的设计
        color_hex = design_suggestions.get("color", {}).get("hex", "#FFFFFF")
        fabric_type = design_suggestions.get("fabric", "Cotton")
        
        # 根据变体ID调整颜色和纹理
        if variation_id is not None:
            # 为不同变体生成不同的颜色 (简单的色调变化)
            color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            r, g, b = color_rgb
            
            if variation_id == 1:  # 稍微调亮
                r = min(255, int(r * 1.2))
                g = min(255, int(g * 1.2))
                b = min(255, int(b * 1.2))
            elif variation_id == 2:  # 稍微调暗
                r = int(r * 0.8)
                g = int(g * 0.8)
                b = int(b * 0.8)
            elif variation_id == 3:  # 更偏向红色
                r = min(255, int(r * 1.3))
            elif variation_id == 4:  # 更偏向蓝色
                b = min(255, int(b * 1.3))
            
            color_hex = f"#{r:02x}{g:02x}{b:02x}"
            
            # 可能的面料变化
            fabric_options = ["Cotton", "Polyester", "Cotton-Polyester Blend", "Jersey", "Linen", "Bamboo"]
            if variation_id < len(fabric_options):
                fabric_type = fabric_options[variation_id % len(fabric_options)]
        
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
            # 为变体版本可能稍微修改logo描述
            logo_desc = logo_description
            if variation_id is not None and variation_id > 0:
                modifiers = ["minimalist", "colorful", "abstract", "geometric", "vintage"]
                if variation_id <= len(modifiers):
                    logo_desc = f"{modifiers[variation_id-1]} {logo_description}"
            
            # 修改Logo提示词，确保生成的Logo有白色背景，没有透明部分
            logo_prompt = f"Create a Logo design for printing: {logo_desc}. Requirements: 1. Simple professional design 2. NO TRANSPARENCY background (NO TRANSPARENCY) 3. Clear and distinct graphic 4. Good contrast with colors that will show well on fabric"
            logo_image = generate_vector_image(logo_prompt)
        
        # 最终设计 - 不添加文字
        final_design = colored_shirt
        
        # 应用Logo (如果有)
        if logo_image:
            final_design = apply_logo_to_shirt(colored_shirt, logo_image, "center", 30)
        
        return final_design, {
            "color": {"hex": color_hex, "name": design_suggestions.get("color", {}).get("name", "Custom Color")},
            "fabric": fabric_type,
            "logo": logo_description,
            "variation_id": variation_id
        }
    
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        return None, {"error": f"Error generating design: {str(e)}\n{traceback_str}"}

def generate_multiple_designs(design_prompt, count=1):
    """Generate multiple T-shirt designs in parallel"""
    if count <= 1:
        # 如果只需要一个设计，直接生成不需要并行
        base_design, base_info = generate_complete_design(design_prompt)
        if base_design:
            return [(base_design, base_info)]
        else:
            return []
    
    designs = []
    
    # 定义一个函数来生成单个设计，用于并行处理
    def generate_single_design(variation_id):
        try:
            if variation_id == 0:  # 基础设计
                return generate_complete_design(design_prompt)
            else:  # 变体设计
                return generate_complete_design(design_prompt, variation_id=variation_id)
        except Exception as e:
            print(f"Error generating design {variation_id}: {e}")
            return None, {"error": f"Failed to generate design {variation_id}"}
    
    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
        # 提交所有任务
        future_to_id = {executor.submit(generate_single_design, i): i for i in range(count)}
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_id):
            design_id = future_to_id[future]
            try:
                design, info = future.result()
                if design:
                    designs.append((design, info))
            except Exception as e:
                print(f"Design {design_id} generated an exception: {e}")
    
    # 按照原始ID顺序排序
    designs.sort(key=lambda x: x[1].get("variation_id", 0) if x[1] and "variation_id" in x[1] else 0)
    
    return designs

def show_low_recommendation_without_explanation():
    st.title("👕 AI Recommendation Experiment Platform")
    st.markdown("### Study3-Let AI Design Your T-shirt")
    
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
    if 'keyword_style' not in st.session_state:
        st.session_state.keyword_style = "hedonic"  # 默认使用hedonic风格
    if 'generated_designs' not in st.session_state:
        st.session_state.generated_designs = []
    if 'selected_design_index' not in st.session_state:
        st.session_state.selected_design_index = 0
    if 'original_tshirt' not in st.session_state:
        # 加载原始白色T恤图像
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
    
    # 创建两列布局
    design_col, input_col = st.columns([3, 2])
    
    with design_col:
        # 创建占位区域用于T恤设计展示
        design_area = st.empty()
        
        # 在设计区域显示当前状态的T恤设计
        if st.session_state.final_design is not None:
            with design_area.container():
                st.markdown("### Your Custom T-shirt Design")
                st.image(st.session_state.final_design, use_container_width=True)
        elif len(st.session_state.generated_designs) > 0:
            with design_area.container():
                st.markdown("### Generated Design Options")
                
                # 创建多列来显示设计
                design_count = len(st.session_state.generated_designs)
                if design_count > 3:
                    # 两行显示
                    row1_cols = st.columns(min(3, design_count))
                    row2_cols = st.columns(min(3, max(0, design_count - 3)))
                    
                    # 显示第一行
                    for i in range(min(3, design_count)):
                        with row1_cols[i]:
                            design, _ = st.session_state.generated_designs[i]
                            # 添加选中状态的样式
                            if i == st.session_state.selected_design_index:
                                st.markdown(f"""
                                <div style="border:3px solid #f63366; padding:3px; border-radius:5px;">
                                <p style="text-align:center; color:#f63366; margin:0; font-weight:bold;">Design {i+1}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            
                            # 显示设计并添加点击功能
                            st.image(design, use_container_width=True)
                            if st.button(f"Select Design {i+1}", key=f"select_design_{i}"):
                                st.session_state.selected_design_index = i
                                st.session_state.final_design = design
                                st.session_state.design_info = st.session_state.generated_designs[i][1]
                                st.rerun()
                    
                    # 显示第二行
                    for i in range(3, design_count):
                        with row2_cols[i-3]:  
                            design, _ = st.session_state.generated_designs[i]
                            # 添加选中状态的样式
                            if i == st.session_state.selected_design_index:
                                st.markdown(f"""
                                <div style="border:3px solid #f63366; padding:3px; border-radius:5px;">
                                <p style="text-align:center; color:#f63366; margin:0; font-weight:bold;">Design {i+1}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            
                            # 显示设计并添加点击功能
                            st.image(design, use_container_width=True)
                            if st.button(f"Select Design {i+1}", key=f"select_design_{i}"):
                                st.session_state.selected_design_index = i
                                st.session_state.final_design = design
                                st.session_state.design_info = st.session_state.generated_designs[i][1]
                                st.rerun()
                else:
                    # 单行显示
                    cols = st.columns(design_count)
                    for i in range(design_count):
                        with cols[i]:
                            design, _ = st.session_state.generated_designs[i]
                            # 添加选中状态的样式
                            if i == st.session_state.selected_design_index:
                                st.markdown(f"""
                                <div style="border:3px solid #f63366; padding:3px; border-radius:5px;">
                                <p style="text-align:center; color:#f63366; margin:0; font-weight:bold;">Design {i+1}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"<p style='text-align:center;'>Design {i+1}</p>", unsafe_allow_html=True)
                            
                            # 显示设计并添加点击功能
                            st.image(design, use_container_width=True)
                            if st.button(f"Select Design {i+1}", key=f"select_design_{i}"):
                                st.session_state.selected_design_index = i
                                st.session_state.final_design = design
                                st.session_state.design_info = st.session_state.generated_designs[i][1]
                                st.rerun()
                
                # 添加确认选择按钮
                if st.button("✅ Confirm Selection"):
                    selected_design, selected_info = st.session_state.generated_designs[st.session_state.selected_design_index]
                    st.session_state.final_design = selected_design
                    st.session_state.design_info = selected_info
                    st.session_state.generated_designs = []  # 清空生成的设计列表
                    st.rerun()
        else:
            # 显示原始空白T恤
            with design_area.container():
                st.markdown("### T-shirt Design Preview")
                if st.session_state.original_tshirt is not None:
                    st.image(st.session_state.original_tshirt, use_container_width=True)
                else:
                    st.info("Could not load original T-shirt image, please refresh the page")
    
    with input_col:
        # 设计提示词和关键词选择区
        st.markdown("### Design Options")
        
        # 创建两个选项卡，分别用于hedonic和functional风格
        tab1, tab2 = st.tabs(["Hedonic", "Functional"])
        
        # Hedonic选项卡
        with tab1:
            st.markdown("#### Select hedonic keywords for your T-shirt design:")
            
            # 添加hedonic关键词说明
            st.markdown("""
            <div style="margin-bottom: 15px; padding: 10px; background-color: #f0f2f6; border-radius: 5px;">
            <p style="margin: 0; font-size: 14px;"><strong>Hedonic Keywords:</strong> Words associated with emotions, sentiments, or aesthetic qualities.<br>
            Examples: elegant, vibrant, playful, artistic, stylish</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Hedonic关键词列表
            hedonic_keywords = [
                "Elegant", "Vibrant", "Playful", "Artistic", "Stylish",
                "Dreamy", "Bold", "Minimalist", "Retro", "Cheerful"
            ]
            
            # 创建两行五列的选择布局
            for i in range(0, len(hedonic_keywords), 5):
                cols = st.columns(5)
                for j in range(5):
                    if i+j < len(hedonic_keywords):
                        with cols[j]:
                            # 使用唯一标识符作为键
                            keyword = hedonic_keywords[i+j]
                            key_name = f"kw_h_{keyword.lower()}"
                            # 复选框默认不选中
                            st.checkbox(keyword, key=key_name)
            
            # 自定义输入框
            st.markdown("#### Add your own hedonic keywords:")
            
            # 创建两个自定义关键词输入框
            custom_cols = st.columns(2)
            with custom_cols[0]:
                custom_h_keyword1 = st.text_input("Custom Hedonic Keyword 1", 
                                                placeholder="e.g., glamorous", key="custom_h1")
            
            with custom_cols[1]:
                custom_h_keyword2 = st.text_input("Custom Hedonic Keyword 2", 
                                                placeholder="e.g., nostalgic", key="custom_h2")
        
        # Functional选项卡
        with tab2:
            st.markdown("#### Select functional keywords for your T-shirt design:")
            
            # 添加functional关键词说明
            st.markdown("""
            <div style="margin-bottom: 15px; padding: 10px; background-color: #f0f2f6; border-radius: 5px;">
            <p style="margin: 0; font-size: 14px;"><strong>Functional Keywords:</strong> Words associated with practical or technical attributes.<br>
            Examples: durable, breathable, lightweight, comfortable, practical</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Functional关键词列表
            functional_keywords = [
                "Durable", "Breathable", "Lightweight", "Comfortable", "Practical",
                "Athletic", "Quick-dry", "Stretchy", "Sustainable", "UV-protective" 
            ]
            
            # 创建两行五列的选择布局
            for i in range(0, len(functional_keywords), 5):
                cols = st.columns(5)
                for j in range(5):
                    if i+j < len(functional_keywords):
                        with cols[j]:
                            # 使用唯一标识符作为键
                            keyword = functional_keywords[i+j]
                            key_name = f"kw_f_{keyword.lower()}"
                            # 复选框默认不选中
                            st.checkbox(keyword, key=key_name)
            
            # 自定义输入框
            st.markdown("#### Add your own functional keywords:")
            
            # 创建两个自定义关键词输入框
            custom_cols = st.columns(2)
            with custom_cols[0]:
                custom_f_keyword1 = st.text_input("Custom Functional Keyword 1", 
                                                placeholder="e.g., stain-resistant", key="custom_f1")
            
            with custom_cols[1]:
                custom_f_keyword2 = st.text_input("Custom Functional Keyword 2", 
                                                placeholder="e.g., moisture-wicking", key="custom_f2")
        
        # 生成设计按钮
        generate_col = st.empty()
        with generate_col:
            generate_button = st.button("🎨 Generate T-shirt Design", key="generate_design", use_container_width=True)
        
        # 创建进度和消息区域在输入框下方
        progress_area = st.empty()
        message_area = st.empty()
        
        # 生成设计按钮事件处理
        if generate_button:
            # 收集选择的关键词
            selected_keywords = []
            selected_style = None
            
            # 检查hedonic关键词
            hedonic_selected = False
            for keyword in hedonic_keywords:
                key_name = f"kw_h_{keyword.lower()}"
                if key_name in st.session_state and st.session_state[key_name]:
                    selected_keywords.append(keyword)
                    hedonic_selected = True
            
            # 添加hedonic自定义关键词
            if custom_h_keyword1.strip():
                selected_keywords.append(custom_h_keyword1.strip())
                hedonic_selected = True
            if custom_h_keyword2.strip():
                selected_keywords.append(custom_h_keyword2.strip())
                hedonic_selected = True
            
            # 检查functional关键词
            functional_selected = False
            for keyword in functional_keywords:
                key_name = f"kw_f_{keyword.lower()}"
                if key_name in st.session_state and st.session_state[key_name]:
                    selected_keywords.append(keyword)
                    functional_selected = True
            
            # 添加functional自定义关键词
            if custom_f_keyword1.strip():
                selected_keywords.append(custom_f_keyword1.strip())
                functional_selected = True
            if custom_f_keyword2.strip():
                selected_keywords.append(custom_f_keyword2.strip())
                functional_selected = True
                
            # 确定选择的主要风格
            if hedonic_selected and not functional_selected:
                selected_style = "hedonic"
            elif functional_selected and not hedonic_selected:
                selected_style = "functional"
            elif hedonic_selected and functional_selected:
                selected_style = "mixed"
            
            # 检查是否至少选择了一个关键词
            if not selected_keywords:
                message_area.error("Please select at least one keyword or add a custom keyword")
            else:
                # 组合关键词成为完整提示词
                user_prompt = ", ".join(selected_keywords)
                
                # 添加风格提示
                if selected_style == "hedonic":
                    user_prompt += " (hedonic t-shirt design emphasizing aesthetics and emotions)"
                elif selected_style == "functional":
                    user_prompt += " (functional t-shirt design emphasizing practical features)"
                else:
                    user_prompt += " (t-shirt design balancing aesthetics and functionality)"
                
                # 保存用户输入
                st.session_state.user_prompt = user_prompt
                
                # 清空之前的设计
                st.session_state.final_design = None
                st.session_state.generated_designs = []
                
                try:
                    # 显示生成进度
                    with design_area.container():
                        st.markdown("### Generating T-shirt Designs")
                        if st.session_state.original_tshirt is not None:
                            st.image(st.session_state.original_tshirt, use_container_width=True)
                    
                    # 创建进度条和状态消息在输入框下方
                    progress_bar = progress_area.progress(0)
                    message_area.info(f"AI is generating 1 design for you, please wait...")
                    
                    # 记录开始时间
                    start_time = time.time()
                    
                    # 生成单个设计
                    design, info = generate_complete_design(user_prompt)
                    
                    # 记录结束时间
                    end_time = time.time()
                    generation_time = end_time - start_time
                    
                    # 存储生成的设计
                    if design:
                        st.session_state.final_design = design
                        st.session_state.design_info = info
                        st.session_state.selected_design_index = 0
                        message_area.success(f"Generated design in {generation_time:.1f} seconds!")
                    else:
                        message_area.error("Could not generate any designs. Please try again.")
                    
                    # 重新渲染设计区域以显示新生成的设计
                    st.rerun()
                except Exception as e:
                    import traceback
                    message_area.error(f"An error occurred: {str(e)}")
                    st.error(traceback.format_exc())
    
    # 下载按钮 (在主区域底部)
    if st.session_state.final_design is not None:
        st.markdown("---")
        download_col, next_col = st.columns(2)
        
        with download_col:
            buf = BytesIO()
            st.session_state.final_design.save(buf, format="PNG")
            buf.seek(0)
            st.download_button(
                label="💾 Download Design",
                data=buf,
                file_name="ai_tshirt_design.png",
                mime="image/png"
            )
        
        with next_col:
            # 确认完成按钮
            if st.button("✅ Confirm"):
                st.session_state.page = "survey"
                st.rerun()
    
    # 添加返回主页按钮
    st.markdown("---")
    if st.button("🏠 Return to Home"):
        # 重置基本状态变量
        for key in ['user_prompt', 'final_design', 'design_info', 'is_generating', 
                    'keyword_style', 'generated_designs', 'selected_design_index',
                    'custom_h1', 'custom_h2', 'custom_f1', 'custom_f2']:
            if key in st.session_state:
                del st.session_state[key]
        
        # 清除所有关键词复选框状态
        hedonic_keywords = [
            "Elegant", "Vibrant", "Playful", "Artistic", "Stylish",
            "Dreamy", "Bold", "Minimalist", "Retro", "Cheerful"
        ]
        for keyword in hedonic_keywords:
            key_name = f"kw_h_{keyword.lower()}"
            if key_name in st.session_state:
                del st.session_state[key_name]
        
        functional_keywords = [
            "Durable", "Breathable", "Lightweight", "Comfortable", "Practical",
            "Athletic", "Quick-dry", "Stretchy", "Sustainable", "UV-protective" 
        ]
        for keyword in functional_keywords:
            key_name = f"kw_f_{keyword.lower()}"
            if key_name in st.session_state:
                del st.session_state[key_name]
        
        # 设置页面为welcome
        st.session_state.page = "welcome"
        st.rerun()