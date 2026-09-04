"""审批台流程的无网络回归：schema、列表解析、同轮创建+批准。"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from src.comticket.creat_comticket import creat_components, get_user_comticket
from src.comticket.ticket_flow import (
    INFO_SCHEMA_KEYS,
    build_component_info,
    component_add_url,
    dumps_info,
    extract_csrf_token,
    get_component_settings,
    guess_login_type,
    list_pending_tickets,
    normalize_remark,
    parse_component_id,
    parse_pending_tickets,
    process_pending_ticket,
    ticket_change_url,
    ticket_detail_url,
)


SAMPLE_CONFIG = {
    "base_url": "https://ats.example.com",
    "user": {"userID": [30]},
    "component": {
        "tag_id": "5",
        "default_maintainer_id": "30",
        "default_version": "3.0.0",
        "approve_status": "31",
        "default_info": {
            "系统版本": "Microsoft Windows Server 2019 Standard",
            "浏览器": "Google",
            "场景": "网银",
            "验证类型": "无验证",
            "区域": "其他",
        },
    },
    "notifications": {},
}

LIST_HTML = """
<table id="result_list">
  <thead><tr><th>组件</th></tr></thead>
  <tbody>
    <tr>
      <td class="action-checkbox">
        <input type="checkbox" name="_selected_action" value="101">
      </td>
      <th class="field-to_component_name">
        <a href="/robot/admin/app/comticket/101/change/">招商银行_UKEY登录组件</a>
      </th>
      <td>张三</td>
      <td>备注含待处理字样也不该误判整行</td>
      <td>-</td>
      <td><span class="status">待处理</span></td>
    </tr>
    <tr>
      <td class="action-checkbox">
        <input type="checkbox" name="_selected_action" value="102">
      </td>
      <th>
        <a href="/robot/admin/app/comticket/102/change/">已批组件</a>
      </th>
      <td>李四</td>
      <td>-</td>
      <td>-</td>
      <td><span>已批准</span></td>
    </tr>
  </tbody>
</table>
"""

SEARCH_HTML = """
<table id="result_list">
  <tbody>
    <tr>
      <th class="field-name">
        <a href="/robot/admin/app/component/55/change/">招商银行_UKEY登录组件</a>
      </th>
    </tr>
    <tr>
      <th>
        <a href="/robot/admin/app/component/56/change/">其他组件</a>
      </th>
    </tr>
  </tbody>
</table>
"""

CSRF_HTML = """
<form method="post">
  <input type="hidden" name="csrfmiddlewaretoken" value="form-csrf-token">
