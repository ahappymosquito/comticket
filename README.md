# comticket

面向内部 RPA 组件平台的自动化处理服务：定时检查组件版本更新，读取待审批工单，按备注调用 LLM 补全组件信息，并通过 HTTP、钉钉和 SMTP 完成后续处理与通知。

> 当前代码针对特定的 Django Admin 接口和内部字段设计。公开仓库用于二次开发参考；接入自己的平台前，需要替换接口地址、表单字段、状态值和通知策略。

## 功能概览

- 使用 `requests.Session` 登录并复用本地 Cookie。
- 轮询待审批的 component ticket，解析 HTML 表格并创建/更新组件版本。
- 使用 Zhipu AI GLM 从备注中抽取结构化组件信息。
- 通过钉钉机器人和 SMTP 发送成功/失败通知。
- 将组件版本监控结果保存到 SQLite，并在检测到更新时通知群组。
- 保存失败响应 HTML，方便定位上游页面或字段变化。

## 项目结构

```text
.
├── config.example.toml       # 脱敏配置模板，复制为 config.toml 后填写
├── pyproject.toml             # Poetry 项目定义与依赖
├── scripts/
│   ├── run.bat                # Windows 启动脚本
│   └── run.sh                 # Linux/macOS 启动脚本
├── src/
│   ├── comticket/
│   │   ├── main.py            # 主循环：登录、审批处理、定时监控
│   │   ├── get_session.py     # 登录与 Cookie 持久化
│   │   ├── creat_comticket.py # 工单解析、组件创建与审批提交
│   │   ├── check_component_update.py
│   │   │                         # 组件版本监控
│   │   ├── htmlParser.py      # HTML/XPath 辅助封装
│   │   ├── sqlite.py          # SQLite 存储
│   │   ├── utils.py            # 配置、Cookie、通知、LLM 和版本工具
│   │   ├── Msg_DingTalk.py    # 钉钉机器人客户端
│   │   └── Msg_Email.py       # SMTP 客户端
│   └── upload_component/
│       └── decode_zip.py      # 将本地 Base64 载荷还原为 ZIP
└── tests/                     # 无外部副作用的测试与回归用例
```

运行时产生的 `config.toml`、Cookie、SQLite 数据库、日志、失败响应和组件载荷均属于本地状态，不应提交到 Git。

## 环境要求

- Python `3.12+`
- Poetry `2.x`
- 可访问目标 RPA 平台的网络环境
- 如启用 LLM、钉钉或邮件通知，需要对应服务的有效凭据

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

然后至少填写以下配置：

| 配置段 | 关键字段 | 用途 |
| --- | --- | --- |
| 顶层 | `base_url` | RPA 平台根地址，不要带末尾 `/` |
| `[user]` | `username`、`password`、`userID` | 登录凭据与待处理用户 ID 列表 |
| `[llm]` | `token` | Zhipu AI API Key；不使用 LLM 时需改造 `utils.llm` |
| `[smtp]` | `server`、`port`、`sender`、`pwd` | 邮件通知 |
| `[DingTalk]` | `access_token`、`secret` | 单聊/指定群通知 |
| `[send_group]` | `access_token`、`secret` | 群组更新通知 |

`config.toml` 已加入 `.gitignore`。不要把真实密码、API Key、Cookie 或导出的数据库上传到公开仓库；如果凭据曾经进入过 Git 历史，应立即吊销并轮换。

### 3. 启动服务

在仓库根目录执行：

```bash
poetry run python -m src.comticket.main
```

后台运行可使用：

```bash
./scripts/run.sh
```

Windows 直接运行 `scripts/run.bat`。服务会持续轮询，登录成功后将 Cookie 保存到 `data/session_cookies.pkl`。首次运行或 Cookie 失效时会重新登录。

## 二次开发指南

### 替换目标平台

1. 在 `config.toml` 中设置自己的 `base_url`、用户信息和通知配置。
2. 根据目标平台页面结构调整 `get_user_comticket`、`get_component_id` 和 `check_component` 中的 XPath/CSS 选择器。
3. 根据目标平台的状态值、表单字段和重定向规则修改 `creat_components`、`creat_comtickets`。
4. 为页面字段变化增加 HTML fixture 测试，避免只依赖线上请求验证。

### 替换通知渠道

`send_DingTalk`、`send_Group_DingTalk` 和 `send_Email` 都集中在 `utils.py`。可以替换为企业微信、Slack、Webhook 或项目内的消息总线，同时保持业务模块只调用通知函数。

### 替换 LLM

`utils.llm(remark, base_info)` 是当前的抽取边界。实现新的模型适配器时，保持返回值为 JSON 字符串，并确保字段集合与平台表单一致；建议为超时、空响应和非法 JSON 增加降级策略。

### 调整调度

`main.py` 当前使用常驻循环，组件更新监控在 `check_component_update.py` 中按时间窗口执行。生产环境可以将这两个入口拆分为 cron、systemd timer、Windows Task Scheduler 或任务队列。

## 验证与测试

```bash
poetry check
poetry run pytest
python -m compileall -q src tests
```

线上接口依赖登录态和内部网络，默认测试不会主动访问目标平台，也不会发送钉钉消息或邮件。联调前请使用测试账号、测试机器人和隔离邮箱。

## 常见问题

### 登录失败或反复要求登录

检查 `base_url` 是否正确、账号是否有权限访问 `/robot/admin/app/comticket/`，删除本地 `data/session_cookies.pkl` 后重新运行，并确认系统时间准确。

### 组件页面返回 200 但解析不到数据

这通常表示上游 HTML 字段或 XPath 已变化。先查看 `data/response/` 下的失败响应，再更新解析器和对应测试 fixture。

### LLM 返回无法解析的 JSON

检查 API Key、模型名称和返回内容；建议在 `utils.llm` 外层增加 JSON Schema 校验与默认值回退。

## 版本与贡献

版本号位于 `pyproject.toml`，采用 `MAJOR.MINOR.PATCH`。提交改动前请同步锁文件、运行测试，并确保没有把本地配置和运行态文件加入 Git。

仓库公开不等于自动授予二次分发权限；当前项目尚未声明开源许可证。若要正式对外二次发布，请先补充合适的 `LICENSE` 并确认原内部接口、字段和依赖的授权范围。
