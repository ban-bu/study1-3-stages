"""
SVG处理工具模块 - 提供SVG到PNG转换功能
不依赖cairosvg库，仅使用svglib和reportlab
"""

import streamlit as st
from io import BytesIO
from PIL import Image

# 检查是否可用svglib库
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    SVGLIB_AVAILABLE = True
except ImportError:
    SVGLIB_AVAILABLE = False

def convert_svg_to_png(svg_content):
    """
    将SVG内容转换为PNG格式的PIL图像对象
    使用svglib库来处理，不依赖cairosvg
    
    参数:
        svg_content: SVG内容（bytes或string格式）
        
    返回:
        PIL.Image对象（RGBA模式）或None（如果转换失败）
    """
    try:
        if SVGLIB_AVAILABLE:
            # 确保svg_content是bytes类型
            if isinstance(svg_content, str):
                svg_content = svg_content.encode('utf-8')
                
            # 使用svglib将SVG内容转换为PNG
            svg_bytes = BytesIO(svg_content)
            drawing = svg2rlg(svg_bytes)
            png_bytes = BytesIO()
            renderPM.drawToFile(drawing, png_bytes, fmt="PNG")
            png_bytes.seek(0)
            return Image.open(png_bytes).convert("RGBA")
        else:
            st.error("SVG转换库未安装，请安装svglib和reportlab: pip install svglib reportlab")
            return None
    except Exception as e:
        st.error(f"SVG转PNG转换错误: {str(e)}")
        # 记录更详细的错误信息
        import traceback
        print(traceback.format_exc())
        return None 