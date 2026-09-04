import time

from loguru import logger

from .check_component_update import *
from .get_session import get_session
from .ticket_flow import list_pending_tickets, process_pending_ticket
from .utils import *

# 日志配置：每天一个文件，保留 7 天，超过自动压缩
logger.add(
    "logs/comticket_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    compression="zip",
    encoding="utf-8",
    level="INFO",
)

if __name__ == "__main__":
    check_list = ["网银查询业务组件模板", "网银客户端登录组件模板", "网银浏览器登录组件模板"]

    while True:
        try:
            session = get_session()
        except Exception as e:
            logger.exception(f"未能成功登录,原因：{e}")
            time.sleep(10)
            continue

        run(check_list)

        try:
            comticket_list = list_pending_tickets(session)
            logger.info(f"获取到 {len(comticket_list)} 条待审批工单")

            for ticket in comticket_list:
                wid = ticket.get("wid")
                name = ticket.get("component_name")
                try:
                    logger.info(f"开始处理工单 {wid}: {name}（同轮创建+批准）")
                    process_pending_ticket(session, wid)
                except Exception as e:
                    logger.exception(f"处理工单出错: {name} (wid={wid}), error={e}")

        except Exception as e:
            logger.exception(f"本轮审批台流程执行失败,{e}")

        logger.info("等待 10 秒后再次执行...")
        time.sleep(10)
