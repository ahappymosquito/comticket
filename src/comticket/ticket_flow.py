"""ATS 审批台流程（2026-09-04 生产验证）：详情 API → 按需创建组件 → 同轮批准。

旧路径 `/robot/admin/app/component/add/?_popup=1` + `com_group` + `rjf_*` 已废弃。
详情页走 urlPrefix=`robot` 的 `/robot/com/admin/...`；后台表单仍走 `/robot/admin/...`。
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from loguru import logger

from .htmlParser import HtmlParser
from .utils import load_config, save_response_html, send_DingTalk, send_Email

INFO_SCHEMA_KEYS = (
    "系统版本",
    "浏览器",
    "场景",
    "验证类型",
    "区域",
    "浏览器版本",
    "登陆类型",
    "登陆网址",
    "JIRA工单",
)

DEFAULT_INFO = {
    "系统版本": "Microsoft Windows Server 2019 Standard",
    "浏览器": "Google",
    "场景": "网银",
    "验证类型": "无验证",
    "区域": "其他",
    "浏览器版本": "",
    "登陆类型": "其他",
    "登陆网址": "",
    "JIRA工单": "",
}

APPROVED_STATUS = "已批准"
PENDING_STATUS = "待处理"
TICKET_ID_RE = re.compile(r"/comticket/(\d+)/")
COMPONENT_ID_RE = re.compile(r"/component/(\d+)/")

HTML_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) "
        "Gecko/20100101 Firefox/143.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
}

JSON_HEADERS = {
    **HTML_HEADERS,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

FORM_HEADERS = {
    **HTML_HEADERS,
    "Content-Type": "application/x-www-form-urlencoded",
    "Upgrade-Insecure-Requests": "1",
}


def _cfg(config: dict | None) -> dict:
    return config if config is not None else load_config()


def base_url(config: dict | None = None) -> str:
    return _cfg(config)["base_url"].rstrip("/")


def get_component_settings(config: dict | None = None) -> dict[str, str]:
    """读取 `[component]`，缺省对齐 2026-09-04 生产值。"""
    component = _cfg(config).get("component") or {}
    return {
        "tag_id": str(component.get("tag_id", "5")),
        "default_maintainer_id": str(component.get("default_maintainer_id", "30")),
        "default_version": str(component.get("default_version", "3.0.0")),
        "approve_status": str(component.get("approve_status", "31")),
    }


def ticket_list_url(user_id: Any, config: dict | None = None) -> str:
    return f"{base_url(config)}/robot/admin/app/comticket/?sender_user__id__exact={user_id}"


def ticket_detail_path(wid: Any) -> str:
    return f"/robot/com/admin/app/comticket/{wid}/detail/"


def ticket_detail_url(wid: Any, config: dict | None = None) -> str:
    return f"{base_url(config)}{ticket_detail_path(wid)}"


def component_add_url(wid: Any, config: dict | None = None) -> str:
    return (
        f"{base_url(config)}/robot/admin/app/component/add/"
        f"?source=ticket&wid={wid}&redirect={ticket_detail_path(wid)}"
    )


def ticket_change_url(wid: Any, config: dict | None = None) -> str:
    return (
        f"{base_url(config)}/robot/admin/app/comticket/{wid}/change/"
        f"?source=process&redirect={ticket_detail_path(wid)}"
    )


def component_search_url(name: str, config: dict | None = None) -> str:
    return f"{base_url(config)}/robot/admin/app/component/?q={quote(name)}"


def guess_login_type(name: str) -> str:
    """名称含 KEY/UKEY/U盾 → UKEY版；含登录 → 网页版；否则其他。"""
    text = name or ""
    if "U盾" in text or "KEY" in text.upper():
        return "UKEY版"
    if "登录" in text:
        return "网页版"
    return "其他"


def normalize_remark(remark: Any) -> str:
    text = "" if remark is None else str(remark).strip()
    if text in ("", "-"):
        return ""
    return text


def build_component_info(
    name: str,
    remark: str = "",
    extra: dict | None = None,
    config: dict | None = None,
) -> dict[str, str]:
    """构造 django-jsonform 的 `info` 字典，键必须与 schema 完全一致。"""
    info = dict(DEFAULT_INFO)
    configured = ((_cfg(config).get("component") or {}).get("default_info") or {})
    for key in INFO_SCHEMA_KEYS:
        if key in configured and configured[key] is not None:
            info[key] = str(configured[key])
    info["登陆类型"] = guess_login_type(name)
    if extra:
        for key in INFO_SCHEMA_KEYS:
            value = extra.get(key)
            if value not in (None, ""):
                info[key] = str(value)
    return {key: info.get(key, "") for key in INFO_SCHEMA_KEYS}


def dumps_info(info: dict) -> str:
    payload = {key: info.get(key, "") for key in INFO_SCHEMA_KEYS}
    return json.dumps(payload, ensure_ascii=False)


def extract_csrf_token(html: str, fallback: str | None = None) -> str | None:
    soup = BeautifulSoup(html or "", "html.parser")
    field = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if field and field.get("value"):
        return field["value"]
    return fallback


def csrf_from_session(session: requests.Session) -> str | None:
    return session.cookies.get("csrftoken")


def parse_pending_tickets(html: str) -> list[dict[str, str]]:
    """从工单列表 HTML 抽出状态为「待处理」的工单 id，不依赖固定列下标。"""
    parser = HtmlParser(html)
    rows = parser.get_elements("//*[@id='result_list']//tr")
    tickets: list[dict[str, str]] = []
    for row in rows[1:]:
        if _row_status(row) != PENDING_STATUS:
            continue
        wid = _row_ticket_id(row)
        if not wid:
            continue
        name_els = row.get_elements("./th[1]//a") or row.get_elements("./th[1]")
        name = name_els[0].get_text() if name_els else ""
        tickets.append({"wid": wid, "component_name": name, "status": PENDING_STATUS})
    return tickets


def _row_status(row) -> str | None:
    for span in row.get_elements(".//span"):
        text = span.get_text()
        if text in (PENDING_STATUS, APPROVED_STATUS, "已驳回", "已拒绝"):
            return text
    for cell in row.get_elements("./td"):
        text = cell.get_text()
        if text in (PENDING_STATUS, APPROVED_STATUS, "已驳回", "已拒绝"):
            return text
    return None


def _row_ticket_id(row) -> str | None:
    checkbox = row.get_elements('.//input[@name="_selected_action"]')
    if checkbox:
        value = checkbox[0].get_attribute("value")
        if value and str(value).isdigit():
            return str(value)
    for anchor in row.get_elements(".//a"):
        href = anchor.get_attribute("href") or ""
        match = TICKET_ID_RE.search(href)
        if match:
            return match.group(1)
    return None


def parse_component_id(html: str, component_name: str) -> str | None:
    """组件搜索页：`th a` 文本精确匹配后取 `/component/{id}/`。"""
    parser = HtmlParser(html)
    for link in parser.get_elements("//table[@id='result_list']//th//a"):
        if link.get_text() == component_name:
            href = link.get_attribute("href") or ""
            match = COMPONENT_ID_RE.search(href)
            if match:
                return match.group(1)
    return None


def list_pending_tickets(
    session: requests.Session,
    config: dict | None = None,
) -> list[dict[str, Any]]:
    config = _cfg(config)
    user_ids = config.get("user", {}).get("userID", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]

    tickets: list[dict[str, Any]] = []
    for user_id in user_ids:
        url = ticket_list_url(user_id, config)
        logger.info("拉取待处理工单: {}", url)
        response = session.get(url, headers=HTML_HEADERS, timeout=10)
        response.raise_for_status()
        for item in parse_pending_tickets(response.text):
            item["user_id"] = user_id
            tickets.append(item)
    logger.info("待处理工单 {} 条", len(tickets))
    return tickets


def fetch_ticket_detail(
    session: requests.Session,
    wid: Any,
    config: dict | None = None,
) -> dict:
    url = ticket_detail_url(wid, config)
    logger.info("GET 工单详情 {}", url)
    response = session.get(url, headers=JSON_HEADERS, timeout=10)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        save_response_html(response.text, f"detail_{wid}_not_json")
        raise RuntimeError(f"工单 {wid} 详情不是 JSON") from exc
    if payload.get("code") != 1:
        raise RuntimeError(f"工单 {wid} 详情失败: {payload}")
    return payload


def find_component_id(
    session: requests.Session,
    component_name: str,
    config: dict | None = None,
) -> str | None:
    url = component_search_url(component_name, config)
    logger.info("搜索组件 {} -> {}", component_name, url)
    response = session.get(url, headers=HTML_HEADERS, timeout=10)
    response.raise_for_status()
    component_id = parse_component_id(response.text, component_name)
    if component_id:
        logger.info("组件 {} id={}", component_name, component_id)
    else:
        logger.warning("未找到精确匹配的组件: {}", component_name)
        save_response_html(response.text, f"component_search_{component_name}")
    return component_id


def create_component_from_ticket(
    session: requests.Session,
    wid: Any,
    name: str,
    remark: str,
    info: dict,
    config: dict | None = None,
) -> None:
    """GET+POST `/robot/admin/app/component/add/?source=ticket&wid=`，字段为 tags 而非 com_group。"""
    config = _cfg(config)
    settings = get_component_settings(config)
    url = component_add_url(wid, config)
    get_resp = session.get(url, headers=HTML_HEADERS, timeout=10)
    get_resp.raise_for_status()
    csrf = extract_csrf_token(get_resp.text, csrf_from_session(session))
    if not csrf:
        raise RuntimeError(f"创建组件表单缺少 csrf: wid={wid}")

    form = {
        "csrfmiddlewaretoken": csrf,
        "name": name,
        "desc": normalize_remark(remark),
        "tags": settings["tag_id"],
        "maintainer_by": settings["default_maintainer_id"],
        "info": dumps_info(info),
        "_save": "保存",
    }
    headers = {
        **FORM_HEADERS,
        "Referer": url,
        "Origin": base_url(config),
    }
    logger.info("POST 创建组件 wid={} name={} tags={}", wid, name, settings["tag_id"])
    post_resp = session.post(url, headers=headers, data=form, timeout=10)
    if post_resp.status_code >= 400:
        save_response_html(post_resp.text, f"create_component_{wid}_{post_resp.status_code}")
        post_resp.raise_for_status()
    if _django_form_errors(post_resp.text):
        save_response_html(post_resp.text, f"create_component_{wid}_form_error")
        raise RuntimeError(f"创建组件表单校验失败: wid={wid} name={name}")
    logger.success("已提交创建组件: {} (wid={})", name, wid)


def approve_ticket(
    session: requests.Session,
    wid: Any,
    component_id: str,
    remark: str,
    info: dict,
    config: dict | None = None,
) -> None:
    """GET+POST `/robot/admin/app/comticket/{wid}/change/?source=process`。"""
    config = _cfg(config)
    settings = get_component_settings(config)
    url = ticket_change_url(wid, config)
    get_resp = session.get(url, headers=HTML_HEADERS, timeout=10)
    get_resp.raise_for_status()
    csrf = extract_csrf_token(get_resp.text, csrf_from_session(session))
    if not csrf:
        raise RuntimeError(f"审批表单缺少 csrf: wid={wid}")

    form = {
        "csrfmiddlewaretoken": csrf,
        "target_component": component_id,
        "form_process_version": settings["default_version"],
        "form_status": settings["approve_status"],
        "process_remark": normalize_remark(remark) or "自动审批",
        "info": dumps_info(info),
        "_save": "保存",
    }
    headers = {
        **FORM_HEADERS,
        "Referer": url,
        "Origin": base_url(config),
    }
    logger.info(
        "POST 批准工单 wid={} component={} version={} status={}",
        wid,
        component_id,
        settings["default_version"],
        settings["approve_status"],
    )
    post_resp = session.post(url, headers=headers, data=form, timeout=10)
    if post_resp.status_code >= 400:
        save_response_html(post_resp.text, f"approve_{wid}_{post_resp.status_code}")
        post_resp.raise_for_status()
    if _django_form_errors(post_resp.text):
        save_response_html(post_resp.text, f"approve_{wid}_form_error")
        raise RuntimeError(f"审批表单校验失败: wid={wid}")
    logger.success("已提交批准: wid={}", wid)


def process_pending_ticket(
    session: requests.Session,
    wid: Any,
    config: dict | None = None,
) -> dict[str, Any]:
    """同一轮：无目标组件则创建，解析组件 id，批准，并用详情 API 核对「已批准」。"""
    config = _cfg(config)
    detail = fetch_ticket_detail(session, wid, config)
    data = detail.get("data") or {}
    ticket_info = data.get("ticket_info") or {}
    name = ticket_info.get("to_component_name") or ""
    remark = ticket_info.get("remark") or ""
    status = ticket_info.get("status")

    if not name:
        raise RuntimeError(f"工单 {wid} 详情缺少 to_component_name")
    if status == APPROVED_STATUS:
        logger.info("工单 {} 已是「已批准」，跳过", wid)
        return {"wid": str(wid), "status": status, "skipped": True, "ok": True}

    info = build_component_info(name, remark, config=config)
    if not data.get("has_target_component"):
        create_component_from_ticket(session, wid, name, remark, info, config)

    component_id = find_component_id(session, name, config)
    if not component_id:
        raise RuntimeError(f"无法解析组件 id: {name} (wid={wid})")

    approve_ticket(session, wid, component_id, remark, info, config)

    verified = fetch_ticket_detail(session, wid, config)
    new_status = ((verified.get("data") or {}).get("ticket_info") or {}).get("status")
    if new_status != APPROVED_STATUS:
        raise RuntimeError(f"工单 {wid} 批准后状态为 {new_status!r}，期望「{APPROVED_STATUS}」")

    notify_approval_success(name, ticket_info, wid, config)
    logger.success("工单 {} ({}) 已批准", wid, name)
    return {
        "wid": str(wid),
        "status": new_status,
        "component_id": component_id,
        "component_name": name,
        "ok": True,
    }


def notify_approval_success(
    name: str,
    ticket_info: dict,
    wid: Any,
    config: dict | None = None,
) -> None:
    """审批成功后的钉钉/邮件钩子；通知失败不回滚审批、不中断主循环。"""
    config = _cfg(config)
    sender = (
        ticket_info.get("sender_user")
        or ticket_info.get("sender")
        or ticket_info.get("sender_user_name")
        or ""
    )
    message = f"{name} {sender}已审批！".strip()
    try:
        notification_config = config.get("notifications") or {}
        send_DingTalk(message, notification_config.get("approval_at_mobiles", []))
        recipients = notification_config.get("approval_email_recipients") or []
        if recipients:
            send_Email(
                recipients,
                subject=message,
                body=f"ticket {wid} approved: {ticket_detail_url(wid, config)}",
            )
    except Exception:
        logger.exception("工单 {} 已批准，但通知发送失败", wid)


def _django_form_errors(html: str) -> bool:
    if not html:
        return False
    markers = (
        "errorlist",
        "这个字段是必填项",
        "This field is required",
        "请修正下面的错误",
        "Please correct the error",
    )
    return any(marker in html for marker in markers)
