#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ名片自动点赞机器人
基于 OneBot V11 标准和 NapCatQQ 实现

新增：
- 管理页面（按钮触发点赞一次 + 开关控制是否执行定时点赞）
"""

import html
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

import requests
import schedule


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _safe_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"{name} 必须是整数，当前: {raw!r}") from e


class QQAutoLikeBot:
    def __init__(self, api_url: str, access_token: Optional[str] = None):
        self.api_url = api_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

    def _post(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.api_url}/{action.lstrip('/')}"
        response = requests.post(url, headers=self.headers, json=params or {}, timeout=10)
        return response.json()

    def get_login_info(self) -> Dict[str, Any]:
        return self._post("get_login_info")

    def get_status(self) -> Dict[str, Any]:
        return self._post("get_status")

    def send_like(self, user_id: str, times: int = 10) -> bool:
        try:
            like_times = max(1, min(int(times), 10))
        except Exception:
            like_times = 1

        try:
            result = self._post("send_like", {"user_id": user_id, "times": like_times})
            if result.get("status") == "ok" or result.get("retcode") == 0:
                print(f"✓ 成功给 {user_id} 点赞 {like_times} 次")
                return True
            print(f"✗ 给 {user_id} 点赞失败: {result}")
            return False
        except Exception as e:
            print(f"✗ 请求失败: {e}")
            return False

    def get_friend_list(self) -> List[Dict[str, Any]]:
        try:
            result = self._post("get_friend_list", {})
            if result.get("status") == "ok" or result.get("retcode") == 0:
                return result.get("data", []) or []
            print(f"✗ 获取好友列表失败: {result}")
            return []
        except Exception as e:
            print(f"✗ 请求失败: {e}")
            return []

    def auto_like_friends(self, friend_ids: List[str], times: int = 10, delay: int = 2) -> Dict[str, int]:
        print(f"\n{'=' * 50}")
        print(f"开始自动点赞任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 50}\n")

        success_count = 0
        fail_count = 0

        for idx, user_id in enumerate(friend_ids):
            if self.send_like(user_id, times):
                success_count += 1
            else:
                fail_count += 1

            if idx != len(friend_ids) - 1:
                time.sleep(delay)

        print(f"\n{'=' * 50}")
        print(f"点赞任务完成！成功: {success_count}, 失败: {fail_count}")
        print(f"{'=' * 50}\n")
        return {"success": success_count, "fail": fail_count}


@dataclass
class BotState:
    schedule_enabled: bool = True
    last_action: str = ""
    last_action_at: str = ""
    last_action_ok: Optional[bool] = None
    last_action_detail: str = ""


class StateStore:
    def __init__(self, path: Optional[str], initial: BotState):
        self._path = path
        self._lock = threading.Lock()
        self._state = initial
        if self._path:
            self._load()

    def _load(self) -> None:
        path = Path(self._path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, value in data.items():
                    if hasattr(self._state, key):
                        setattr(self._state, key, value)
        except FileNotFoundError:
            self._save_locked()
        except Exception as e:
            print(f"[admin] 状态文件读取失败: {e}")

    def _save_locked(self) -> None:
        if not self._path:
            return
        path = Path(self._path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(asdict(self._state), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[admin] 状态文件写入失败: {e}")

    def get(self) -> BotState:
        with self._lock:
            return BotState(**asdict(self._state))

    def update(self, **kwargs: Any) -> BotState:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._save_locked()
            return BotState(**asdict(self._state))


class LikeController:
    def __init__(self, bot: QQAutoLikeBot, targets: List[str], delay: int, store: StateStore):
        self.bot = bot
        self.targets = targets
        self.delay = delay
        self.store = store
        self._task_lock = threading.Lock()

    def like_users(self, user_ids: List[str], times: int, reason: str) -> Dict[str, Any]:
        if not user_ids:
            raise ValueError("TARGET_FRIENDS 为空，请先配置要点赞的 QQ 号")
        if times < 1:
            raise ValueError("times 必须 >= 1")
        if not self._task_lock.acquire(blocking=False):
            raise RuntimeError("当前有任务正在执行，请稍后再试")

        started_at = _now_str()
        try:
            summary = self.bot.auto_like_friends(user_ids, times, self.delay)
            ok = bool(summary.get("fail", 0) == 0)
            self.store.update(
                last_action=reason,
                last_action_at=started_at,
                last_action_ok=ok,
                last_action_detail=json.dumps(summary, ensure_ascii=False),
            )
            return summary
        except Exception as e:
            self.store.update(
                last_action=reason,
                last_action_at=started_at,
                last_action_ok=False,
                last_action_detail=str(e),
            )
            raise
        finally:
            self._task_lock.release()

    def like_all(self, times: int, reason: str) -> Dict[str, Any]:
        return self.like_users(self.targets, times, reason)


def _token_qs(token: str) -> str:
    if not token:
        return ""
    return f"?token={quote(token)}"


def _render_admin_page(
    state: BotState,
    config: Dict[str, Any],
    next_run: str,
    napcat_status: Optional[Dict[str, Any]],
    login_info: Optional[Dict[str, Any]],
    napcat_error: str,
    token: str,
) -> str:
    def esc(s: Any) -> str:
        return html.escape("" if s is None else str(s), quote=True)

    enabled_text = "开启" if state.schedule_enabled else "关闭"
    last_ok = state.last_action_ok
    last_ok_text = "" if last_ok is None else ("成功" if last_ok else "失败")
    last_ok_class = "" if last_ok is None else ("ok" if last_ok else "bad")

    online = None
    if napcat_status:
        online = napcat_status.get("data", {}).get("online")

    login_text = ""
    if login_info and isinstance(login_info.get("data"), dict):
        data = login_info["data"]
        login_text = f"{data.get('nickname')} ({data.get('user_id')})"

    action_suffix = _token_qs(token)

    targets = config.get("targets") or []
    targets_text = ", ".join(str(x) for x in targets)

    status_line = ""
    if napcat_error:
        status_line = f'<span class="pill bad">连接失败：{esc(napcat_error)}</span>'
    else:
        status_line = (
            f'<span class="pill">在线：{esc(online)}</span>'
            + (f'<span class="pill">已登录：{esc(login_text)}</span>' if login_text else "")
        )

    last_detail_block = ""
    if state.last_action_detail:
        last_detail_block = f"""
        <div class="hr"></div>
        <div class="muted">最近操作详情：</div>
        <div class="pre mono">{esc(state.last_action_detail)}</div>
        """

    last_action_line = ""
    if state.last_action_at:
        last_action_line = f'<span class="pill">最近操作：{esc(state.last_action)} @ {esc(state.last_action_at)}</span>'
        if last_ok is not None:
            last_action_line += f' <span class="pill {esc(last_ok_class)}">{esc(last_ok_text)}</span>'

    api_url = config.get("api_url", "")
    schedule_time = config.get("schedule_time", "")
    like_times = config.get("like_times", "")
    delay = config.get("delay", "")
    state_file = config.get("state_file", "")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QQ 自动点赞管理</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; background:#0b0f14; color:#e6edf3; margin:0; }}
    a {{ color:#7ee787; }}
    .container {{ max-width: 920px; margin: 0 auto; padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    @media (min-width: 900px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{ background:#111827; border:1px solid #243043; border-radius: 12px; padding: 16px; }}
    h1 {{ font-size: 20px; margin: 0 0 12px; }}
    h2 {{ font-size: 16px; margin: 0 0 8px; color: #c9d1d9; }}
    .row {{ display:flex; gap: 12px; flex-wrap: wrap; align-items:center; }}
    .pill {{ display:inline-block; padding: 4px 8px; border-radius:999px; background:#0f172a; border:1px solid #243043; font-size:12px; }}
    .ok {{ background:#2dba4e; border-color:#2dba4e; color:#041; }}
    .bad {{ background:#ff7b72; border-color:#ff7b72; color:#2d0b0b; }}
    .btn {{ cursor:pointer; border:1px solid #2dba4e; background:#2dba4e; color:#041; padding: 8px 12px; border-radius: 8px; font-weight: 600; }}
    .btn.secondary {{ background:transparent; color:#e6edf3; border-color:#243043; }}
    .btn.danger {{ background:#ff7b72; border-color:#ff7b72; color:#2d0b0b; }}
    input {{ background:#0b1220; color:#e6edf3; border:1px solid #243043; border-radius:8px; padding:8px 10px; }}
    code {{ background:#0b1220; padding:2px 6px; border-radius:6px; border:1px solid #243043; }}
    .muted {{ color:#9da7b3; font-size: 12px; }}
    .mono {{ font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace; }}
    .hr {{ height:1px; background:#243043; margin: 12px 0; }}
    .pre {{ white-space: pre-wrap; word-break: break-word; background:#0b1220; border:1px solid #243043; border-radius: 10px; padding: 10px; }}
  </style>
</head>
<body>
<div class="container">
  <h1>QQ 自动点赞管理</h1>
  <div class="grid">
    <div class="card">
      <h2>运行状态</h2>
      <div class="row">
        <span class="pill">定时点赞：{esc(enabled_text)}</span>
        {last_action_line}
      </div>
      <div class="muted" style="margin-top:8px;">下次定时执行：{esc(next_run or '（未设置）')}</div>
      {last_detail_block}
      <div class="hr"></div>
      <div class="row">
        <form method="post" action="/toggle_schedule{action_suffix}">
          <input type="hidden" name="enabled" value="1">
          <button class="btn secondary" type="submit">开启定时点赞</button>
        </form>
        <form method="post" action="/toggle_schedule{action_suffix}">
          <input type="hidden" name="enabled" value="0">
          <button class="btn danger" type="submit">关闭定时点赞</button>
        </form>
      </div>
      <div class="muted" style="margin-top:8px;">说明：开关只影响“定时任务”，手动按钮仍可随时点。</div>
    </div>

    <div class="card">
      <h2>手动点赞</h2>
      <div class="row">
        <form method="post" action="/like_once{action_suffix}">
          <button class="btn" type="submit">对所有目标点赞 1 次</button>
        </form>
      </div>
      <div class="hr"></div>
      <form method="post" action="/like_once{action_suffix}">
        <div class="row">
          <input name="user_id" placeholder="指定 QQ 号（可选）" class="mono" style="min-width: 220px;">
          <button class="btn secondary" type="submit">对指定 QQ 点赞 1 次</button>
        </div>
      </form>
      <div class="muted" style="margin-top:8px;">目标列表来自 <code>TARGET_FRIENDS</code> 环境变量。</div>
    </div>

    <div class="card">
      <h2>NapCat / OneBot</h2>
      <div class="row">
        {status_line}
      </div>
      <div class="hr"></div>
      <div class="muted">HTTP API：<span class="mono">{esc(api_url)}</span></div>
      <div class="muted">提示：命令行测试要用 POST，例如：</div>
      <div class="pre mono">curl -sS -X POST {esc(api_url)}/get_status -H "Content-Type: application/json" -d '{{}}'</div>
    </div>

    <div class="card">
      <h2>当前配置</h2>
      <div class="muted">TARGET_FRIENDS：</div>
      <div class="pre mono">{esc(targets_text)}</div>
      <div class="muted">定时：每天 {esc(schedule_time)}；每人 {esc(like_times)} 次；间隔 {esc(delay)} 秒</div>
      {f'<div class="muted">状态文件：<span class="mono">{esc(state_file)}</span></div>' if state_file else ''}
      <div class="hr"></div>
      <div class="row">
        <a href="/{action_suffix}">刷新页面</a>
        <span class="muted">（端口映射在 docker-compose.yml 的 like-bot1 -> ports）</span>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


def _make_admin_handler(
    controller: LikeController,
    bot: QQAutoLikeBot,
    store: StateStore,
    config: Dict[str, Any],
    admin_token: Optional[str],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "QQLikeAdmin/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[admin] {self.address_string()} - {fmt % args}")

        def _get_query(self) -> Tuple[str, Dict[str, List[str]]]:
            parsed = urlparse(self.path)
            return parsed.path, parse_qs(parsed.query)

        def _auth_ok(self, token: str) -> bool:
            if not admin_token:
                return True
            header_token = (self.headers.get("X-Admin-Token") or "").strip()
            if header_token == admin_token:
                return True
            return token == admin_token

        def _send_text(self, text: str, status: HTTPStatus) -> None:
            body = text.encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html_text: str) -> None:
            body = html_text.encode("utf-8")
            self.send_response(HTTPStatus.OK.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, obj: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER.value)
            self.send_header("Location", location)
            self.end_headers()

        def _read_body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except Exception:
                length = 0
            if length <= 0:
                return b""
            return self.rfile.read(length)

        def do_GET(self) -> None:  # noqa: N802
            path, query = self._get_query()
            token = (query.get("token", [""])[0] or "").strip()
            if not self._auth_ok(token):
                self._send_text("Unauthorized", HTTPStatus.UNAUTHORIZED)
                return

            if path in {"", "/"}:
                state = store.get()
                try:
                    next_run = (
                        schedule.jobs[0].next_run.isoformat(sep=" ", timespec="seconds") if schedule.jobs else ""
                    )
                except Exception:
                    next_run = ""

                napcat_error = ""
                napcat_status = None
                login_info = None
                try:
                    napcat_status = bot.get_status()
                except Exception as e:
                    napcat_error = str(e)
                try:
                    login_info = bot.get_login_info()
                except Exception as e:
                    napcat_error = napcat_error or str(e)

                page = _render_admin_page(
                    state=state,
                    config=config,
                    next_run=next_run,
                    napcat_status=napcat_status,
                    login_info=login_info,
                    napcat_error=napcat_error,
                    token=token if admin_token else "",
                )
                self._send_html(page)
                return

            if path == "/api/config":
                self._send_json(config)
                return

            if path == "/api/state":
                self._send_json(asdict(store.get()))
                return

            if path == "/api/next_run":
                try:
                    next_run = (
                        schedule.jobs[0].next_run.isoformat(sep=" ", timespec="seconds") if schedule.jobs else ""
                    )
                except Exception:
                    next_run = ""
                self._send_json({"next_run": next_run})
                return

            if path == "/api/napcat":
                napcat_error = ""
                napcat_status = None
                login_info = None
                try:
                    napcat_status = bot.get_status()
                except Exception as e:
                    napcat_error = str(e)
                try:
                    login_info = bot.get_login_info()
                except Exception as e:
                    napcat_error = napcat_error or str(e)
                self._send_json({"error": napcat_error, "status": napcat_status, "login": login_info})
                return

            self._send_text("Not Found", HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            path, query = self._get_query()
            token = (query.get("token", [""])[0] or "").strip()
            if not self._auth_ok(token):
                self._send_text("Unauthorized", HTTPStatus.UNAUTHORIZED)
                return

            body = self._read_body()
            content_type = (self.headers.get("Content-Type") or "").lower()

            form = {}
            payload = {}
            if content_type.startswith("application/json"):
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    payload = {}
            else:
                try:
                    form = parse_qs(body.decode("utf-8"))
                except Exception:
                    form = {}

            def form_value(key: str) -> str:
                values = form.get(key) or []
                return (values[0] if values else "").strip()

            if path == "/toggle_schedule":
                enabled = _parse_bool(form_value("enabled"), True)
                store.update(schedule_enabled=enabled)
                self._redirect(f"/{_token_qs(token if admin_token else '')}")
                return

            if path == "/like_once":
                user_id = form_value("user_id")
                try:
                    if user_id:
                        controller.like_users([user_id], 1, "manual")
                    else:
                        controller.like_all(1, "manual")
                except Exception as e:
                    store.update(
                        last_action="manual",
                        last_action_at=_now_str(),
                        last_action_ok=False,
                        last_action_detail=str(e),
                    )
                self._redirect(f"/{_token_qs(token if admin_token else '')}")
                return

            if path == "/api/like_once":
                try:
                    user_id = str(payload.get("user_id") or "").strip()
                    if user_id:
                        summary = controller.like_users([user_id], 1, "manual")
                    else:
                        summary = controller.like_all(1, "manual")
                    self._send_json(summary)
                except Exception as e:
                    self._send_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            if path == "/api/toggle_schedule":
                try:
                    enabled_raw = payload.get("enabled")
                    enabled = enabled_raw if isinstance(enabled_raw, bool) else _parse_bool(str(enabled_raw), True)
                    state = store.update(schedule_enabled=enabled)
                    self._send_json(asdict(state))
                except Exception as e:
                    self._send_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            if path == "/api/run":
                try:
                    user_id = str(payload.get("user_id") or "").strip()
                    times = payload.get("times", 1)
                    try:
                        times_int = int(times)
                    except Exception:
                        times_int = 1
                    times_int = max(1, min(times_int, 10))
                    reason = str(payload.get("reason") or "manual").strip() or "manual"
                    if user_id:
                        summary = controller.like_users([user_id], times_int, reason)
                    else:
                        summary = controller.like_all(times_int, reason)
                    self._send_json(summary)
                except Exception as e:
                    self._send_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return

            self._send_text("Not Found", HTTPStatus.NOT_FOUND)

    return Handler


def run_admin_server(
    host: str,
    port: int,
    controller: LikeController,
    bot: QQAutoLikeBot,
    store: StateStore,
    config: Dict[str, Any],
    admin_token: Optional[str],
) -> None:
    handler = _make_admin_handler(controller, bot, store, config, admin_token)
    httpd = ThreadingHTTPServer((host, port), handler)
    try:
        httpd.serve_forever(poll_interval=0.5)
    finally:
        httpd.server_close()


def main() -> None:
    API_URL = os.getenv("API_URL", "http://localhost:3000")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or None

    target_friends_str = os.getenv("TARGET_FRIENDS", "123456789")
    TARGET_FRIENDS = [f.strip() for f in target_friends_str.split(",") if f.strip()]

    LIKE_TIMES = _safe_int_env("LIKE_TIMES", 10)
    DELAY = _safe_int_env("DELAY", 2)
    SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")

    ADMIN_ENABLE = _parse_bool(os.getenv("ADMIN_ENABLE"), False)
    ADMIN_HOST = os.getenv("ADMIN_HOST", "0.0.0.0")
    ADMIN_PORT = _safe_int_env("ADMIN_PORT", 8080)
    ADMIN_PUBLIC_URL = os.getenv("ADMIN_PUBLIC_URL", "").strip()
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip() or None

    STATE_FILE = os.getenv("STATE_FILE") or None
    SCHEDULE_ENABLED = _parse_bool(os.getenv("SCHEDULE_ENABLED"), True)

    bot = QQAutoLikeBot(API_URL, ACCESS_TOKEN)
    store = StateStore(STATE_FILE, BotState(schedule_enabled=SCHEDULE_ENABLED))
    controller = LikeController(bot, TARGET_FRIENDS, DELAY, store)

    def like_task() -> None:
        if not store.get().schedule_enabled:
            print(f"[{_now_str()}] 自动点赞已关闭，跳过本次定时任务")
            return
        controller.like_all(LIKE_TIMES, "scheduled")

    schedule.clear()
    try:
        schedule.every().day.at(SCHEDULE_TIME).do(like_task)
    except Exception as e:
        raise ValueError(f"SCHEDULE_TIME 格式不正确：{SCHEDULE_TIME!r}，应为 HH:MM（例如 09:00）") from e

    print("QQ自动点赞机器人已启动！")
    print(f"OneBot API: {API_URL.rstrip('/')}")
    print(f"将在每天 {SCHEDULE_TIME} 自动执行点赞任务（每人 {LIKE_TIMES} 次，间隔 {DELAY}s）")
    print(f"目标好友: {len(TARGET_FRIENDS)} 个")
    if ADMIN_ENABLE:
        public_url = ADMIN_PUBLIC_URL or f"http://localhost:{ADMIN_PORT}"
        print(f"点赞管理页面: {public_url}")
        if ADMIN_TOKEN:
            print("管理页面已启用 token：请使用 ?token=xxx 访问")
    print("按 Ctrl+C 停止运行\n")

    if ADMIN_ENABLE:
        stop_event = threading.Event()

        def scheduler_loop() -> None:
            while not stop_event.is_set():
                schedule.run_pending()
                time.sleep(1)

        thread = threading.Thread(target=scheduler_loop, name="scheduler", daemon=True)
        thread.start()

        admin_config: Dict[str, Any] = {
            "api_url": API_URL.rstrip("/"),
            "targets": TARGET_FRIENDS,
            "like_times": LIKE_TIMES,
            "delay": DELAY,
            "schedule_time": SCHEDULE_TIME,
            "state_file": STATE_FILE or "",
        }
        try:
            run_admin_server(ADMIN_HOST, ADMIN_PORT, controller, bot, store, admin_config, ADMIN_TOKEN)
        finally:
            stop_event.set()
            thread.join(timeout=5)
    else:
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n机器人已停止运行")
