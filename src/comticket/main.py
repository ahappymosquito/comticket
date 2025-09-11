"""
1.登录拿取cookie，保存在data/
2.使用cookie登录网站，获取用户所有待审批工单
3.创建组件，创建审批单
4.发送邮件到xuwc2315@fignard.com
"""

from .get_session import get_session
from .creat_comticket import get_user_comticket

if __name__ == '__main__':
    session = get_session()
    get_user_comticket(session)


