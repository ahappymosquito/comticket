"""职责：集中管理配置、运行态数据、通知适配器和版本工具。"""

import json
import os
import tomllib  # Python 3.11+
import pickle
from loguru import logger
from datetime import datetime
import time
from pathlib import Path

from .sqlite import *
from .Msg_DingTalk import DingTalkBot
from .Msg_Email import MailClient
from .versioning import bump_version


# 工程根目录
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE_DIR = Path(__file__).resolve().parents[2]

# 配置文件
CONFIG_PATH = os.path.join(BASE_DIR, "config.toml")

# 数据文件目录
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_RESPONSE_DIR = os.path.join(DATA_DIR, "response")
SESSION_COOKIES_PATH = os.path.join(DATA_DIR, "session_cookies.pkl")

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DATA_RESPONSE_DIR, exist_ok=True)

def get_db():
    db = SQLiteDB(db_name="info_monitor.db", data_dir=DATA_DIR)
    init_table(db)
    return db


# ================= 配置相关 =================
def load_config():
    """加载 config.toml"""
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


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

def send_DingTalk(msg: str, phone_number=[],is_at_all=False):
    config = load_config()
    base_DingTalk = config["DingTalk"]
    bot = DingTalkBot(
        access_token=base_DingTalk["access_token"],
        secret=base_DingTalk["secret"]
    )
    bot.send_text(
        msg=msg,
        # at_user_ids=["3538670625-1997372447","1vb_pwihce3l92"],
        at_mobiles=phone_number,
        is_at_all=is_at_all
    )

def send_Group_DingTalk(msg: str, phone_number=[],is_at_all=False):
    config = load_config()
    base_DingTalk = config["send_group"]
    bot = DingTalkBot(
        access_token=base_DingTalk["access_token"],
        secret=base_DingTalk["secret"]
    )
    bot.send_text(
        msg=msg,
        # at_user_ids=["3538670625-1997372447","1vb_pwihce3l92"],
        at_mobiles=phone_number,
        is_at_all=is_at_all
    )

def send_Email(to: list, subject:str ,body:str,html = '' ,sender_name="徐文超"):
    config = load_config()
    smtp = config["smtp"]
    client = MailClient(
        smtp_server=smtp["server"],
        port=smtp["port"],
        sender_email=smtp["sender"],
        password=smtp["pwd"],
        sender_name=sender_name,
    )

    client.send_mail(
        to=to,
        subject=subject,
        body=body,
        html=html,
    )


# =========llm========
def _init_client():
    """实例化 ZhipuAiClient。仅在 [llm].enabled=true 时调用。"""
    try:
        from zai import ZhipuAiClient
    except ImportError as exc:
        raise RuntimeError("启用 LLM 需要安装 zai-sdk") from exc

    config = load_config()
    token = config.get("llm", {}).get("token")
    if not token:
        raise RuntimeError("缺少 [llm].token，请在 config.toml 中配置")

    logger.info("初始化 ZhipuAiClient ...")
    start = time.perf_counter()
    client = ZhipuAiClient(api_key=token)
    logger.success("ZhipuAiClient 初始化完成，耗时 {:.2f}s", time.perf_counter() - start)
    return client

def _llm_enabled() -> bool:
    return bool(load_config().get("llm", {}).get("enabled"))


def llm(remark, base_info):
    """可选 LLM 抽取。审批台主路径不调用本函数，enabled=false 时不请求模型。"""
    defaults = {
        "系统版本": "Microsoft Windows Server 2019 Standard",
        "浏览器": "Google",
        "场景": "网银",
        "验证类型": "无验证",
        "区域": "其他",
        "浏览器版本": "",
        "登陆类型": "其他",
        "登陆网址": "",
        "JIRA工单": "",
    }
    if isinstance(base_info, dict):
        defaults.update(base_info)
    if not _llm_enabled():
        logger.info("LLM 未启用，跳过 remark 抽取")
        return json.dumps(defaults, ensure_ascii=False)

    client = _init_client()
    # base_info =
    #         {
    #             "系统版本": "Windows10",
    #             "浏览器": "Google",
    #             "场景": "网银",
    #             "验证类型": "无验证",
    #             "区域": "境内",
    #             "浏览器版本": "140.0.7339.128",
    #             "登陆类型": "其他",
    #             "登陆网址": "https://default.com",
    #             "JIRA工单": "RPA-3276"
    #         }


    """
    Available options: 
        glm-4.6, 
        glm-4.5, 
        glm-4.5-air, 
        glm-4.5-x, 
        glm-4.5-airx, 
        glm-4.5-flash, 
        glm-4-plus, 
        glm-4-air-250414, 
        glm-4-airx, 
        glm-4-flashx, 
        glm-4-flashx-250414, 
        glm-z1-air, 
        glm-z1-airx, 
        glm-z1-flash, 
        glm-z1-flashx 
    
    """


    start = time.perf_counter()
    logger.info("分析 remark: {}", remark)

    response = client.chat.completions.create(
        model="glm-4.5",
        messages=[
            {"role": "system", "content": "你是一名网络工程师，擅长python数据处理。"},
            {
                "role": "user",
                "content": f"""已知一个字典：{base_info};备注内容：{remark};请你根据备注内容分析并补充/修改这个字典的字段，注意（场景！验证类型！区域！登录类型！浏览器版本！浏览器！系统版本！）这些字段是唯一的选项！，
                                缺省的字段使用字典value分号前的默认值，分号在新字段里隐藏，字段值不要出现空格；“JIRA工单”字段有时不会传“RPA-”前缀，遇到四位数字默认为RPA-xxxx，
                                多个使用逗号隔开，注意如果传入了工单号，就不需要默认的RPA-0001了；
                                注意：以下这些字段是严格控制的，不可以自定义！(场景！验证类型！区域！登录类型！)；
                                注意保持字典结构！返回完整的字典（只返回JSON!不要解释,不要变量名，纯文本！不要有''',不要有'json'等会干扰json解析的字符！)。
                            """
            }
        ],
    )

    duration = time.perf_counter() - start
    result = response.choices[0].message.content.strip()

    logger.info("耗时: {:.2f}s", duration)
    logger.info("更新后的 base_info: {}", result)
    return result
