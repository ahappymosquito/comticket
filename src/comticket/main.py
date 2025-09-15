"""
1.登录拿取cookie，保存在data/
2.使用cookie登录网站，获取用户所有待审批工单
3.创建组件，创建审批单
4.发送邮件到xuwc2315@fignard.com
"""

from .get_session import get_session
from .creat_comticket import get_user_comticket, creat_components, creat_comtickets, get_component_id

if __name__ == '__main__':
    session = get_session()
    comticket_list = get_user_comticket(session)

    # comticket_list = [
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
    #     'create_component_url': 'http://ats.fingard.net:9561/robot/admin/app/comticket/2954/change/?source=process&redirect=%2Frobot%2Fadmin%2Fapp%2Fcomticket%2F%3Fsender_user__id__exact%3D30'
    #   }
    # ]
    for ticket in comticket_list:
        if ticket.get('target_component') == '-':
            creat_components(ticket)
        creat_comtickets(ticket)
