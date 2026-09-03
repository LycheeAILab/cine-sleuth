#!/usr/bin/env python3
"""Authenticate CineSleuth with a revocable LycheeAILab user API key."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlencode
import urllib.error
import urllib.request
import webbrowser


DEFAULT_BASE_URL = "https://lab.lycheeai.com.cn"


class AuthenticationError(RuntimeError):
    pass


def token_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "LycheeAILab" / "cine-sleuth-token.json"


def save_token(token: str) -> None:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"accessToken": token}), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_token() -> str | None:
    environment_token = os.environ.get("LYCHEE_LAB_TOKEN")
    if environment_token:
        return environment_token.strip()
    try:
        value = json.loads(token_path().read_text(encoding="utf-8"))["accessToken"]
        return value if isinstance(value, str) and value.startswith("lych_live_") else None
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None


def validate_token(token: str, base_url: str = DEFAULT_BASE_URL) -> bool:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/skill-auth/me",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "CineSleuth-Skill/1.0.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def browser_login(base_url: str = DEFAULT_BASE_URL, timeout_seconds: int = 180) -> str:
    state = secrets.token_urlsafe(32)
    result: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/callback":
                self.send_error(404)
                return
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            fields = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            received_state = fields.get("state", [""])[0]
            api_key = fields.get("api_key", [""])[0]
            if not secrets.compare_digest(received_state, state) or not api_key.startswith("lych_live_"):
                self.send_error(403)
                return
            result["api_key"] = api_key
            body = "<!doctype html><meta charset='utf-8'><title>Authorized</title><style>body{font-family:sans-serif;display:grid;place-items:center;height:100vh;margin:0}p{color:#555}</style><div><h2>CineSleuth 已授权</h2><p>可以关闭此窗口并返回智能体。</p></div><script>setTimeout(()=>window.close(),500)</script>".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    server.timeout = timeout_seconds
    callback = f"http://127.0.0.1:{server.server_port}/callback"
    authorize_url = f"{base_url.rstrip('/')}/skill-auth?{urlencode({'callback': callback, 'state': state, 'skill': 'CineSleuth'})}"
    print(f"Authorize CineSleuth at:\n{authorize_url}", flush=True)
    webbrowser.open(authorize_url)
    server.handle_request()
    server.server_close()
    token = result.get("api_key")
    if not token:
        raise AuthenticationError("LycheeAILab browser authorization timed out or was rejected")
    save_token(token)
    return token


def authorized_token(base_url: str = DEFAULT_BASE_URL, force_login: bool = False) -> str:
    token = None if force_login else load_token()
    if token and validate_token(token, base_url):
        return token
    token = browser_login(base_url)
    if not validate_token(token, base_url):
        raise AuthenticationError("LycheeAILab returned a credential that could not be validated")
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("LYCHEE_LAB_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    authorized_token(args.base_url, args.force)
    print(json.dumps({"authenticated": True, "runtime_ready": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
