"""
1.登录拿取cookie，保存在data/
"""

import requests
from bs4 import BeautifulSoup
from src.comticket.utils import *

def get_session():
    """
    返回已登录的 requests.Session()
    会尝试使用保存的 session_cookies.pkl，否则重新登录并保存 cookies
    """
    config = load_config()
    base_url = config["base_url"]
    login_url = f"{base_url}/robot/admin/login/"
    next_url = f"{base_url}/robot/admin/app/comticket/"

    username = config["user"]["username"]
    password = config["user"]["password"]

    session = requests.Session()

    # 尝试加载 cookies
    cookies = load_session_cookies()
    if cookies:
        session.cookies.update(cookies)
        logger.success("已加载上次登录的 cookies")

    # 检查 cookies 是否有效
    resp = session.get(next_url, allow_redirects=False, timeout=10)
    # save_response_html(resp.text, prefix="aaa")
    if resp.status_code == 200 and '待处理' in resp.text:
        logger.success("已登录，无需再次登录")
        return session

    # 需要登录
    logger.warning("需要登录，开始登录流程...")

    # 获取 CSRF token
    resp = session.get(login_url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if not csrf_input:
        raise RuntimeError("无法找到 csrf token，请检查登录页 HTML")
    csrf_token = csrf_input["value"]

    payload = {
        "username": username,
        "password": password,
        "csrfmiddlewaretoken": csrf_token,
        "next": "/robot/admin/app/comticket/"
    }

    headers = {
        "Referer": login_url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    login_resp = session.post(login_url, data=payload, headers=headers, allow_redirects=False, timeout=10)
    if "sessionid" in session.cookies:
        logger.success("登录成功，已保存 cookies")
        save_session_cookies(session.cookies)
    else:
        logger.error("登录失败，请检查用户名/密码或 csrf token")
        raise RuntimeError("登录失败")

    return session

if __name__ == "__main__":
    session1 = get_session()
    resp = session1.get(
        f'{load_config()["base_url"].rstrip("/")}/robot/admin/app/comticket/'
    )
    logger.debug(resp.text[:500])
    logger.debug(session1.cookies)
