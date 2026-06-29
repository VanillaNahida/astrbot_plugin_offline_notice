# QQ账号离线通知

![:name](https://count.getloli.com/@astrbot_plugin_offline_notice?name=astrbot_plugin_offline_notice&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

一个专门为 QQ 个人号平台打造的掉线检测插件，定时检测 QQ 账号的在线状态，离线时第一时间通过邮件通知用户，并且支持SnowLuma Webhook 通知。仅支持 aiocqhttp（OneBot v11）。


<p align="center">
  <img src="https://img.dkdun.cn/v1/2026/17/08f0226a817892df.png" alt="圣娅怪叫.png（太臭了哼哼啊啊啊啊啊啊啊啊啊啊啊！）">
</p>

<div align="center">

  [![GitHub license](https://img.shields.io/github/license/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/blob/main/LICENSE)
  [![GitHub stars](https://img.shields.io/github/stars/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/network)
  [![GitHub issues](https://img.shields.io/github/issues/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/issues)
  [![python3](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://www.python.org/)
  [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-brightgreen.svg?style=flat-square)]()
  [![Author](https://img.shields.io/badge/%E4%BD%9C%E8%80%85-VanillaNahida-green)](https://github.com/VanillaNahida )



</div>

# 功能特性

- **定时心跳检测**：通过 OneBot v11 的 `get_status` API 定时检测账号在线状态
- **邮件离线通知**：账号离线时自动发送 HTML 富文本邮件到指定邮箱
- **离线原因追踪**：自动捕获 OneBot v11 下发的 `bot_offline` 通知事件，汇总下线原因并包含在邮件中
- **SnowLuma Webhook 通知**：接收 SnowLuma 推送的账号上下线状态通知，自动转为邮件发送
- **自定义邮件模板**：支持魔法变量，可自定义邮件主题和正文（HTML 格式），心跳检测和 SnowLuma 各有独立模板
- **多种加密方式**：SMTP 发送支持 SSL / TLS / 不加密
- **测试邮件命令**：配置完成后可通过管理员命令发送测试邮件验证配置

# 原理

本插件通过 OneBot v11 API 定时调用 `get_status` 接口，检查返回数据中的 `online` 字段。当 `online` 为 `false` 时，判定账号已离线，随即调用 `get_login_info` 获取账号信息，连同捕获到的 `bot_offline` 下线原因一并发送邮件通知。

同时插件会启动一个 HTTP Webhook 服务器，接收 SnowLuma 推送的账号上下线状态通知，解析后通过独立模板发送邮件通知。

```
心跳检测流程:
get_status → online: false
    ↓
get_login_info → {user_id, nickname}
    ↓
bot_offline 通知缓存 → {时间, 类型, 详情}
    ↓
渲染邮件模板 → SMTP 发送

SnowLuma Webhook 流程:
SnowLuma POST /notice/send?token=xxx
    ↓
解析 JSON → {title, desp}
    ↓
提取 event, uin, nickname, time 并格式化为 GMT+8
    ↓
QQ号-昵称缓存匹配 / 更新
    ↓
渲染 SnowLuma 邮件模板 → SMTP 发送
```

# 使用方法

> [!TIP]
>
> 支持 SnowLuma Webhook 通知。配置插件后，Webhook URL 和 Body 模板会自动生成在配置页面中，将其填入 SnowLuma 的 WebUI 即可接收账号状态变更通知。

## 安装

1. 在 AstrBot WebUI 插件市场搜索 `astrbot_plugin_offline_notice` 或 `QQ账号离线通知`
2. 点击安装插件
3. 或者通过仓库地址安装：复制 `https://github.com/VanillaNahida/astrbot_plugin_offline_notice` 粘贴到 WebUI 安装

## 配置

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `heartbeat_interval` | int | 180 | 心跳检测间隔（秒） |

### 邮件发送配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `username` | string | SMTP 登录用户名，通常与发信地址相同 |
| `sender` | string | 邮件显示的发件人地址 |
| `password` | string | SMTP 登录密码或授权码（QQ 邮箱需使用授权码） |
| `display_name` | string | 收件人看到的发件人名称 |
| `smtp_server` | string | SMTP 服务器地址，例如 `smtp.qq.com` |
| `smtp_port` | int | SMTP 端口，SSL 通常为 465，TLS 通常为 587 |
| `encryption` | string | 加密类型，可选 `SSL` / `TLS` / `不启用` |
| `recipients` | list | 通知收件人邮箱列表 |

### 邮件模板

支持以下魔法变量，可在主题和正文中使用：

| 变量 | 说明 |
|------|------|
| `{{user_id}}` | QQ 账号 ID |
| `{{nickname}}` | QQ 昵称 |
| `{{timestamp}}` | 检测时间 |
| `{{platform}}` | 平台名称 |
| `{{offline_reason}}` | 离线原因详情（bot_offline 通知汇总） |

正文支持 HTML 格式，默认提供一套美观的富文本邮件模板。

### SnowLuma Webhook 配置

插件启动后会在配置中自动生成 Webhook 地址和 Body 模板，无需手动填写。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `host` | string | 127.0.0.1 | Webhook 服务器监听地址 |
| `port` | int | 3051 | Webhook 服务器监听端口 |
| `access_token` | string | （空） | 访问令牌，用于验证请求（可留空） |
| `webhook_url` | string | 自动生成 | 完整的 Webhook 地址，填入 SnowLuma |
| `webhook_body_template` | json | 自动生成 | Body JSON 模板，填入 SnowLuma （这里使用的是SnowLuma的默认值）|

Webhook 地址格式：`http://{host}:{port}/notice/send?token={access_token}`

### SnowLuma 通知邮件模板

独立于心跳检测的邮件模板，支持以下模板变量：

| 变量 | 说明 |
|------|------|
| `{{title}}` | SnowLuma 推送的完整标题 |
| `{{uin}}` | QQ 号 |
| `{{nickname}}` | QQ 昵称 |
| `{{event}}` | 事件类型（上线/离线） |
| `{{time}}` | 时间（格式：YYYY-MM-DD HH:MM:SS） |
| `{{desp}}` | 原始描述文本 |
| `{{desp_html}}` | 自动转换为 HTML 后的描述 |

QQ号-昵称映射会存储在插件数据目录的 `uin_nickname.json` 中，上限 10 条，超过时自动移除最久未访的记录。

## 验证配置

配置完成后，在 AstrBot 中使用管理员命令发送测试邮件：

```
/发送测试邮件 test@example.com
```

收到测试邮件即代表一切配置正确。

# 命令总览

| 命令 | 示例用法 | 权限要求 | 说明 |
|------|------|----------|------|
| `/发送测试邮件` | `/发送测试邮件 test@example.com` | Bot 管理员 | 发送测试邮件到指定地址，验证邮件配置是否正确 |

# 常见邮箱 SMTP 配置

| 邮箱 | SMTP 服务器 | 端口 | 加密 |
|------|------------|------|------|
| QQ 邮箱 | `smtp.qq.com` | 465 | SSL |
| 163 邮箱 | `smtp.163.com` | 465 | SSL |
| Gmail | `smtp.gmail.com` | 587 | TLS |
| Outlook | `smtp-mail.outlook.com` | 587 | TLS |

# Bug 反馈

如果在使用过程中遇到任何问题，请通过以下方式反馈：

- [GitHub Issues](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/issues)
- QQ群：
  - 三群：195260107（推荐）
  - 四群：1074471035（闲聊群）

# QQ 群

- 一群：621457510
- 二群：1031065631
- 三群：195260107（推荐）
- 四群：1074471035

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=VanillaNahida/astrbot_plugin_offline_notice&type=Date)](https://star-history.com/#VanillaNahida/astrbot_plugin_offline_notice&Date)
