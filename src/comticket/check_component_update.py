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
            logger.info(f"正在查询 {component_name}")
            response = requests.get(query_url, headers=headers, cookies=cookies, timeout=10)

            logger.info(f"状态码: {response.status_code}")
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

                    return_list.append( (component_name,version, mark, name,date) )
                else:
                    logger.warning("哪有这组件啊！？")
            else:
                logger.warning(f"请求失败，状态码: {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"请求异常: {e}")
            return return_list
    return return_list


if __name__ == '__main__':
    check_component_update(["网银查询业务组件模板"])
    # check_component_update("网银客户端登录组件模板")
    # check_component_update("网银浏览器登录组件模板")
