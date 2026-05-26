# QQ账号离线通知

一个专门为 QQ 个人号平台打造的掉线检测插件，定时检测 QQ 账号的在线状态，离线时第一时间通过邮件通知用户。仅支持 aiocqhttp（OneBot v11）。


<p align="center">
  <img src="logo.png" alt="离线通知 Logo">
</p>

<div align="center">

  [![GitHub license](https://img.shields.io/github/license/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/blob/main/LICENSE)
  [![GitHub stars](https://img.shields.io/github/stars/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/stargazers)
  [![GitHub forks](https://img.shields.io/github/forks/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/network)
  [![GitHub issues](https://img.shields.io/github/issues/VanillaNahida/astrbot_plugin_offline_notice?style=flat-square)](https://github.com/VanillaNahida/astrbot_plugin_offline_notice/issues)
  [![python3](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square)](https://www.python.org/)
  [![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-brightgreen.svg?style=flat-square)]()

</div>

# 功能特性

- **定时心跳检测**：通过 OneBot v11 的 `get_status` API 定时检测账号在线状态
- **邮件离线通知**：账号离线时自动发送 HTML 富文本邮件到指定邮箱
- **离线原因追踪**：自动捕获 OneBot v11 下发的 `bot_offline` 通知事件，汇总下线原因并包含在邮件中
- **自定义邮件模板**：支持魔法变量，可自定义邮件主题和正文（HTML 格式）
- **多种加密方式**：SMTP 发送支持 SSL / TLS / 不加密
- **测试邮件命令**：配置完成后可通过管理员命令发送测试邮件验证配置

# 原理

本插件通过 OneBot v11 API 定时调用 `get_status` 接口，检查返回数据中的 `online` 字段。当 `online` 为 `false` 时，判定账号已离线，随即调用 `get_login_info` 获取账号信息，连同捕获到的 `bot_offline` 下线原因一并发送邮件通知。

```
get_status → online: false
    ↓
get_login_info → {user_id, nickname}
    ↓
bot_offline 通知缓存 → {时间, 类型, 详情}
    ↓
渲染邮件模板 → SMTP 发送
```

# 使用方法

> [!WARNING]
>
> 请确保您的 AstrBot 版本号 ≥ `v4.16`，且已配置好 aiocqhttp 协议端。

> [!TIP]
>
> 由于框架限制，暂时无法捕捉到 `bot_offline` 通知事件，只能捕捉是否在线的事件，后续会尝试优化这个问题。

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
