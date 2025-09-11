import os
import tomllib  # Python 3.11+
import pickle
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime
import os


# 工程根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置文件
CONFIG_PATH = os.path.join(BASE_DIR, "config.toml")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 数据文件目录
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_RESPONSE_DIR = os.path.join(DATA_DIR, "response")
SESSION_COOKIES_PATH = os.path.join(DATA_DIR, "session_cookies.pkl")

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DATA_RESPONSE_DIR, exist_ok=True)


# ================= 配置相关 =================
def load_config():
    """加载 config.toml"""
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def load_env():
    """加载 .env"""
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH)

# 不存在返回None
def get_env_var(key: str, default=None):
    """获取环境变量"""
    return os.getenv(key, default)


# ================= Cookie 存取 =================
def load_session_cookies():
    """读取会话 cookies"""
    if os.path.exists(SESSION_COOKIES_PATH):
        with open(SESSION_COOKIES_PATH, "rb") as f:
            return pickle.load(f)
    return None


def save_session_cookies(cookies):
    """保存会话 cookies"""
    with open(SESSION_COOKIES_PATH, "wb") as f:
        pickle.dump(cookies, f)



# =============保存相应页面=========
def save_response_html(content: str, prefix: str = "response") -> str:
    """
    将 HTML 内容保存到指定文件夹，文件名带时间戳
    :param content: 要保存的 HTML 文本
    :param prefix: 文件名前缀，默认 'response'
    :return: 保存的文件路径
    """
    os.makedirs(DATA_RESPONSE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.html"
    filepath = os.path.join(DATA_RESPONSE_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.success(f"响应已保存: {filepath}")
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        filepath = ""

    return filepath
