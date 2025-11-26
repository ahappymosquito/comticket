import json
import re

from loguru import logger
import requests
from bs4 import BeautifulSoup
from lxml import etree
from parsel import Selector
from src.comticket.utils import *
from src.comticket.htmlParser import *

#先检查有没有已有组件，获取版本号再+1返回
def check_component_update(component_name_list):
    db_ccu = get_db()

    return_list = []
    for component_name in component_name_list:
        base_url = load_config()["base_url"]
        query_url = f'{base_url}/robot/admin/app/componentversion/?main_component__name={component_name}'
        headers = {
            "Host": "ats.fingard.net:9561",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "http://ats.fingard.net:9561/robot/admin/app/component/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        cookies = load_session_cookies()

        try:
            logger.info(f"正在查询 {component_name},url:{query_url}")
            response = requests.get(query_url, headers=headers, cookies=cookies, timeout=10)
            # save_response_html(response.text)

            # logger.info(f"状态码: {response.status_code}")
            if response.status_code == 200:
                logger.success("请求成功，返回200")
                content = response.text

                # print(content)
                arserp = HtmlParser(content)

                if arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[2]"):
                    version = arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[2]")[0].get_text()
                    mark = arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[3]")[0].get_text()
                    name = arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[4]")[0].get_text()
                    date = arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[7]")[0].get_text()

                    logger.debug((version, mark, name,date))
                    logger.info(">>> 开始保存数据")
                    target_hash = add_record(db_ccu, component_name,version, mark, name,date)
                    logger.debug(target_hash)
                    if target_hash:
                        send_DingTalk(f"{component_name}{version}已更新!\n注意：{mark}\n{name}于{date}上传更新",is_at_all='True')
                        send_Group_DingTalk(f"{component_name}{version}已更新!\n注意：{mark}\n{name}于{date}上传更新",is_at_all='False')

                    return_list.append((component_name, version, mark, name, date, target_hash))
                else:
                    logger.warning("哪有这组件啊！？")
                    save_response_html(content)
                    send_DingTalk("哪有这组件啊！？",is_at_all=False)
            else:
                logger.warning(f"请求失败，状态码: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"请求异常: {e}")
            return return_list
    return return_list


# if __name__ == '__main__':
#
#     muban = ["网银查询业务组件模板","网银客户端登录组件模板","网银浏览器登录组件模板"]
#     lis = check_component_update(muban)
#     for i in range(3):
#         if len(lis) == len(muban):
#             break
#         lis = check_component_update(muban)

from datetime import datetime
import time


def run(muban):
    # muban = ["网银查询业务组件模板", "网银客户端登录组件模板", "网银浏览器登录组件模板"]

    now_time = datetime.now().time()
    start = datetime.strptime("08:00", "%H:%M").time()
    end = datetime.strptime("08:10", "%H:%M").time()

    if start <= now_time <= end:
        lis = check_component_update(muban)

        # for 循环控制最多 3 次重试
        for i in range(3):
            if len(lis) == len(muban):
                print(f"✅ 任务成功，在第 {i + 1} 次重试前跳出。")
                break
            print(f"⚠️ 检查不完整，执行第 {i + 1} 次重试...")
            lis = check_component_update(muban)
        else:
            if len(lis) != len(muban):
                print("❌ 达到最大尝试次数，任务最终失败。")
        time.sleep(900)

if __name__ == '__main__':

    # 任务配置
    TARGET_H = 1
    TARGET_M = 55
    muban = ["网银查询业务组件模板", "网银客户端登录组件模板", "网银浏览器登录组件模板"]

    print(f"服务启动：等待 {TARGET_H:02d}:{TARGET_M:02d}...")

    while True:
        now = datetime.datetime.now()

        # 检查是否是目标时间 01:50
        if now.hour == TARGET_H and now.minute == TARGET_M:

            print(f"\n>>> 时间到达 {TARGET_H:02d}:{TARGET_M:02d}，开始执行任务 <<<")

            # === 您提供的核心重试逻辑（完全保留） ===
            lis = check_component_update(muban)

            # for 循环控制最多 3 次重试
            for i in range(3):
                if len(lis) == len(muban):
                    print(f"✅ 任务成功，在第 {i + 1} 次重试前跳出。")
                    break
                print(f"⚠️ 检查不完整，执行第 {i + 1} 次重试...")
                lis = check_component_update(muban)
            else:
                if len(lis) != len(muban):
                    print("❌ 达到最大尝试次数，任务最终失败。")
            # ========================================

            # 任务完成后等待 60 秒，避免在同一分钟内重复执行
            print("任务流程结束，等待 60 秒进入下一分钟...")
            time.sleep(60)

        else:
            # 未到时间，等待 1 秒后继续检查
            time.sleep(1)