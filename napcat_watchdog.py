#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import docker
import requests


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_items(raw: str) -> List[Tuple[str, str]]:
    """
    Format: "like-bot1|napcat_account1,like-bot2|napcat_account2"
    Left: like-bot service name (base URL will be http://<service>:8080)
    Right: docker container name to restart.
    """
    items: List[Tuple[str, str]] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "|" not in part:
            raise ValueError(f"WATCH_ITEMS 格式不正确（缺少 | ）: {part!r}")
        bot_service, napcat_container = part.split("|", 1)
        bot_service = bot_service.strip()
        napcat_container = napcat_container.strip()
        if not bot_service or not napcat_container:
            raise ValueError(f"WATCH_ITEMS 格式不正确（空字段）: {part!r}")
        items.append((bot_service, napcat_container))
    return items


@dataclass
class WatchState:
    not_logged_since: Optional[float] = None
    last_restart_at: Optional[float] = None


def _is_logged_in(napcat_payload: Dict) -> bool:
    if not isinstance(napcat_payload, dict):
        return False
    if napcat_payload.get("error"):
        return False
    login = napcat_payload.get("login")
    if not isinstance(login, dict):
        return False
    data = login.get("data")
    if not isinstance(data, dict):
        return False
    user_id = data.get("user_id")
    return bool(user_id)


def main() -> None:
    watch_items = _parse_items(os.getenv("WATCH_ITEMS", "like-bot1|napcat_account1"))
    check_interval = float(os.getenv("CHECK_INTERVAL", "30"))
    relogin_delay = float(os.getenv("RELOGIN_DELAY", "300"))  # 5 minutes
    http_timeout = float(os.getenv("HTTP_TIMEOUT", "5"))

    client = docker.DockerClient(base_url=os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))

    states: Dict[str, WatchState] = {bot: WatchState() for bot, _ in watch_items}

    print(f"[{_now_str()}] napcat_watchdog started")
    print(f"[{_now_str()}] WATCH_ITEMS={','.join([f'{b}|{c}' for b, c in watch_items])}")
    print(f"[{_now_str()}] CHECK_INTERVAL={check_interval}s RELLOGIN_DELAY={relogin_delay}s HTTP_TIMEOUT={http_timeout}s")

    while True:
        loop_started = time.time()
        for bot_service, napcat_container in watch_items:
            url = f"http://{bot_service}:8080/api/napcat"
            st = states.setdefault(bot_service, WatchState())
            ok = False
            err = ""
            payload = None
            try:
                r = requests.get(url, timeout=http_timeout)
                r.raise_for_status()
                payload = r.json()
                ok = _is_logged_in(payload)
            except Exception as e:
                err = str(e)
                ok = False

            if ok:
                if st.not_logged_since is not None:
                    print(f"[{_now_str()}] {bot_service}: login ok again; clear timer")
                st.not_logged_since = None
                continue

            now = time.time()
            if st.not_logged_since is None:
                st.not_logged_since = now
                reason = payload.get("error") if isinstance(payload, dict) else err
                print(f"[{_now_str()}] {bot_service}: not logged in; start 5min timer ({reason})")
                continue

            elapsed = now - st.not_logged_since
            if elapsed < relogin_delay:
                continue

            # Try restart napcat container as "relogin attempt"
            try:
                print(f"[{_now_str()}] {bot_service}: try restart {napcat_container} (elapsed={int(elapsed)}s)")
                container = client.containers.get(napcat_container)
                container.restart(timeout=20)
                st.last_restart_at = now
                st.not_logged_since = now  # reset timer: next attempt after another relogin_delay
            except Exception as e:
                print(f"[{_now_str()}] {bot_service}: restart failed: {e}")
                # avoid tight loop on repeated failures
                st.not_logged_since = now

        spent = time.time() - loop_started
        sleep_s = max(1.0, check_interval - spent)
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()

