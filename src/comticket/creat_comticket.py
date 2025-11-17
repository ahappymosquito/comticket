"""
2.使用cookie登录网站，获取用户所有待审批工单
"""
import json
import re

from loguru import logger
import requests
from bs4 import BeautifulSoup
from lxml import etree
from parsel import Selector
from .utils import *
from .htmlParser import *

# 根据remark解析字段
def get_rjf_info(remark):
    base_info = {
        "系统版本": "Windows10;windows11;windows server;",
        "浏览器": "Google;IE;Firefox;Edge",
        "场景": "网银;电商;其他",
        "验证类型": "无验证;纯英数;单滑块;双滑块;文字点选;轨迹滑块;数学运算;动画英数;图片点选;其他",
        "区域": "境内;境外;其他",
        "浏览器版本": "140.0.7339.128",
        "登陆类型": "其他;网页版;UKEY版;客户端",
        "登陆网址": "https://default.com;",
        "JIRA工单": "RPA-0001;"
    }

    specific_info = {
        "登陆地址": base_info.get("登陆网址",""),
        "浏览器类型": base_info.get("浏览器",""),
        "验证码类型": base_info.get("验证类型",""),
    }

    base_info = llm(remark,base_info)
    logger.debug("{}".format(base_info))
    base_info = json.loads(base_info)

    final_info = base_info.copy()
    final_info.update(specific_info)
    return {"component": base_info, "comticket": final_info}

# 获取用户需要审批的审批单 [row_data,row_data,row_data]
def get_user_comticket(session):
    config = load_config()
    base_url = config["base_url"]
    user_list = config["user"]["userID"]
    ticket_list = []
    for user_id in user_list:
        user_url = f"{base_url}/robot/admin/app/comticket/?sender_user__id__exact={user_id}"

        response = session.get(user_url)
        # save_response_html(response.text)

        content = response.text
        parser = HtmlParser(content)


        tr_list = parser.get_elements("//*[@id='result_list']//tr")

        # Iterate through each row, skipping the header (tr_list[0])
        for tr in tr_list[1:]:
            # Get the status text from the 6th cell (index 5)
            # The XPath index is 1-based, so td[6] is the 6th td element
            stat_element = tr.get_elements('./td[5]/span')
            if not stat_element:
                continue  # Skip if the status element doesn't exist

            stat = stat_element[0].get_text()

            # Process only the rows with the status '待处理'
            if stat == '待处理':
                # --- Extract elements using their index positions ---

                # Note: The first column is a checkbox (td[1]), the second is a th.
                # We will adjust for this structure.

                # <th> is the 2nd child of <tr>
                component_name = tr.get_elements('./th[1]')[0].get_text()

                # <td> elements start after the <th>
                sender_user = tr.get_elements('./td[2]')[0].get_text()
                remark = tr.get_elements('./td[3]')[0].get_text()
                customer = tr.get_elements('./td[4]')[0].get_text()
                # 'stat' is already extracted
                target_component = tr.get_elements('./td[6]')[0].get_text()
                target_component_version = tr.get_elements('./td[7]')[0].get_text()
                change_info = tr.get_elements('./td[8]')[0].get_text().strip()  # .strip() to remove extra whitespace
                refer_info = tr.get_elements('./td[9]/div//span')[0].get_text().strip()
                more_info = tr.get_elements('./td[10]')[0].get_text()  # '查看更多'
                create_at = tr.get_elements('./td[11]')[0].get_text()
                download_and_open = tr.get_elements('./td[12]')[0].get_text().strip()

                create_ticket_url_element = tr.get_elements('./td[last()]/div/a[2]')
                create_ticket_url = create_ticket_url_element[0].get_attribute(
                    'href') if create_ticket_url_element else ""

                # --- Store the extracted data in a dictionary ---
                row_data = {
                    'component_name': component_name,
                    'sender_user': sender_user,
                    'remark': remark,
                    'customer': customer,
                    'status': stat,
                    'target_component': target_component,
                    'target_component_version': target_component_version,
                    'change_info': change_info,
                    'refer_info': refer_info,
                    'more_info': more_info,
                    'create_at': create_at,
                    'create_component_url': create_ticket_url,
                    'rjf_info': get_rjf_info(remark),
                    'user_id': user_id
                }

                # --- Append the dictionary to the list ---
                ticket_list.append(row_data)
    # [
    #   {
    #     'component_name': '招商永隆_明细查询组件',
    #     'sender_user': '徐文超',
    #     'remark': '测试，勿用',
    #     'customer': '-',
    #     'status': '待处理',
    #     'target_component': '-',
    #     'target_component_version': '-',
    #     'change_info': '变更',
    #     'refer_info': '-',
    #     'more_info': '查看更多',
    #     'create_at': '09月12日',
    #     'create_component_url': '_user__id__exact%3D30'
    #   }
    # ]
    logger.info(ticket_list)
    return ticket_list