</form>
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.cookies = {"csrftoken": "cookie-csrf"}

    def _handle(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        for prefix, response in self.routes:
            if url.startswith(prefix) or prefix in url:
                return response
        raise AssertionError(f"unexpected {method} {url}")

    def get(self, url, **kwargs):
        return self._handle("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._handle("POST", url, **kwargs)


def test_guess_login_type_ukey_and_web():
    assert guess_login_type("某某银行_UKEY转账") == "UKEY版"
    assert guess_login_type("某某银行_KEY证书") == "UKEY版"
    assert guess_login_type("某某银行_U盾查询") == "UKEY版"
    assert guess_login_type("某某银行_登录组件") == "网页版"
    assert guess_login_type("某某银行_明细查询") == "其他"


def test_normalize_remark_treats_dash_as_empty():
    assert normalize_remark("-") == ""
    assert normalize_remark("  -  ") == ""
    assert normalize_remark(None) == ""
    assert normalize_remark("测试，勿用") == "测试，勿用"


def test_build_component_info_uses_exact_schema_and_defaults():
    info = build_component_info("某行_UKEY登录", remark="-", config=SAMPLE_CONFIG)
    assert list(info) == list(INFO_SCHEMA_KEYS)
    assert info["场景"] == "网银"
    assert info["验证类型"] == "无验证"
    assert info["区域"] == "其他"
    assert info["系统版本"] == "Microsoft Windows Server 2019 Standard"
    assert info["浏览器"] == "Google"
    assert info["登陆类型"] == "UKEY版"
    payload = json.loads(dumps_info(info))
    assert list(payload) == list(INFO_SCHEMA_KEYS)


def test_urls_use_com_admin_detail_and_ticket_source():
    detail = ticket_detail_url(88, SAMPLE_CONFIG)
    assert detail == "https://ats.example.com/robot/com/admin/app/comticket/88/detail/"

    add = component_add_url(88, SAMPLE_CONFIG)
    parsed = urlparse(add)
    assert parsed.path == "/robot/admin/app/component/add/"
    query = parse_qs(parsed.query)
    assert query["source"] == ["ticket"]
    assert query["wid"] == ["88"]
    assert query["redirect"] == ["/robot/com/admin/app/comticket/88/detail/"]

    change = ticket_change_url(88, SAMPLE_CONFIG)
    parsed = urlparse(change)
    assert parsed.path == "/robot/admin/app/comticket/88/change/"
    query = parse_qs(parsed.query)
    assert query["source"] == ["process"]


def test_parse_pending_tickets_ignores_approved_and_column_order():
    tickets = parse_pending_tickets(LIST_HTML)
    assert [t["wid"] for t in tickets] == ["101"]
    assert tickets[0]["component_name"] == "招商银行_UKEY登录组件"


def test_parse_component_id_requires_exact_th_text():
    assert parse_component_id(SEARCH_HTML, "招商银行_UKEY登录组件") == "55"
    assert parse_component_id(SEARCH_HTML, "不存在") is None


def test_extract_csrf_prefers_form_field():
    assert extract_csrf_token(CSRF_HTML, fallback="cookie") == "form-csrf-token"
    assert extract_csrf_token("<html></html>", fallback="cookie") == "cookie"


def test_get_component_settings_defaults():
    settings = get_component_settings({"component": {}})
    assert settings == {
        "tag_id": "5",
        "default_maintainer_id": "30",
        "default_version": "3.0.0",
        "approve_status": "31",
    }


def test_list_pending_tickets_uses_configured_user():
    session = FakeSession(
        [
            (
                "/robot/admin/app/comticket/?sender_user__id__exact=30",
                FakeResponse(text=LIST_HTML),
            )
        ]
    )
    tickets = list_pending_tickets(session, SAMPLE_CONFIG)
    assert len(tickets) == 1
    assert tickets[0]["user_id"] == 30
    assert get_user_comticket is list_pending_tickets


def test_old_popup_create_is_removed():
    with pytest.raises(RuntimeError, match="popup"):
        creat_components({"component_name": "x"})


def test_process_pending_ticket_creates_then_approves_same_pass(monkeypatch):
    pending = {
        "code": 1,
        "data": {
            "has_target_component": False,
            "ticket_info": {
                "to_component_name": "招商银行_UKEY登录组件",
                "remark": "-",
                "status": "待处理",
                "sender_user": "张三",
            },
        },
    }
    approved = {
        "code": 1,
        "data": {
            "has_target_component": True,
            "ticket_info": {
                "to_component_name": "招商银行_UKEY登录组件",
                "remark": "-",
                "status": "已批准",
                "sender_user": "张三",
            },
        },
    }
    detail_calls = {"n": 0}

    def detail_response():
        detail_calls["n"] += 1
        payload = pending if detail_calls["n"] == 1 else approved
        return FakeResponse(json_data=payload, text=json.dumps(payload))

    class DetailThenRest(FakeSession):
        def get(self, url, **kwargs):
            if urlparse(url).path.endswith("/comticket/101/detail/"):
                self.calls.append({"method": "GET", "url": url, "kwargs": kwargs})
                return detail_response()
            return super().get(url, **kwargs)

    session = DetailThenRest(
        [
            ("/robot/admin/app/component/add/", FakeResponse(text=CSRF_HTML)),
            ("/robot/admin/app/component/?q=", FakeResponse(text=SEARCH_HTML)),
            ("/robot/admin/app/comticket/101/change/", FakeResponse(text=CSRF_HTML)),
        ]
    )
    monkeypatch.setattr("src.comticket.ticket_flow.notify_approval_success", lambda *a, **k: None)

    result = process_pending_ticket(session, "101", SAMPLE_CONFIG)
    assert result["ok"] is True
    assert result["status"] == "已批准"
    assert result["component_id"] == "55"

    posts = [c for c in session.calls if c["method"] == "POST"]
    assert len(posts) == 2
    create_data = posts[0]["kwargs"]["data"]
    assert create_data["tags"] == "5"
    assert "com_group" not in create_data
    assert create_data["maintainer_by"] == "30"
    assert create_data["desc"] == ""
    assert create_data["_save"] == "保存"
    info = json.loads(create_data["info"])
    assert list(info) == list(INFO_SCHEMA_KEYS)
    assert info["登陆类型"] == "UKEY版"

    approve_data = posts[1]["kwargs"]["data"]
    assert approve_data["target_component"] == "55"
    assert approve_data["form_process_version"] == "3.0.0"
    assert approve_data["form_status"] == "31"
    assert "source=ticket" in posts[0]["url"]
    assert "source=process" in posts[1]["url"]

    xhr_gets = [
        c
        for c in session.calls
        if c["method"] == "GET" and "/detail/" in c["url"]
    ]
    assert xhr_gets
    assert xhr_gets[0]["kwargs"]["headers"]["X-Requested-With"] == "XMLHttpRequest"


def test_approve_skips_create_when_target_exists(monkeypatch):
    payload = {
        "code": 1,
        "data": {
            "has_target_component": True,
            "ticket_info": {
                "to_component_name": "招商银行_UKEY登录组件",
                "remark": "联调",
                "status": "待处理",
            },
        },
    }
    approved = {
        "code": 1,
        "data": {
            "has_target_component": True,
            "ticket_info": {
                "to_component_name": "招商银行_UKEY登录组件",
                "remark": "联调",
                "status": "已批准",
            },
        },
    }
    n = {"i": 0}

    class Session(FakeSession):
        def get(self, url, **kwargs):
            if urlparse(url).path.endswith("/comticket/101/detail/"):
                self.calls.append({"method": "GET", "url": url, "kwargs": kwargs})
                n["i"] += 1
                data = payload if n["i"] == 1 else approved
                return FakeResponse(json_data=data, text=json.dumps(data))
            return super().get(url, **kwargs)

    session = Session(
        [
            ("/robot/admin/app/component/?q=", FakeResponse(text=SEARCH_HTML)),
            ("/robot/admin/app/comticket/101/change/", FakeResponse(text=CSRF_HTML)),
        ]
    )
    monkeypatch.setattr("src.comticket.ticket_flow.notify_approval_success", lambda *a, **k: None)
    result = process_pending_ticket(session, "101", SAMPLE_CONFIG)
    assert result["ok"] is True
    posts = [c for c in session.calls if c["method"] == "POST"]
    assert len(posts) == 1
    assert "comticket/101/change/" in posts[0]["url"]
