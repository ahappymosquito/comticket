"""兼容入口。审批台创建/批准已迁到 ticket_flow，此处只保留薄包装。

旧 popup `/robot/admin/app/component/add/?_to_field=id&_popup=1`、
`com_group=23`、`rjf_*` 字段和「version==3.0.0 则不审批」逻辑已删除。
"""

from .ticket_flow import (
    find_component_id,
    list_pending_tickets,
    process_pending_ticket,
)

# 列表入口仍可用；创建/批准决策请走详情 API。
get_user_comticket = list_pending_tickets


def creat_comtickets(ticket, session=None):
    """同一轮创建（如需）并批准。需要 session；ticket 至少含 wid。"""
    if session is None:
        from .get_session import get_session

        session = get_session()
    wid = ticket.get("wid") if isinstance(ticket, dict) else ticket
    if not wid:
        raise ValueError("creat_comtickets 需要 ticket['wid']")
    return process_pending_ticket(session, wid)


def get_component_id(component_name, session=None):
    if session is None:
        from .get_session import get_session

        session = get_session()
    return find_component_id(session, component_name)


def creat_components(*_args, **_kwargs):
    raise RuntimeError(
        "旧 popup 创建路径已移除。请使用 ticket_flow.create_component_from_ticket"
        "（/robot/admin/app/component/add/?source=ticket&wid=...，字段 tags 而非 com_group）。"
    )


def check_component(*_args, **_kwargs):
    raise RuntimeError(
        "旧 check_component / 版本 +1 路径已移除。"
        "审批版本使用 [component].default_version（默认 3.0.0）。"
    )
