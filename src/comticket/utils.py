import json
import os
import tomllib  # Python 3.11+
import pickle
from dotenv import load_dotenv
from loguru import logger
from datetime import datetime
import os
from zai import ZhipuAiClient
import time



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

def get_user_id():
    config = load_config()
    return config["user"]["userID"]

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

def get_session_csrftoken():
    cookies = load_session_cookies()
    for cookie in cookies:
        # print(f"{cookie.name} = {cookie.value}; domain={cookie.domain}; path={cookie.path}; expires={cookie.expires}")
        if cookie.name == "csrftoken":
            return cookie.value
    return None


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

# =========llm========
def _init_client() -> ZhipuAiClient:
    """实例化全局 ZhipuAiClient"""
    config = load_config()
    token = config.get("llm", {}).get("token")
    if not token:
        raise RuntimeError("缺少 [llm].token，请在 config.toml 中配置")

    logger.info("初始化 ZhipuAiClient ...")
    start = time.perf_counter()
    client = ZhipuAiClient(api_key=token)
    logger.success("ZhipuAiClient 初始化完成，耗时 {:.2f}s", time.perf_counter() - start)
    return client

# 全局唯一实例
client: ZhipuAiClient = _init_client()



def llm(remark, base_info):
    start = time.perf_counter()
    logger.info("分析 remark: {}", remark)

    response = client.chat.completions.create(
        model="glm-4.5",
        messages=[
            {"role": "system", "content": "你是一名网络工程师，擅长python数据处理。"},
            {
                "role": "user",
                "content": f"""已知一个base_info字典：{base_info};备注内容：{remark};请你根据备注内容分析并补充/修改 base_info 的字段，缺省的字段使用字典value分号前的默认值，分号在新字段里隐藏；“JIRA工单”字段有时不会传“RPA-”前缀，遇到四位数字默认为RPA-xxxx，多个使用逗号隔开；保持字典结构，返回完整的base_info字典（只返回JSON，不要解释）。"""
            }
        ],
    )

    duration = time.perf_counter() - start
    result = response.choices[0].message.content.strip()

    logger.info("耗时: {:.2f}s", duration)
    logger.info("更新后的 base_info: {}", result)
    return result


