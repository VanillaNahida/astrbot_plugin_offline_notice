import asyncio
import json
import re
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from smtplib import SMTP, SMTP_SSL

from aiohttp import web

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.star.star_tools import StarTools


@register("astrbot_plugin_offline_notice", "香草味的纳西妲喵（VanillaNahida）", "账号离线邮件通知插件", "1.0.0",
          "https://github.com/VanillaNahida/astrbot_plugin_offline_notice")
class OfflineNoticePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        self._heartbeat_task = None
        self._was_online = {}
        self._login_info_cache = {}
        self._offline_notices = {}
        self._api_fail_count = {}
        self._webhook_runner = None
        # Initialize data file path for offline notice persistence
        data_dir = StarTools.get_data_dir("astrbot_plugin_offline_notice")
        data_dir.mkdir(parents=True, exist_ok=True)
        self._data_file = data_dir / "uin_nickname.json"

    async def initialize(self):
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("离线通知心跳检测已启动")
        try:
            await self._start_webhook_server()
        except Exception as e:
            logger.error(f"Webhook 服务器启动失败: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_event(self, event: AstrMessageEvent):
        """用来捕捉 bot_offline 的通知事件（目前没用）"""
        raw = event.message_obj.raw_message
        if not isinstance(raw, dict):
            return
        if raw.get("post_type") != "notice":
            return
        if raw.get("notice_type") != "bot_offline":
            return

        platform_name = event.get_platform_name()
        self_id = raw.get("self_id", "")
        tag = raw.get("tag", "")
        message = raw.get("message", "")
        notice_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if platform_name not in self._offline_notices:
            self._offline_notices[platform_name] = []

        self._offline_notices[platform_name].append({
            "time": notice_time,
            "tag": tag,
            "message": message,
            "self_id": str(self_id),
        })
        logger.info(f"捕获 bot_offline 通知 [{platform_name}] [{tag}]: {message}")

    async def _heartbeat_loop(self):
        while True:
            try:
                interval = self._get_config_int("heartbeat_interval", 180)
                await asyncio.sleep(interval)
                await self._check_status()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"心跳检测异常: {e}")

    async def _check_status(self):
        try:
            platforms = self.context.platform_manager.get_insts()
        except Exception as e:
            logger.error(f"获取平台实例失败: {e}")
            return

        for platform in platforms:
            platform_name = platform.__class__.__name__

            if platform_name != "AiocqhttpAdapter":
                continue

            try:
                client = platform.get_client()
            except Exception as e:
                logger.warning(f"获取平台客户端失败 ({platform_name}): {e}")
                continue

            if not hasattr(client, 'api') or client.api is None:
                logger.debug(f"跳过不支持 Onebot11 API 的平台: {platform_name}")
                continue

            try:
                status = await client.api.call_action("get_status")
            except Exception as e:
                self._api_fail_count[platform_name] = self._api_fail_count.get(platform_name, 0) + 1
                fail_count = self._api_fail_count[platform_name]
                logger.info(f"心跳检测 [{platform_name}] API 调用失败 ({fail_count}/3): {e}")
                if fail_count >= 3:
                    logger.warning(f"心跳检测 [{platform_name}] 连续 {fail_count} 次 API 调用失败，视为离线")
                    was_online = self._was_online.get(platform_name, True)
                    if was_online:
                        await self._handle_offline(platform_name)
                    self._was_online[platform_name] = False
                continue

            self._api_fail_count[platform_name] = 0

            logger.debug(f"心跳检测 [{platform_name}] 原始返回: {status}")
            online = status.get("online", False) if isinstance(status, dict) else False

            if not online:
                was_online = self._was_online.get(platform_name, True)
                logger.info(f"心跳检测 [{platform_name}] 状态: 离线")
                if was_online:
                    await self._handle_offline(platform_name)
                self._was_online[platform_name] = False
            else:
                await self._cache_login_info(platform_name, client)
                if self._was_online.get(platform_name) is False:
                    logger.info(f"心跳检测 [{platform_name}] 状态: 在线（已恢复）")
                    self._offline_notices.pop(platform_name, None)
                else:
                    logger.info(f"心跳检测 [{platform_name}] 状态: 在线")
                self._was_online[platform_name] = True

    async def _cache_login_info(self, platform_name, client):
        try:
            login_info = await client.api.call_action("get_login_info")
            logger.debug(f"缓存 login_info [{platform_name}] 原始返回: {login_info}")
            user_id = login_info.get("user_id", "未知") if isinstance(login_info, dict) else "未知"
            nickname = login_info.get("nickname", "未知") if isinstance(login_info, dict) else "未知"
            if user_id != "未知" or nickname != "未知":
                self._login_info_cache[platform_name] = {
                    "user_id": user_id,
                    "nickname": nickname,
                }
                logger.info(f"已缓存账号信息 [{platform_name}]: {nickname}({user_id})")
        except Exception as e:
            logger.warning(f"获取 login_info 失败 ({platform_name}): {e}")

    async def _handle_offline(self, platform_name):
        cached = self._login_info_cache.get(platform_name, {})
        user_id = cached.get("user_id", "未知")
        nickname = cached.get("nickname", "未知")

        if user_id == "未知" and nickname == "未知":
            try:
                platforms = self.context.platform_manager.get_insts()
                for p in platforms:
                    if p.__class__.__name__ == platform_name:
                        client = p.get_client()
                        if hasattr(client, 'api') and client.api is not None:
                            await self._cache_login_info(platform_name, client)
                            cached = self._login_info_cache.get(platform_name, {})
                            user_id = cached.get("user_id", "未知")
                            nickname = cached.get("nickname", "未知")
                        break
            except Exception as e:
                logger.error(f"兜底获取 login_info 失败 ({platform_name}): {e}")

        offline_reason = self._build_offline_reason(platform_name)

        logger.warning(f"检测到账号离线: {nickname}({user_id}) 平台: {platform_name}")
        await self._send_email(user_id, nickname, platform_name, offline_reason=offline_reason)

    def _build_offline_reason(self, platform_name):
        notices = self._offline_notices.get(platform_name, [])
        if not notices:
            return ""

        lines = []
        for notice in notices:
            lines.append(
                f"<tr>"
                f"<td style=\"padding:8px 10px;border:1px solid #e9ecef;white-space:nowrap;color:#888;\">{notice['time']}</td>"
                f"<td style=\"padding:8px 10px;border:1px solid #e9ecef;font-weight:bold;\">{notice['tag']}</td>"
                f"<td style=\"padding:8px 10px;border:1px solid #e9ecef;\">{notice['message']}</td>"
                f"</tr>"
            )

        return (
            "<div style=\"margin-top:15px;\">\n"
            "  <h3 style=\"font-size:16px;color:#e74c3c;margin-bottom:8px;\">📋 离线通知详情</h3>\n"
            "  <table style=\"width:100%;border-collapse:collapse;font-size:13px;\">\n"
            "    <tr style=\"background:#f8f9fa;\">"
            "<th style=\"padding:8px 10px;border:1px solid #e9ecef;text-align:left;\">时间</th>"
            "<th style=\"padding:8px 10px;border:1px solid #e9ecef;text-align:left;\">类型</th>"
            "<th style=\"padding:8px 10px;border:1px solid #e9ecef;text-align:left;\">详情</th>"
            "</tr>\n"
            + "\n".join(lines) +
            "\n  </table>\n</div>"
        )

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("发送测试邮件")
    async def send_test_email(self, event: AstrMessageEvent, email: str = ""):
        """发送测试邮件到指定邮箱地址，用于验证邮件配置是否正确。用法：/发送测试邮件 test@example.com"""
        email_config = self.config.get("email_config", {})
        sender = email_config.get("sender", "")
        username = email_config.get("username", sender)
        password = email_config.get("password", "")
        display_name = email_config.get("display_name", "AstrBot 离线通知")
        smtp_server = email_config.get("smtp_server", "")
        smtp_port = self._get_int(email_config.get("smtp_port", 465))
        encryption = email_config.get("encryption", "SSL")

        if not all([sender, password, smtp_server]):
            yield event.plain_result("❌ 邮件配置不完整，请先在插件配置中填写发信地址、密码和 SMTP 服务器地址。")
            return

        if not email:
            message_str = event.message_str
            parts = message_str.strip().split(maxsplit=1)
            email = parts[1] if len(parts) > 1 else ""

        if not email or "@" not in email:
            yield event.plain_result("❌ 请提供有效的邮箱地址，用法：/发送测试邮件 test@example.com")
            return

        body = f"这是一封 {display_name} 的测试邮件，当你收到了这个邮件，证明插件和发件配置一切正常。"
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(f"【{display_name}】测试邮件", "utf-8")
        msg["From"] = formataddr((display_name, sender))
        msg["To"] = email

        try:
            if encryption == "SSL":
                server = SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                server = SMTP(smtp_server, smtp_port, timeout=30)
                if encryption == "TLS":
                    server.starttls()

            server.login(username, password)
            server.sendmail(sender, [email], msg.as_string())
            server.quit()

            yield event.plain_result(f"✅ 测试邮件已发送至 {email}，请检查收件箱。")
        except Exception as e:
            yield event.plain_result(f"❌ 发送失败：{e}")

    async def _send_email(self, user_id, nickname, platform_name, recipients=None, offline_reason=""):
        email_config = self.config.get("email_config", {})

        if recipients is None:
            recipients = email_config.get("recipients", [])

        if not recipients:
            logger.warning("未配置收件人邮箱，跳过发送离线通知邮件")
            return

        template_config = self.config.get("email_template", {})

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        template_vars = {
            "user_id": str(user_id),
            "nickname": nickname,
            "timestamp": now,
            "platform": platform_name,
            "offline_reason": offline_reason,
        }
        logger.debug(f"邮件模板变量: {template_vars}")

        subject_template = template_config.get("subject", "")
        body_template = template_config.get("body", "")
        subject = self._render_template(subject_template, template_vars)
        body = self._render_template(body_template, template_vars)

        sender = email_config.get("sender", "")
        username = email_config.get("username", sender)
        password = email_config.get("password", "")
        display_name = email_config.get("display_name", "AstrBot 离线通知")
        smtp_server = email_config.get("smtp_server", "")
        smtp_port = self._get_int(email_config.get("smtp_port", 465))
        encryption = email_config.get("encryption", "SSL")

        if not all([sender, password, smtp_server]):
            logger.error("邮件配置不完整，请检查发信地址、密码和 SMTP 服务器地址")
            return

        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((display_name, sender))
        msg["To"] = ", ".join(recipients)

        try:
            if encryption == "SSL":
                server = SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                server = SMTP(smtp_server, smtp_port, timeout=30)
                if encryption == "TLS":
                    server.starttls()

            server.login(username, password)
            server.sendmail(sender, recipients, msg.as_string())
            server.quit()

            logger.info(f"离线通知邮件已发送至: {', '.join(recipients)}")
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")

    def _render_template(self, template: str, template_vars: dict) -> str:
        result = template
        for key, value in template_vars.items():
            result = result.replace("{{" + key + "}}", value)
        return result

    def _get_config_int(self, key: str, default: int) -> int:
        val = self.config.get(key, default)
        return self._get_int(val)

    @staticmethod
    def _get_int(val) -> int:
        if isinstance(val, int):
            return val
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    async def _start_webhook_server(self):
        webhook_config = self.config.get("webhook", {})
        host = webhook_config.get("host", "127.0.0.1")
        port = self._get_int(webhook_config.get("port", 3051))

        app = web.Application()
        app.router.add_post("/notice/send", self._handle_webhook_notice)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        self._webhook_runner = runner

        url = f"http://{host}:{port}/notice/send"
        token = webhook_config.get("access_token", "")
        if token:
            url += f"?token={token}"
        try:
            self.config["webhook"]["webhook_url"] = url
        except Exception:
            pass

        body_template = (
            '{\n'
            '  "title": "账号状态通知：{event}",\n'
            '  "desp": "您的账号状态发生了改变。\\n\\n'
            '**昵称**：{nickname}\\n'
            '**QQ号**：{uin}\\n'
            '**当前状态**：{event}\\n'
            '**时间**：{time}"\n'
            '}'
        )
        try:
            self.config["webhook"]["webhook_body_template"] = body_template
        except Exception:
            pass

        logger.info(f"Webhook 服务器已启动: {url}")

    async def _handle_webhook_notice(self, request: web.Request):
        webhook_config = self.config.get("webhook", {})
        configured_token = webhook_config.get("access_token", "")

        if configured_token:
            token = request.query.get("token", "")
            if token != configured_token:
                logger.warning(f"Webhook 通知 token 验证失败，来源: {request.remote}")
                return web.json_response({"code": 403, "message": "invalid token"}, status=403)

        try:
            body = await request.json()
        except Exception as e:
            logger.warning(f"Webhook 通知 JSON 解析失败: {e}")
            return web.json_response({"code": 400, "message": "invalid json"}, status=400)

        title = body.get("title", "")
        desp = body.get("desp", "")

        if not title:
            logger.warning("Webhook 通知缺少 title 字段")
            return web.json_response({"code": 400, "message": "missing title"}, status=400)

        parsed = self._parse_snowluma_body(title, desp)
        desp_html = self._desp_to_html(desp)

        uin = parsed["uin"]
        nickname = parsed["nickname"]

        if uin != "未知" and nickname == uin:
            cached_nickname = self._lookup_nickname(uin)
            if cached_nickname:
                parsed["nickname"] = cached_nickname
                logger.info(f"从缓存恢复昵称: {uin} -> {cached_nickname}")

        if uin != "未知" and nickname != "未知" and nickname != uin:
            self._update_uin_nickname(uin, nickname)

        logger.info(
            f"收到 SnowLuma 通知: event={parsed['event']}, "
            f"uin={parsed['uin']}, nickname={parsed['nickname']}"
        )
        await self._send_snowluma_email(title=title, desp=desp, desp_html=desp_html, **parsed)

        return web.json_response({"code": 0, "message": "ok"})

    def _parse_snowluma_body(self, title: str, desp: str) -> dict:
        result = {
            "event": "unknown",
            "uin": "未知",
            "nickname": "未知",
            "time": "",
        }

        event_match = re.search(r"账号状态通知[：:]\s*(\S+)", title)
        if event_match:
            raw_event = event_match.group(1)
            event_map = {"offline": "离线", "online": "上线"}
            result["event"] = event_map.get(raw_event, raw_event)

        nickname_match = re.search(r"(?:\*\*)?昵称(?:\*\*)?[：:]\s*(.+)", desp)
        if nickname_match:
            result["nickname"] = nickname_match.group(1).strip()

        uin_match = re.search(r"(?:\*\*)?QQ号(?:\*\*)?[：:]\s*(\d+)", desp)
        if uin_match:
            result["uin"] = uin_match.group(1)

        time_match = re.search(r"(?:\*\*)?时间(?:\*\*)?[：:]\s*(.+)", desp)
        if time_match:
            result["time"] = self._format_time_gmt8(time_match.group(1).strip())

        return result

    @staticmethod
    def _format_time_gmt8(time_str: str) -> str:
        from datetime import timezone, timedelta
        tz_gmt8 = timezone(timedelta(hours=8))
        iso_patterns = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        for fmt in iso_patterns:
            try:
                dt = datetime.strptime(time_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(tz_gmt8).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return time_str

    @staticmethod
    def _desp_to_html(desp: str) -> str:
        result = desp
        result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
        parts = result.split("\n\n")
        paragraphs = []
        for part in parts:
            lines = part.split("\n")
            paragraphs.append("<br>".join(lines))
        result = "</p><p>".join(paragraphs)
        result = f"<p>{result}</p>"
        return result

    def _load_uin_nickname_map(self) -> dict:
        try:
            if self._data_file.exists():
                with open(self._data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载 uin_nickname.json 失败: {e}")
        return {}

    def _save_uin_nickname_map(self, data: dict):
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存 uin_nickname.json 失败: {e}")

    def _update_uin_nickname(self, uin: str, nickname: str):
        data = self._load_uin_nickname_map()
        data[uin] = {
            "nickname": nickname,
            "last_access": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if len(data) > 10:
            sorted_items = sorted(
                data.items(), key=lambda x: x[1].get("last_access", "")
            )
            data = dict(sorted_items[-10:])
        self._save_uin_nickname_map(data)

    def _lookup_nickname(self, uin: str) -> str:
        data = self._load_uin_nickname_map()
        if uin in data:
            data[uin]["last_access"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_uin_nickname_map(data)
            return data[uin]["nickname"]
        return ""

    async def _send_snowluma_email(
        self, title: str, desp: str, desp_html: str,
        event: str, uin: str, nickname: str, time: str,
    ):
        email_config = self.config.get("email_config", {})
        recipients = email_config.get("recipients", [])

        if not recipients:
            logger.warning("未配置收件人邮箱，跳过发送 SnowLuma 通知邮件")
            return

        template_config = self.config.get("snowluma_email_template", {})
        template_vars = {
            "title": title,
            "desp": desp,
            "desp_html": desp_html,
            "uin": uin,
            "nickname": nickname,
            "event": event,
            "time": time,
        }

        subject_template = template_config.get("subject", "")
        body_template = template_config.get("body", "")
        subject = self._render_template(subject_template, template_vars)
        body = self._render_template(body_template, template_vars)

        sender = email_config.get("sender", "")
        username = email_config.get("username", sender)
        password = email_config.get("password", "")
        display_name = email_config.get("display_name", "AstrBot 离线通知")
        smtp_server = email_config.get("smtp_server", "")
        smtp_port = self._get_int(email_config.get("smtp_port", 465))
        encryption = email_config.get("encryption", "SSL")

        if not all([sender, password, smtp_server]):
            logger.error("邮件配置不完整，请检查发信地址、密码和 SMTP 服务器地址")
            return

        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((display_name, sender))
        msg["To"] = ", ".join(recipients)

        try:
            if encryption == "SSL":
                server = SMTP_SSL(smtp_server, smtp_port, timeout=30)
            else:
                server = SMTP(smtp_server, smtp_port, timeout=30)
                if encryption == "TLS":
                    server.starttls()

            server.login(username, password)
            server.sendmail(sender, recipients, msg.as_string())
            server.quit()

            logger.info(f"SnowLuma 通知邮件已发送至: {', '.join(recipients)}")
        except Exception as e:
            logger.error(f"发送 SnowLuma 通知邮件失败: {e}")

    async def terminate(self):
        if self._webhook_runner:
            await self._webhook_runner.cleanup()
            logger.info("Webhook 服务器已停止")
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.info("离线通知插件已停止")
