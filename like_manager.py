#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import html
import json
import os
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests


def _parse_bots(value: str) -> List[Tuple[str, str]]:
    bots: List[Tuple[str, str]] = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, url = part.split("=", 1)
            name = name.strip()
            url = url.strip()
        else:
            url = part
            name = url
        url = url.rstrip("/")
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        bots.append((name or url, url))
    return bots


def _safe_get_json(url: str, timeout: float) -> Tuple[Optional[Any], str]:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json(), ""
    except Exception as e:
        return None, str(e)


def _safe_post_json(url: str, payload: Dict[str, Any], timeout: float) -> Tuple[Optional[Any], str]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json(), ""
    except Exception as e:
        return None, str(e)


@dataclass(frozen=True)
class BotInfo:
    name: str
    base_url: str


def _render_index() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QQLike 统一点赞管理</title>
  <style>
    body { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; background:#0b0f14; color:#e6edf3; margin:0; }
    .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
    h1 { font-size: 18px; margin: 0 0 10px; }
    .muted { color:#9da7b3; font-size: 12px; }
    .grid { display:grid; grid-template-columns: 1fr; gap: 14px; margin-top: 12px; }
    @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
    .card { background:#111827; border:1px solid #243043; border-radius: 12px; padding: 14px; }
    .row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    .pill { display:inline-block; padding: 4px 8px; border-radius: 999px; background:#0f172a; border:1px solid #243043; font-size: 12px; }
    .ok { background:#2dba4e; border-color:#2dba4e; color:#041; }
    .bad { background:#ff7b72; border-color:#ff7b72; color:#2d0b0b; }
    .mono { font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace; }
    .btn { cursor:pointer; border:1px solid #2dba4e; background:#2dba4e; color:#041; padding: 7px 10px; border-radius: 8px; font-weight: 700; }
    .btn.secondary { background:transparent; color:#e6edf3; border-color:#243043; }
    .btn.danger { background:#ff7b72; border-color:#ff7b72; color:#2d0b0b; }
    input { background:#0b1220; color:#e6edf3; border:1px solid #243043; border-radius:8px; padding:7px 9px; }
    .pre { white-space: pre-wrap; word-break: break-word; background:#0b1220; border:1px solid #243043; border-radius: 10px; padding: 10px; }
    .hr { height:1px; background:#243043; margin: 10px 0; }
    a { color:#7ee787; }
  </style>
</head>
<body>
  <div class="container">
    <div class="row" style="justify-content: space-between;">
      <div>
        <h1>QQLike 统一点赞管理</h1>
        <div class="muted">说明：NapCat WebUI 仍需分别登录；这里只统一管理多个 like-bot 的定时开关/手动执行。</div>
      </div>
      <div class="row">
        <button class="btn secondary" onclick="refreshAll()">刷新</button>
      </div>
    </div>
    <div id="meta" class="muted" style="margin-top:10px;"></div>
    <div id="grid" class="grid"></div>
  </div>

<script>
  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async function api(path, options) {
    const res = await fetch(path, options);
    const text = await res.text();
    let data = null;
    try { data = JSON.parse(text); } catch (e) { data = { error: text }; }
    if (!res.ok) throw new Error(data?.error || (res.status + " " + res.statusText));
    return data;
  }

  async function refreshAll() {
    const meta = document.getElementById("meta");
    meta.textContent = "加载中...";
    try {
      const data = await api("/api/bots");
      meta.textContent = "更新时间：" + (data.now || "");
      render(data.bots || []);
    } catch (e) {
      meta.textContent = "加载失败：" + e.message;
      render([]);
    }
  }

  function pill(text, cls) {
    return `<span class="pill ${cls||""}">${esc(text)}</span>`;
  }

  function render(bots) {
    const grid = document.getElementById("grid");
    if (!bots.length) {
      grid.innerHTML = `<div class="card"><div class="muted">没有可用的 like-bot（检查 like-manager 的 LIKE_BOTS 配置）。</div></div>`;
      return;
    }
    grid.innerHTML = bots.map(b => {
      const err = b.error || "";
      const state = b.state || {};
      const cfg = b.config || {};
      const nap = b.napcat || {};
      const napErr = nap.error || "";
      const online = nap.status?.data?.online;
      const loginData = nap.login?.data || null;
      const loginText = loginData ? `${loginData.nickname || ""} (${loginData.user_id || ""})` : "";

      const scheduleEnabled = state.schedule_enabled;
      const schedulePill = scheduleEnabled ? pill("定时：开启", "ok") : pill("定时：关闭", "bad");
      const botPill = err ? pill("Bot连接失败", "bad") : pill("Bot可用", "ok");
      const napPill = napErr ? pill("NapCat连接失败", "bad") : pill("NapCat在线：" + String(online), online ? "ok" : "");

      const last = state.last_action_at ? `最近：${state.last_action || ""} @ ${state.last_action_at}（${state.last_action_ok === true ? "成功" : (state.last_action_ok === false ? "失败" : "未知")}）` : "最近：无";
      const next = b.next_run || "";
      const targets = Array.isArray(cfg.targets) ? cfg.targets.join(", ") : "";
      const likeTimes = cfg.like_times ?? "";
      const delay = cfg.delay ?? "";
      const scheduleTime = cfg.schedule_time ?? "";

      return `
        <div class="card">
          <div class="row" style="justify-content: space-between;">
            <div class="row">
              <span class="pill mono">${esc(b.name)}</span>
              <span class="pill mono">${esc(b.base_url)}</span>
            </div>
            <div class="row">
              ${botPill}
              ${schedulePill}
            </div>
          </div>
          <div class="hr"></div>
          <div class="row">
            ${napPill}
            ${loginText ? pill("已登录：" + loginText, "ok") : pill("未登录/未知", "")}
          </div>
          ${err ? `<div class="muted" style="margin-top:8px;">Bot错误：${esc(err)}</div>` : ""}
          ${napErr ? `<div class="muted" style="margin-top:8px;">NapCat错误：${esc(napErr)}</div>` : ""}
          <div class="muted" style="margin-top:8px;">${esc(last)}</div>
          <div class="muted" style="margin-top:4px;">下次执行：<span class="mono">${esc(next || "（未知）")}</span></div>
          <div class="hr"></div>
          <div class="muted">TARGET_FRIENDS：</div>
          <div class="pre mono">${esc(targets || "")}</div>
          <div class="muted" style="margin-top:6px;">定时：每天 ${esc(scheduleTime)}；每人 ${esc(likeTimes)} 次；间隔 ${esc(delay)} 秒</div>
          <div class="hr"></div>
          <div class="row">
            <button class="btn secondary" onclick="toggleSchedule('${esc(b.name)}', true)">开启定时</button>
            <button class="btn danger" onclick="toggleSchedule('${esc(b.name)}', false)">关闭定时</button>
            <button class="btn" onclick="runNow('${esc(b.name)}', ${Number(likeTimes||1) || 1})">立即执行（${esc(likeTimes||1)}次）</button>
            <button class="btn secondary" onclick="runNow('${esc(b.name)}', 1)">点赞1次</button>
          </div>
          <div class="row" style="margin-top:10px;">
            <input class="mono" id="qq_${esc(b.name)}" placeholder="指定QQ（可选）" style="min-width: 200px;" />
            <button class="btn secondary" onclick="runForQQ('${esc(b.name)}')">对该QQ执行</button>
          </div>
          ${state.last_action_detail ? `<div class="muted" style="margin-top:10px;">最近详情：</div><div class="pre mono">${esc(state.last_action_detail)}</div>` : ""}
        </div>
      `;
    }).join("");
  }

  async function toggleSchedule(name, enabled) {
    try {
      await api(`/api/bot/toggle_schedule?name=${encodeURIComponent(name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled })
      });
      await refreshAll();
    } catch (e) {
      alert("操作失败：" + e.message);
    }
  }

  async function runNow(name, times) {
    try {
      await api(`/api/bot/run?name=${encodeURIComponent(name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ times, reason: "manual" })
      });
      await refreshAll();
    } catch (e) {
      alert("操作失败：" + e.message);
    }
  }

  async function runForQQ(name) {
    const el = document.getElementById("qq_" + name);
    const user_id = (el?.value || "").trim();
    if (!user_id) { alert("请输入QQ号"); return; }
    try {
      await api(`/api/bot/run?name=${encodeURIComponent(name)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id, times: 1, reason: "manual" })
      });
      await refreshAll();
    } catch (e) {
      alert("操作失败：" + e.message);
    }
  }

  refreshAll();
  setInterval(refreshAll, 15000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "QQLikeManager/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[manager] {self.address_string()} - {fmt % args}")

    def _get_query(self) -> Tuple[str, Dict[str, List[str]]]:
        parsed = urlparse(self.path)
        return parsed.path, parse_qs(parsed.query)

    def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def _send_html(self, text: str) -> None:
        self._send(HTTPStatus.OK, "text/html; charset=utf-8", text.encode("utf-8"))

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        path, query = self._get_query()
        if path in {"", "/"}:
            self._send_html(_render_index())
            return

        if path == "/api/bots":
            bots = self.server.bots  # type: ignore[attr-defined]
            timeout = self.server.timeout_s  # type: ignore[attr-defined]
            out: List[Dict[str, Any]] = []
            for bot in bots:
                base = bot.base_url
                item: Dict[str, Any] = {"name": bot.name, "base_url": base}

                cfg, cfg_err = _safe_get_json(f"{base}/api/config", timeout)
                state, state_err = _safe_get_json(f"{base}/api/state", timeout)
                next_run, nr_err = _safe_get_json(f"{base}/api/next_run", timeout)
                napcat, nap_err = _safe_get_json(f"{base}/api/napcat", timeout)

                item["config"] = cfg or {}
                item["state"] = state or {}
                item["next_run"] = (next_run or {}).get("next_run") if isinstance(next_run, dict) else ""
                item["napcat"] = napcat or {}

                errors = [e for e in [cfg_err, state_err, nr_err, nap_err] if e]
                item["error"] = "; ".join(errors)
                out.append(item)

            self._send_json({"now": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "bots": out})
            return

        self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not Found")

    def do_POST(self) -> None:  # noqa: N802
        path, query = self._get_query()
        if path == "/api/bot/toggle_schedule":
            name = (query.get("name", [""])[0] or "").strip()
            payload = self._read_json()
            enabled = payload.get("enabled", True)
            bots = self.server.bots  # type: ignore[attr-defined]
            timeout = self.server.timeout_s  # type: ignore[attr-defined]
            target = next((b for b in bots if b.name == name), None)
            if not target:
                self._send_json({"error": f"Unknown bot: {html.escape(name)}"}, HTTPStatus.NOT_FOUND)
                return
            data, err = _safe_post_json(f"{target.base_url}/api/toggle_schedule", {"enabled": enabled}, timeout)
            if err:
                self._send_json({"error": err}, HTTPStatus.BAD_GATEWAY)
                return
            self._send_json(data)
            return

        if path == "/api/bot/run":
            name = (query.get("name", [""])[0] or "").strip()
            payload = self._read_json()
            bots = self.server.bots  # type: ignore[attr-defined]
            timeout = self.server.timeout_s  # type: ignore[attr-defined]
            target = next((b for b in bots if b.name == name), None)
            if not target:
                self._send_json({"error": f"Unknown bot: {html.escape(name)}"}, HTTPStatus.NOT_FOUND)
                return
            data, err = _safe_post_json(f"{target.base_url}/api/run", payload, timeout)
            if err:
                self._send_json({"error": err}, HTTPStatus.BAD_GATEWAY)
                return
            self._send_json(data)
            return

        self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not Found")


def main() -> None:
    host = os.getenv("MANAGER_HOST", "0.0.0.0")
    port = int(os.getenv("MANAGER_PORT", "8090"))
    timeout_s = float(os.getenv("MANAGER_HTTP_TIMEOUT", "5"))

    bots_env = os.getenv("LIKE_BOTS", "")
    bots_list = _parse_bots(bots_env)
    bots = [BotInfo(name=n, base_url=u) for n, u in bots_list]

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.bots = bots  # type: ignore[attr-defined]
    httpd.timeout_s = timeout_s  # type: ignore[attr-defined]

    print("QQLike unified manager started")
    print(f"Listen: http://{host}:{port}")
    print(f"LIKE_BOTS: {bots_env}")
    httpd.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()

