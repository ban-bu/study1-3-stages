# 导入所有必要的基础依赖
import streamlit as st

# Page configuration - 必须是第一个Streamlit命令
st.set_page_config(
    page_title="AI Co-Creation Clothing Consumer Behavior Experiment",
    page_icon="👕",
    layout="wide",
    initial_sidebar_state="expanded"
)

import warnings
warnings.filterwarnings('ignore')

from PIL import Image, ImageDraw
import requests
from io import BytesIO
# 重新组织cairosvg导入逻辑，避免错误
# 完全移除cairosvg依赖，只使用svglib或其他备选方案
import base64
import numpy as np
import os
import pandas as pd
import uuid
import datetime
import json

# Requires installation: pip install streamlit-image-coordinates
from streamlit_image_coordinates import streamlit_image_coordinates
from streamlit.components.v1 import html
from streamlit_drawable_canvas import st_canvas

# 导入环境变量支持
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入OpenAI配置 - 使用环境变量
from openai import OpenAI
API_KEY = os.getenv("OPENAI_API_KEY", "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepbricks.ai/v1/")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 导入面料纹理模块
from fabric_texture import apply_fabric_texture

# 导入SVG处理功能
from svg_utils import convert_svg_to_png

# 导入分拆出去的各页面模块
from welcome_page import show_welcome_page
from survey_page import show_survey_page, initialize_experiment_data, save_experiment_data
from low_no_explanation import show_low_recommendation_without_explanation
from low_with_explanation import show_low_recommendation_with_explanation
from high_no_explanation import show_high_recommendation_without_explanation
from high_with_explanation import show_high_recommendation_with_explanation

# Custom CSS styles
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        height: 3rem;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .design-area {
        border: 2px dashed #f63366;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 20px;
    }
    .highlight-text {
        color: #f63366;
        font-weight: bold;
    }
    .purchase-intent {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    .rating-container {
        display: flex;
        justify-content: space-between;
        margin: 20px 0;
    }
    .welcome-card {
        background-color: #f8f9fa;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 30px;
    }
    .group-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
        border: 1px solid #e0e0e0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .group-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    .design-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 10px;
        margin: 20px 0;
    }
    .design-item {
        border: 2px solid transparent;
        border-radius: 5px;
        transition: border-color 0.2s;
        cursor: pointer;
    }
    .design-item.selected {
        border-color: #f63366;
    }
    .movable-box {
        cursor: move;
    }
</style>
""", unsafe_allow_html=True)

# 数据文件路径 - 共享常量
DATA_FILE = "experiment_data.csv"

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 工具函数：获取资源文件的完整路径
def get_resource_path(filename):
    """获取资源文件的完整路径，支持多种可能的位置"""
    possible_paths = [
        os.path.join(current_dir, filename),
        os.path.join(current_dir, "assets", filename),
        os.path.join(current_dir, "images", filename),
        filename  # 相对路径作为后备
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 如果都找不到，返回原始文件名
    return filename

# Preset design options (using local images) - 暂时禁用，因为preset_designs目录不存在
PRESET_DESIGNS = {
    # "Floral Pattern": get_resource_path("floral.png"),
    # "Geometric Pattern": get_resource_path("geometric.png"),
    # "Abstract Art": get_resource_path("abstract.png"),
    # "Minimalist Lines": get_resource_path("minimalist.png"),
    # "Animal Pattern": get_resource_path("animal.png")
}

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = "design"  # 直接将初始页面设置为design而不是welcome
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.datetime.now()
if 'experiment_group' not in st.session_state:
    # 直接设置为study1对应的实验组
    st.session_state.experiment_group = "study1: The Effects of AI Recommendation Levels on AI Creativity"
if 'user_info' not in st.session_state:
    # 设置默认用户信息
    st.session_state.user_info = {
        'age': 25,
        'gender': "Male",
        'shopping_frequency': "Weekly",
        'customize_experience': "Some experience",
        'ai_attitude': 5,
        'uniqueness_importance': 5
    }
if 'base_image' not in st.session_state:
    st.session_state.base_image = None
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'current_box_position' not in st.session_state:
    st.session_state.current_box_position = None
if 'generated_design' not in st.session_state:
    st.session_state.generated_design = None
if 'final_design' not in st.session_state:
    st.session_state.final_design = None
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'selected_preset' not in st.session_state:
    st.session_state.selected_preset = None
if 'preset_design' not in st.session_state:
    st.session_state.preset_design = None
if 'drawn_design' not in st.session_state:
    st.session_state.drawn_design = None
if 'preset_position' not in st.session_state:
    st.session_state.preset_position = (0, 0)  # 默认居中，表示相对红框左上角的偏移
if 'preset_scale' not in st.session_state:
    st.session_state.preset_scale = 40  # 默认为40%
if 'design_mode' not in st.session_state:
    st.session_state.design_mode = "preset"  # 默认使用预设设计模式
if 'fabric_type' not in st.session_state:
    st.session_state.fabric_type = None  # 初始状态下没有特定面料类型
if 'apply_texture' not in st.session_state:
    st.session_state.apply_texture = False  # 初始状态下不应用纹理

# Main program control logic
def main():
    # Initialize data file
    initialize_experiment_data()
    
    # Display different content based on current page
    if st.session_state.page == "welcome":
        show_welcome_page()
    elif st.session_state.page == "design":
        # 根据不同的实验组调用不同的设计页面函数
        if st.session_state.experiment_group == "AI Customization Group":
            show_low_recommendation_without_explanation()
        elif st.session_state.experiment_group == "AI Design Group":
            show_low_recommendation_with_explanation()
        elif st.session_state.experiment_group == "AI Creation Group":
            show_high_recommendation_with_explanation()
        elif st.session_state.experiment_group == "study1: The Effects of AI Recommendation Levels on AI Creativity":
            show_high_recommendation_without_explanation()
        else:
            st.error("实验组类型错误，请返回首页重新选择")
            if st.button("返回首页"):
                st.session_state.page = "welcome"
                st.rerun()
    elif st.session_state.page == "survey":
        show_survey_page()

# Run application
if __name__ == "__main__":
    main()