#先检查有没有已有组件，获取版本号再+1返回
def check_component(ticket):
    query_url = f'http://ats.fingard.net:9561/robot/admin/app/component/?q={ticket["component_name"]}'
    check_headers = {
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
        logger.info(f"正在查询 {query_url.split('?q=')[1]}")
        response = requests.get(query_url, headers=check_headers, cookies=cookies, timeout=10)

        logger.info(f"状态码: {response.status_code}")
        if response.status_code == 200:
            logger.success("请求成功，返回200")
            content = response.text
            arserp = HtmlParser(content)

            if arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[@class='field-get_cur_version']/a"):
                # 已有组件，返回版本号+1
                #" 3.0.2 (3个版本) "    " 3.3 (5个版本) ",
                version_num = arserp.get_elements("//table[@id='result_list']//tbody/tr[1]/td[@class='field-get_cur_version']/a")[0].get_text()
                version_num = version_num.strip().split(' ')[0]

                #处理版本号+1
                version_num = bump_version(version_num)
                return version_num
            else:
                #创建成功，返回3.0.0
                return creat_components(ticket)
            # return version_num
        else:
            logger.warning(f"请求失败，状态码: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"请求异常: {e}")

# 没有组件，创建组件
def creat_components(ticket):
    ## ======================================= ##
    post_url = "http://ats.fingard.net:9561/robot/admin/app/component/add/?_to_field=id&_popup=1"

    headers = {
        'Host': 'ats.fingard.net:9561',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': 'http://ats.fingard.net:9561/robot/admin/app/component/add/?_to_field=id&_popup=1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'http://ats.fingard.net:9561',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Priority': 'u=0, i',
    }

    rjf_info = ticket["rjf_info"]["component"]

    form_data = {
        'csrfmiddlewaretoken': "cookie获取，需要覆盖",
        '_popup': '1',
        'name': '需要覆盖',
        'desc': '需要覆盖',
        'com_group': '23',  ## 3.0网银代码
        'rjf§系统版本': rjf_info['系统版本'],
        'rjf§浏览器': rjf_info['浏览器'],
        'rjf§场景': rjf_info['场景'],
        'rjf§验证类型': rjf_info['验证类型'],
        'rjf§区域': rjf_info['区域'],
        'rjf§浏览器版本': rjf_info['浏览器版本'],
        'rjf§登陆类型': rjf_info['登陆类型'],
        'rjf§登陆网址': rjf_info['登陆网址'],
        'rjf§JIRA工单': rjf_info['JIRA工单'],
        'info': json.dumps(rjf_info, ensure_ascii=False),  # 将字典转换为JSON字符串
        'maintainer_by': ticket['user_id'],
        '_save': '保存'
    }

    session_cookies = load_session_cookies()

    com = ticket.copy()

    session = requests.Session()

    session.cookies.update(session_cookies)

    # 动态修改表单数据，例如根据url或索引更新组件名称
    current_form_data = form_data.copy()
    current_form_data['csrfmiddlewaretoken'] = get_session_csrftoken()
    current_form_data['name'] = com.get('component_name')
    current_form_data['desc'] = com.get('remark')
    current_form_data['com_group'] = '23' ## 3.0网银代码


    try:
        logger.info(f"正在为 '{com.get('component_name')}' 创建组件: {current_form_data['name']}...")

        # 发送POST请求
        response = session.post(post_url, headers=headers, data=current_form_data)

        # 检查响应
        response.raise_for_status()  # 如果请求失败 (状态码不是 2xx)，则抛出异常


        # 根据返回内容判断是否真的成功
        if "RPA组件版本管理系统" in response.text:
            logger.success(f"成功为  '{com.get('component_name')}' 创建组件。")
            # time.sleep(5)
            return '3.0.0'
        else:
            # 打印响应内容以便调试
            logger.debug("响应内容:", response.text)
            pass
    except requests.exceptions.RequestException as e:
        logger.error(f"为 '{com.get('component_name')}' 创建组件时发生错误: {e}")

# 获取组件id，审批单需要此字段
def get_component_id(component_name):
    url = f"http://ats.fingard.net:9561/robot/admin/app/component/?q={component_name}"
    headers = {
        "Host": "ats.fingard.net:9561",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Priority": "u=0, i",
    }

    session_cookies = load_session_cookies()

    session = requests.Session()
    session.cookies.update(session_cookies)

    try:
        logger.info(f"正在查询 {component_name} 的组件 ID...")
        response = session.get(url, headers=headers, allow_redirects=False, timeout=10)
    except requests.exceptions.RequestException as e:
        logger.error(f"查询 {component_name} 时发生网络错误: {e}")
        return None
    logger.info(f"响应状态码: {response.status_code}")
    if response.status_code == 200:
        # logger.debug(f"响应内容预览: {response.text[:100]}...")
        logger.debug(f"创建组件成功√")
        # save_response_html(response.text,'组件')
    else:
        logger.warning(f"非 200 响应: {response.status_code}, 内容预览: {response.text[:200]}")

    content = response.text
    parser = HtmlParser(content)
    com_name = parser.get_elements("//*[@id='result_list']//tbody/tr[1]/th/a")[0]
    if com_name.get_text() == component_name:
        # logger.info(com_name.get_attribute('href'))
        match = re.search(r"/component/(\d+)/",com_name.get_attribute('href'))
        component_id = match.group(1)
        logger.info(component_id)
        return component_id
    else:
        return None

# 填写审批单
def creat_comtickets(comticket_info):
    match = re.search(r"/comticket/(\d+)/", comticket_info['create_component_url'])
    comticket_id = match.group(1)

    base_url = f"http://ats.fingard.net:9561/robot/admin/app/comticket/{comticket_id}/change/"
    redirect_path = f"/robot/admin/app/comticket/?sender_user__id__exact={comticket_info['user_id']}"
    post_url = f"{base_url}?source=process&redirect={redirect_path}"

    logger.info(comticket_info["refer_info"])

    # 叠加版本号
    # if comticket_info["refer_info"] !='-':
    #     version = comticket_info["refer_info"]
    #     target_component_version = ".".join(version.split(".")[:-1] + [str(int(version.split(".")[-1]) + 1)])
    # else:
    #     target_component_version = '3.0.0'
    target_component_version = check_component(comticket_info)

    # 2. 设置请求头
    headers = {
        'Host': 'ats.fingard.net:9561',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': post_url,  # Referer 通常与请求的URL相同
        'Origin': 'http://ats.fingard.net:9561',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Priority': 'u=0, i',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }


    rjf_info = comticket_info["rjf_info"]["comticket"]

    form_data = {
        'csrfmiddlewaretoken': '需要覆盖',
        'target_component': get_component_id(comticket_info.get("component_name")),
        'form_process_version': target_component_version,
        'form_status': '31',  # 应该是是审批批准
        'process_remark': comticket_info.get('remark'),
        'rjf§系统版本': rjf_info['系统版本'],
        'rjf§浏览器': rjf_info['浏览器'],
        'rjf§场景': rjf_info['场景'],
        'rjf§验证类型': rjf_info['验证类型'],
        'rjf§区域': rjf_info['区域'],
        'rjf§浏览器版本': rjf_info['浏览器版本'],
        'rjf§登陆类型': rjf_info['登陆类型'],
        'rjf§登陆网址': rjf_info['登陆网址'],
        'rjf§JIRA工单': rjf_info['JIRA工单'],
        'info': json.dumps(rjf_info, ensure_ascii=False),
        '_save': '保存'
    }

    # 4. 加载会话 cookies
    session_cookies = load_session_cookies()
    if not session_cookies:
        logger.info("错误：无法加载会话 cookies。请先登录。")
        return

    # 5. 发送请求
    session = requests.Session()
    session.cookies.update(session_cookies)

    current_form_data = form_data.copy()
    current_form_data['csrfmiddlewaretoken'] = get_session_csrftoken()

    try:
        logger.info(f"正在更新 Comticket ID: {comticket_id}...")

        # 发送POST请求，allow_redirects=False 以捕获302响应
        response = session.post(post_url, headers=headers, data=current_form_data, allow_redirects=False)

        # 6. 检查响应
        # logger.info(f"响应状态码: {response.status_code}")

        if response.status_code == 302:
            redirect_location = response.headers.get('location')

            send_DingTalk(comticket_info["component_name"]+ " "+comticket_info["sender_user"]+"已审批！",["17538215922"])
            send_Email(['xuwc2315@fingard.com'],subject=comticket_info["component_name"]+ " "+comticket_info["sender_user"]+"已审批！",body=redirect_location)

            logger.success(f"请求成功，服务器按预期返回302重定向。")
            # logger.info(f"重定向到: {redirect_location}")
        elif response.status_code == 200:
            logger.error("警告：服务器返回了200，检查下组件版本是否正确")
            save_response_html(response.text,'审批单创建失败')
        else:
            logger.info(f"请求失败，状态码: {response.status_code}")
            response.raise_for_status()  # 抛出异常

    except requests.exceptions.RequestException as e:
        logger.info(f"更新 Comticket {comticket_id} 时发生网络错误: {e}")