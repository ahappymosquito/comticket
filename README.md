# comticket

面向内部 RPA / ATS 组件平台的自动化处理服务：定时检查组件版本更新，读取待审批工单，在**同一轮**按需创建组件并批准，再通过钉钉和 SMTP 发送通知。

> 当前代码针对 Django Admin + 审批台详情 API。公开仓库用于二次开发参考；接入自己的平台前，需要替换接口地址、表单字段、状态值和通知策略。

**v0.3.0 是破坏性流程变更。** 2026-09-04 生产验证（8/8 工单）后，已废弃 `creat_comticket.py` 的 popup 创建路径；主路径不再依赖 LLM。

## 旧流程 vs 新流程

| | 旧路径（已删除） | 新路径（必须使用） |
| --- | --- | --- |
| 创建组件 | popup `GET/POST /robot/admin/app/component/add/?_to_field=id&_popup=1` | `GET/POST /robot/admin/app/component/add/?source=ticket&wid={wid}&redirect=/robot/com/admin/app/comticket/{wid}/detail/` |
| 分类字段 | `com_group=23` + LLM 拼的 `rjf_*` | `tags=5`（文案：`3.0模板网银组件`），无 `rjf_*` |
| 组件元数据 | LLM 补全，键不稳定 | `info` 必须是 django-jsonform 的精确键 JSON |
| 审批时机 | `creat_comtickets` 在 version==`3.0.0` 时直接 `return`，下一轮才批（f78acd0） | **同一轮**创建（如需）后立即批准 |
| 决策依据 | 列表 HTML 列下标 + 混合 cookie Session | 列表只取待处理 id；创建/批准看详情 JSON |
| LLM | 创建/批准阻塞依赖 `zai` | 默认关闭，不阻塞审批 |

### ATS URL 约定

平台 `urlPrefix` 为 `robot`：

- 登录 / 工单列表 / 组件搜索 / 创建表单 / 审批表单：`/robot/admin/...`
- 工单详情 JSON（审批台）：`/robot/com/admin/app/comticket/{wid}/detail/`
  - 请求头必须带 `X-Requested-With: XMLHttpRequest`
  - `code == 1` 时使用 `data.ticket_info`（`to_component_name`、`remark`、`status`）和 `data.has_target_component`

不要把详情路径写成 `/robot/admin/app/comticket/{id}/detail/`。

## 新流程（主循环）

1. `get_session.py`：Django admin 登录，Cookie 写入 `data/session_cookies.pkl`。
2. 按配置的 `user.userID` 打开  
   `/robot/admin/app/comticket/?sender_user__id__exact={id}`，只收集状态文本为 `待处理` 的工单 id（`wid`）。
3. 对每个 `wid` 调用 `process_pending_ticket`（**创建与批准在同一轮**）：
   1. `GET` 详情 API。
   2. 若 `has_target_component` 为 false：GET 再 POST 创建组件。
      - `name` = `ticket_info.to_component_name`
      - `desc` = `remark`（值为 `-` 时留空）
      - `tags` = `[component].tag_id`（默认 `5`）
      - `maintainer_by` = `[component].default_maintainer_id`（默认 `30`，徐文超）
      - `info` = 下列键的 JSON 字符串，缺键或空 `info` 会触发 schema 错误：  
        `系统版本`、`浏览器`、`场景`、`验证类型`、`区域`、`浏览器版本`、`登陆类型`、`登陆网址`、`JIRA工单`
      - 默认：`场景=网银`，`验证类型=无验证`，`区域=其他`，  
        `系统版本=Microsoft Windows Server 2019 Standard`，`浏览器=Google`
      - `登陆类型`：名称含 `KEY` / `UKEY` / `U盾` → `UKEY版`；含 `登录` → `网页版`；否则 `其他`
      - `csrfmiddlewaretoken`，`_save=保存`
   3. 在 `/robot/admin/app/component/?q={name}` 用 `th a` **精确匹配**解析组件 id。
   4. GET 再 POST  
      `/robot/admin/app/comticket/{wid}/change/?source=process&redirect=/robot/com/admin/app/comticket/{wid}/detail/`  
      字段：`target_component`、`form_process_version`（默认 `3.0.0`）、`form_status=31`（批准；`32`=驳回）、`process_remark`、`info`、`_save`、csrf。
   5. 再拉详情 API，确认 `status == 已批准`。
   6. 成功后走钉钉 / 邮件钩子；通知失败只打日志，不回滚审批、不中断循环。

实现入口：`src/comticket/ticket_flow.py`。`creat_comticket.py` 仅保留 `get_user_comticket` / `creat_comtickets` 薄包装。

## 功能概览

- 使用 `requests.Session` 登录并复用本地 Cookie。
- 轮询待审批工单，按详情 API 决定是否创建组件，并在同一轮批准。
- 通过钉钉机器人和 SMTP 发送成功/失败通知。
- 将模板组件版本监控结果保存到 SQLite，检测到更新时通知群组。
- 保存失败响应 HTML，方便定位上游页面或字段变化。
- LLM（Zhipu / `zai`）为可选能力，默认关闭，不参与创建/批准主路径。

