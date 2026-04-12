#!/usr/bin/env python3
import os
import pty
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("/home/guidda/.openclaw/workspace/tmp/pw-openai-auth-profile")
CHROME = "/home/guidda/.cache/ms-playwright/chromium-1208/chrome-linux64/chrome"
EMAIL_HINT = os.environ.get("OPENCLAW_GOOGLE_EMAIL", "")
LOGIN_CMD = ["openclaw", "models", "auth", "login", "--provider", "openai-codex"]
OPEN_RE = re.compile(r"Open:\s+(https://\S+)")
SUCCESS_MARKERS = [
    "OpenAI OAuth complete",
    "Auth profile: openai-codex:default",
]
CALLBACK_PREFIX = "http://localhost:1455/auth/callback"
STATUS_CMD = ["openclaw", "models", "status", "--status-plain"]


def click_any(page, labels):
    for label in labels:
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=label, exact=False)
                if loc.count() > 0:
                    loc.first.click(timeout=4000)
                    return f"{role}:{label}"
            except Exception:
                pass
        try:
            loc = page.get_by_text(label, exact=False)
            if loc.count() > 0:
                loc.first.click(timeout=4000)
                return f"text:{label}"
        except Exception:
            pass
    return None


def browser_flow(auth_url):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    captured = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=CHROME,
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        def remember(url: str):
            if url.startswith(CALLBACK_PREFIX) and url not in captured:
                captured.append(url)
                print(f"[reauth] callback captured: {url}", flush=True)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("framenavigated", lambda frame: remember(frame.url))
        page.on("request", lambda req: remember(req.url))
        page.goto(auth_url, wait_until="domcontentloaded", timeout=60000)
        print(f"[reauth] opened auth url: {page.url}", flush=True)
        time.sleep(2)

        deadline = time.time() + 90
        while time.time() < deadline and not captured:
            for pg in list(ctx.pages):
                click_any(pg, ["Continue with Google", "Google로 계속", "Sign in with Google"])
                if EMAIL_HINT:
                    click_any(pg, [EMAIL_HINT])
                click_any(pg, ["Continue", "계속", "Allow", "동의", "Authorize"])
            time.sleep(1)

        time.sleep(1)
        ctx.close()
        if not captured:
            raise RuntimeError("callback URL was not captured")
        return captured[-1]


def auth_status_ok() -> bool:
    try:
        res = subprocess.run(
            STATUS_CMD,
            capture_output=True,
            text=True,
            timeout=20,
            env=os.environ.copy(),
        )
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        return "openai-codex:default ok expires in" in out
    except Exception:
        return False


def main():
    os.environ.setdefault("DISPLAY", ":0")
    os.environ.setdefault("WAYLAND_DISPLAY", "wayland-0")
    os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    os.environ.setdefault("PULSE_SERVER", "unix:/mnt/wslg/PulseServer")

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        LOGIN_CMD,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=False,
        close_fds=True,
        env=os.environ.copy(),
    )
    os.close(slave_fd)

    full = ""
    auth_url = None
    callback_sent = False
    done = False

    try:
        while True:
            r, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in r:
                try:
                    chunk = os.read(master_fd, 4096).decode("utf-8", errors="ignore")
                except OSError:
                    chunk = ""
                if chunk:
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    full += chunk
                    m = OPEN_RE.search(full)
                    if m and not auth_url:
                        auth_url = m.group(1)
                        print(f"\n[reauth] auth url found", flush=True)
                        callback = browser_flow(auth_url)
                        os.write(master_fd, (callback + "\n").encode())
                        callback_sent = True
                        print("[reauth] callback pasted back into openclaw", flush=True)

                    if any(marker in full for marker in SUCCESS_MARKERS):
                        done = True
                        break

            rc = proc.poll()
            if rc is not None:
                if not done:
                    done = rc == 0 and any(marker in full for marker in SUCCESS_MARKERS)
                break

        rc = proc.wait(timeout=5)
        if not done and callback_sent and auth_status_ok():
            done = True
            rc = 0
        if not done:
            raise SystemExit(rc or 1)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass

    print("[reauth] completed successfully", flush=True)


if __name__ == "__main__":
    main()
