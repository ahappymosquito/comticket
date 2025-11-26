import time
from loguru import logger
from .get_session import get_session
from .creat_comticket import (
    get_user_comticket,
    creat_comtickets,
)
from .check_component_update import *
from .utils import *

# 日志配置：每天一个文件，保留 7 天，超过自动压缩
logger.add(
    "logs/comticket_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    compression="zip",
    encoding="utf-8",
    level="INFO"
)

if __name__ == '__main__':
    check_list = ["网银查询业务组件模板","网银客户端登录组件模板","网银浏览器登录组件模板","网银任务结束组件"]

    while True:
        try:
            # 获取登录cookie
            session = get_session()
        except Exception as e:
            logger.exception(f"未能成功登录,原因：{e}")

        run(check_list)

        try:
            # 获取用户待审批 审批单
            comticket_list = get_user_comticket(session)
            logger.info(f"获取到 {len(comticket_list)} 条待审批工单")

            for ticket in comticket_list:
                try:
                    logger.info(f"开始创建审批单: {ticket.get('component_name')}")
                    creat_comtickets(ticket)

                except Exception as e:
                    logger.exception(f"处理工单出错: {ticket.get('component_name')},error{e}")

        except Exception as e:
            logger.exception(f"本轮创建审批单执行失败,{e}")

        logger.info("等待 10 秒后再次执行...")
        time.sleep(10)
