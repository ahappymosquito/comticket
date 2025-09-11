"""
2.使用cookie登录网站，获取用户所有待审批工单
"""

from loguru import logger
import requests
from bs4 import BeautifulSoup
from lxml import etree
from parsel import Selector
from .utils import *
from .htmlParser import *

def get_user_comticket(session):
    config = load_config()
    base_url = config["base_url"]
    user_id = config["user"]["userID"]
    user_url = f"{base_url}/robot/admin/app/comticket/?sender_user__id__exact={user_id}"

    response = session.get(user_url)
    save_response_html(response.text)

    """
    http://ats.fingard.net:9561/robot/admin/app/comticket/2903/change/?source=process&redirect=%2Frobot%2Fadmin%2Fapp%2Fcomticket%2F%3Fsender_user__id__exact%3D30
    """

    # html = etree.HTML(response.text)
    # sel = Selector(text=response.text)

    # with open(r"D:\RPA\comticket\data\response\response_20250911_211558.html", 'r', encoding='utf-8') as source_file:
    #     content = source_file.read()

    content = response.text

    parser = HtmlParser(content)
    tr_list = parser.get_elements("//*[@id='result_list']//tr")

    for tr in tr_list[1:]:
        comticket_id = tr.get_elements('./td[last()]/div/a[2]')[0].get_attribute('href')
        logger.error(comticket_id)
        # cell_texts = [cell.get('value') for cell in comticket_id]
        # print(cell_texts)
        # creat_url = f"{base_url}/robot/admin/app/comticket/{comticket_id}/change/?source=process&redirect=%2Frobot%2Fadmin%2Fapp%2Fcomticket%2F%3Fsender_user__id__exact%3D{user_id}"


if __name__ == '__main__':
    get_user_comticket()