## 项目结构

```text
.
├── config.example.toml       # 脱敏配置模板，复制为 config.toml 后填写
├── pyproject.toml             # Poetry 项目定义与依赖
├── scripts/
│   ├── run.bat
│   └── run.sh
├── src/
│   ├── comticket/
│   │   ├── main.py            # 主循环：登录、同轮创建+批准、定时监控
│   │   ├── get_session.py     # 登录与 Cookie 持久化
│   │   ├── ticket_flow.py     # 审批台详情 / 创建 / 批准
│   │   ├── creat_comticket.py # 兼容薄包装（不再走 popup）
│   │   ├── check_component_update.py
│   │   ├── htmlParser.py
│   │   ├── sqlite.py
│   │   ├── utils.py            # 配置、Cookie、通知；LLM 可选
│   │   ├── Msg_DingTalk.py
│   │   └── Msg_Email.py
│   └── upload_component/
│       └── decode_zip.py
└── tests/
```

运行时产生的 `config.toml`、Cookie、SQLite 数据库、日志、失败响应和组件载荷均属于本地状态，不应提交到 Git。

## 环境要求

- Python `3.12+`
- Poetry `2.x`
- 可访问目标 ATS / RPA 平台的网络环境
- 如启用钉钉或邮件通知，需要对应服务的有效凭据
- LLM 仅在 `[llm].enabled = true` 时需要 Zhipu API Key

## 快速开始

### 1. 安装依赖

```bash
poetry install
```

### 2. 创建本地配置

```bash
copy config.example.toml config.toml  # Windows PowerShell/cmd
# cp config.example.toml config.toml   # Linux/macOS
```

然后至少填写：

| 配置段 | 关键字段 | 用途 |
| --- | --- | --- |
| 顶层 | `base_url` | 平台根地址，不要带末尾 `/` |
| `[user]` | `username`、`password`、`userID` | 登录凭据与待处理用户 ID 列表 |
| `[component]` | `tag_id`、`default_maintainer_id`、`default_version`、`approve_status` | 创建/批准默认值（生产：`5` / `30` / `3.0.0` / `31`） |
| `[component.default_info]` | schema 键 | 覆盖 `info` 默认值（不要改键名） |
| `[llm]` | `enabled`、`token` | 默认 `enabled=false`；主路径不调用 |
| `[smtp]` | `server`、`port`、`sender`、`pwd` | 邮件通知 |
| `[DingTalk]` | `access_token`、`secret` | 审批成功通知 |
| `[send_group]` | `access_token`、`secret` | 模板组件更新群通知 |

`config.toml` 已加入 `.gitignore`。不要提交真实密码、API Key、Cookie 或数据库。

### 3. 启动服务

```bash
poetry run python -m src.comticket.main
```

后台运行：`./scripts/run.sh`（Windows 用 `scripts/run.bat`）。Cookie 保存在 `data/session_cookies.pkl`。

## 二次开发指南

### 替换目标平台

1. 设置 `base_url`、用户和 `[component]`。
2. 列表解析在 `parse_pending_tickets`：按行内状态文本和 `/comticket/{id}/` 链接取 id，不要依赖列下标。
3. 创建/批准字段在 `create_component_from_ticket` / `approve_ticket`。
4. 为 HTML / JSON 变化补充 `tests/test_ticket_flow.py` fixture。

### 替换通知渠道

`send_DingTalk`、`send_Group_DingTalk` 和 `send_Email` 集中在 `utils.py`。`notify_approval_success` 是审批成功钩子。

### 可选 LLM

`utils.llm(remark, base_info)` 仍可用，但 **创建/批准主路径不会调用它**。`[llm].enabled = false` 时不会初始化 `zai` 客户端。

### 调整调度

`main.py` 常驻循环；组件监控在 `check_component_update.py` 的时间窗口内执行。生产环境可拆到 cron / systemd / 任务队列。

## 验证与测试

```bash
poetry check
poetry run pytest
python -m compileall -q src tests
```

默认测试不访问目标平台，也不发钉钉/邮件。联调请用测试账号。

## 常见问题

### 登录失败或反复要求登录

检查 `base_url`、账号是否能打开 `/robot/admin/app/comticket/`，删除 `data/session_cookies.pkl` 后重跑，并确认系统时间准确。

### 创建组件报 schema 错误

`info` 必须包含上一节列出的 9 个中文键，且不能提交空 `info`。不要再传 `com_group` 或 `rjf§*`。

### 详情 API 404 或 HTML 而不是 JSON

确认路径是 `/robot/com/admin/app/comticket/{wid}/detail/`，并且带了 `X-Requested-With: XMLHttpRequest`。

### 批准后状态不是「已批准」

查看 `data/response/` 下的失败 HTML。`form_status=31` 为批准，`32` 为驳回。

## 版本与贡献

版本号位于 `pyproject.toml`（当前 `0.3.0`）。提交前请运行测试，并确保没有把本地配置和运行态文件加入 Git。

仓库公开不等于自动授予二次分发权限；当前项目尚未声明开源许可证。
