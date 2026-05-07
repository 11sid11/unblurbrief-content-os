from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "workflow_config.json"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
AUTH_URL = "https://www.canva.com/api/oauth/authorize"


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict[str, Any]:
    data = load_json(CONFIG_FILE, {})
    return data if isinstance(data, dict) else {}


def save_config_updates(updates: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    cfg.update(updates)
    save_json(CONFIG_FILE, cfg)
    return cfg


def require_canva_app_config() -> dict[str, Any]:
    cfg = load_config()
    missing = []
    if not str(cfg.get("canva_client_id", "")).strip():
        missing.append("canva_client_id")
    if not str(cfg.get("canva_client_secret", "")).strip():
        missing.append("canva_client_secret")
    if not str(cfg.get("canva_redirect_uri", "")).strip():
        missing.append("canva_redirect_uri")
    if missing:
        raise RuntimeError(
            "Missing Canva OAuth config in workflow_config.json: "
            + ", ".join(missing)
            + ". Create a Canva Connect integration first, then add these values."
        )
    return cfg


def base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def generate_pkce_pair() -> tuple[str, str]:
    verifier = base64url(secrets.token_bytes(64))
    challenge = base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def build_authorization_url(code_challenge: str, state: str) -> str:
    cfg = require_canva_app_config()
    params = {
        "client_id": str(cfg["canva_client_id"]).strip(),
        "redirect_uri": str(cfg["canva_redirect_uri"]).strip(),
        "response_type": "code",
        "scope": str(cfg.get("canva_scopes", "")).strip(),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_token(code: str, code_verifier: str) -> dict[str, Any]:
    cfg = require_canva_app_config()
    client_id = str(cfg["canva_client_id"]).strip()
    client_secret = str(cfg["canva_client_secret"]).strip()
    redirect_uri = str(cfg["canva_redirect_uri"]).strip()

    headers = {
        "Authorization": basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=60)
    payload = response.json() if response.text else {}
    if not response.ok:
        raise RuntimeError(f"Canva token exchange failed {response.status_code}: {payload}")
    return payload


def refresh_canva_token() -> dict[str, Any]:
    cfg = require_canva_app_config()
    refresh_token = str(cfg.get("canva_refresh_token", "")).strip()
    if not refresh_token:
        raise RuntimeError("Missing canva_refresh_token. Run Connect Canva first.")

    client_id = str(cfg["canva_client_id"]).strip()
    client_secret = str(cfg["canva_client_secret"]).strip()
    headers = {
        "Authorization": basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    scope = str(cfg.get("canva_scopes", "")).strip()
    if scope:
        data["scope"] = scope

    response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=60)
    payload = response.json() if response.text else {}
    if not response.ok:
        raise RuntimeError(f"Canva refresh token failed {response.status_code}: {payload}")

    save_token_payload(payload)
    return payload


def save_token_payload(payload: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    expires_in = int(payload.get("expires_in", 0) or 0)
    updates = {
        "canva_enabled": True,
        "canva_access_token": payload.get("access_token", ""),
        "canva_refresh_token": payload.get("refresh_token", ""),
        "canva_token_expires_at": now + expires_in,
        "canva_token_scope": payload.get("scope", ""),
        "canva_token_type": payload.get("token_type", "Bearer"),
        "canva_last_connected_at": now,
    }
    save_config_updates(updates)
    return updates


def get_valid_canva_access_token(min_seconds_remaining: int = 300) -> str:
    cfg = load_config()
    token = str(cfg.get("canva_access_token", "")).strip()
    expires_at = int(cfg.get("canva_token_expires_at", 0) or 0)
    now = int(time.time())

    if token and expires_at > now + min_seconds_remaining:
        return token

    payload = refresh_canva_token()
    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Canva token refresh did not return an access token.")
    return token


def canva_auth_status() -> dict[str, Any]:
    cfg = load_config()
    now = int(time.time())
    expires_at = int(cfg.get("canva_token_expires_at", 0) or 0)
    has_access = bool(str(cfg.get("canva_access_token", "")).strip())
    has_refresh = bool(str(cfg.get("canva_refresh_token", "")).strip())
    return {
        "canva_enabled": bool(cfg.get("canva_enabled", False)),
        "has_access_token": has_access,
        "has_refresh_token": has_refresh,
        "expires_at": expires_at,
        "seconds_remaining": max(0, expires_at - now) if expires_at else 0,
        "scope": cfg.get("canva_token_scope", ""),
        "client_id_present": bool(str(cfg.get("canva_client_id", "")).strip()),
        "client_secret_present": bool(str(cfg.get("canva_client_secret", "")).strip()),
        "redirect_uri": cfg.get("canva_redirect_uri", ""),
    }


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server_version = "UnblurBriefCanvaOAuth/1.0"

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.callback_path = parsed.path
        self.server.query_params = params

        code = params.get("code", [""])[0]
        error = params.get("error", [""])[0]

        if error:
            html = f"<html><body><h2>Canva authorization failed</h2><p>{error}</p><p>You can close this tab.</p></body></html>"
        elif code:
            html = "<html><body><h2>Canva connected</h2><p>You can close this tab and return to UnblurBrief OS.</p></body></html>"
        else:
            html = "<html><body><h2>No authorization code received</h2><p>You can close this tab.</p></body></html>"

        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

        self.server.received = True


def start_oauth_callback_server() -> ThreadingHTTPServer:
    cfg = require_canva_app_config()
    redirect_uri = urllib.parse.urlparse(str(cfg["canva_redirect_uri"]).strip())
    host = redirect_uri.hostname or "127.0.0.1"
    port = redirect_uri.port or 8787

    server = ThreadingHTTPServer((host, port), OAuthCallbackHandler)
    server.received = False
    server.query_params = {}
    server.callback_path = ""

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def wait_for_oauth_callback(server: ThreadingHTTPServer, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    try:
        while time.time() < deadline:
            if getattr(server, "received", False):
                return {
                    "query_params": getattr(server, "query_params", {}),
                    "callback_path": getattr(server, "callback_path", ""),
                }
            time.sleep(0.2)
        raise TimeoutError("Timed out waiting for Canva OAuth callback.")
    finally:
        server.shutdown()
        server.server_close()


def connect_canva(open_url_callback=None) -> dict[str, Any]:
    cfg = require_canva_app_config()
    timeout = int(cfg.get("canva_auth_timeout_seconds", 300) or 300)

    code_verifier, code_challenge = generate_pkce_pair()
    state = base64url(secrets.token_bytes(24))
    auth_url = build_authorization_url(code_challenge, state)

    # Important: start the callback server BEFORE opening Canva.
    # This prevents stale/late callbacks from a previous attempt and avoids a race
    # where Canva returns before localhost is listening.
    server = start_oauth_callback_server()

    try:
        if open_url_callback:
            open_url_callback(auth_url)
        else:
            webbrowser.open(auth_url)

        callback = wait_for_oauth_callback(server, timeout)
    except OSError as exc:
        raise RuntimeError(
            "Could not start the Canva OAuth callback server on the configured redirect URI. "
            "Close other running UnblurBrief windows or anything using port 8787, then retry. "
            f"Original error: {exc}"
        ) from exc

    params = callback["query_params"]

    returned_state = params.get("state", [""])[0]
    if returned_state != state:
        raise RuntimeError(
            "Canva OAuth state mismatch. Authorization aborted. "
            "Close all old Canva authorization tabs, restart START_HERE.bat, then click Connect Canva only once. "
            f"Expected state prefix: {state[:8]}..., received state prefix: {returned_state[:8]}..."
        )

    error = params.get("error", [""])[0]
    if error:
        description = params.get("error_description", [""])[0]
        raise RuntimeError(f"Canva authorization error: {error} {description}".strip())

    code = params.get("code", [""])[0]
    if not code:
        raise RuntimeError(f"No authorization code received from Canva callback: {params}")

    token_payload = exchange_code_for_token(code, code_verifier)
    saved = save_token_payload(token_payload)

    return {
        "ok": True,
        "message": "Canva connected successfully.",
        "token_type": token_payload.get("token_type", "Bearer"),
        "expires_in": token_payload.get("expires_in"),
        "scope": token_payload.get("scope", ""),
        "expires_at": saved.get("canva_token_expires_at"),
    }


if __name__ == "__main__":
    result = connect_canva()
    print(json.dumps(result, ensure_ascii=False, indent=2))
