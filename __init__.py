"""Kiro provider — Claude models via Kiro Pro subscription or AWS Builder ID.

Registers Kiro as a provider in the model picker. Handles the full setup
chain automatically: gateway installation, auth (social login or OIDC),
gateway lifecycle. No manual steps required.

Architecture:
    kiro-cli (Pro) / OIDC (free)  --→  kiro-gateway (:8000)  --→  Hermes
    social login / device flow          OpenAI-compatible            /model

Setup (handled automatically by the provider):
    Pro:  kiro-cli login --use-device-flow → browser OAuth
    Free: OIDC device flow → visit URL → enter code (no kiro-cli needed)
    Plugin extracts token, configures .env, starts gateway (auto)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile

logger = logging.getLogger(__name__)

# ── Gateway constants ────────────────────────────────────────────────────
_GATEWAY_DIR = Path.home() / ".kiro-gateway"
_GATEWAY_PORT = 8000
_GATEWAY_URL = f"http://localhost:{_GATEWAY_PORT}/v1"
_PID_FILE = Path.home() / ".hermes" / "kiro" / "gateway.pid"
_PROXY_KEY = "hermes-kiro-gateway-proxy-key-2026"
_KIRO_CLI_DB = Path.home() / ".local" / "share" / "kiro-cli" / "data.sqlite3"
_GATEWAY_CLONE_LOCK = threading.Lock()

_CREDS_JSON = _GATEWAY_DIR / "credentials.json"

# ── OIDC constants ───────────────────────────────────────────────────────
_OIDC_BASE = "https://oidc.us-east-1.amazonaws.com"
_OIDC_START_URL = "https://view.awsapps.com/start"
_OIDC_SCOPES = [
    "codewhisperer:completions",
    "codewhisperer:analysis",
    "codewhisperer:conversations",
    "codewhisperer:transformations",
    "codewhisperer:taskassist",
]
_OIDC_GRANT_TYPES = [
    "urn:ietf:params:oauth:grant-type:device_code",
    "refresh_token",
]

# ── Token extraction ─────────────────────────────────────────────────────

def _extract_refresh_token_from_creds_json() -> str | None:
    """Extract the most recent refresh token from credentials.json.

    The gateway persists rotated refresh tokens here. This is often fresher
    than the kiro-cli SQLite token (which may have been consumed by the
    gateway and is now stale).
    """
    if not _CREDS_JSON.exists():
        return None
    try:
        data = json.loads(_CREDS_JSON.read_text())
        if isinstance(data, list) and data:
            token = data[0].get("refresh_token")
            if token and len(token) > 20:
                return token
    except Exception as e:
        logger.debug("Kiro: failed to read credentials.json: %s", e)
    return None


def _extract_refresh_token() -> str | None:
    """Extract refresh token — credentials.json first, then kiro-cli SQLite.

    credentials.json holds rotated tokens persisted by the gateway, so it's
    always fresher than the SQLite login token (which may be single-use
    consumed). Falls back to SQLite for first-time setup.
    """
    token = _extract_refresh_token_from_creds_json()
    if token:
        return token

    if not _KIRO_CLI_DB.exists():
        return None

    try:
        db = sqlite3.connect(str(_KIRO_CLI_DB))
        for key in ("kirocli:social:token", "kirocli:odic:token"):
            row = db.execute(
                "SELECT value FROM auth_kv WHERE key = ?", (key,)
            ).fetchone()
            if row:
                data = json.loads(row[0])
                rt = data.get("refresh_token")
                if rt:
                    return rt
        db.close()
    except Exception as e:
        logger.debug("Kiro: failed to read SQLite: %s", e)
    return None


# ── OIDC device flow (AWS Builder ID — no kiro-cli needed) ───────────────

def _oidc_request(method: str, path: str, body: dict | None = None,
                  headers: dict | None = None) -> dict:
    """Make an OIDC request. Returns parsed JSON response."""
    url = _OIDC_BASE + path
    data = json.dumps(body).encode() if body else None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"OIDC {method} {path} failed: HTTP {e.code} — {body}")


def _oidc_register_client() -> tuple[str, str]:
    """Register an OIDC client. Returns (client_id, client_secret)."""
    payload = {
        "clientName": "Hermes Kiro Plugin",
        "clientType": "public",
        "scopes": _OIDC_SCOPES,
        "grantTypes": _OIDC_GRANT_TYPES,
        "issuerUrl": _OIDC_START_URL,
    }
    result = _oidc_request("POST", "/client/register", payload)
    return result["clientId"], result["clientSecret"]


def _oidc_start_device_auth(client_id: str, client_secret: str) -> dict:
    """Start device authorization. Returns {device_code, user_code, verification_uri, interval}."""
    payload = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "startUrl": _OIDC_START_URL,
    }
    result = _oidc_request("POST", "/device_authorization", payload)
    return {
        "device_code": result["deviceCode"],
        "user_code": result["userCode"],
        "verification_uri": result.get("verificationUri",
                                         "https://view.awsapps.com/start"),
        "interval": result.get("interval", 5),
    }


def _oidc_poll_for_token(client_id: str, client_secret: str,
                         device_code: str, interval: int,
                         timeout_sec: int = 120) -> dict:
    """Poll for OIDC token. Returns {access_token, refresh_token, expires_in}.

    Blocks until user completes authorization or timeout.
    """
    payload = {
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": "urn:ietf:params:oauth:grant-type:device_code",
        "deviceCode": device_code,
    }
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            result = _oidc_request("POST", "/token", payload)
            return {
                "access_token": result["accessToken"],
                "refresh_token": result.get("refreshToken", ""),
                "expires_in": result.get("expiresIn", 3600),
            }
        except RuntimeError as e:
            msg = str(e)
            if "authorization_pending" in msg:
                time.sleep(interval)
                continue
            if "slow_down" in msg:
                interval += 5
                time.sleep(interval)
                continue
            raise
    raise TimeoutError("OIDC authorization timed out")


def _oidc_login() -> str | None:
    """Run the OIDC device flow interactively. Returns refresh_token or None."""
    try:
        client_id, client_secret = _oidc_register_client()
        auth = _oidc_start_device_auth(client_id, client_secret)

        print(
            f"\n  ╔══════════════════════════════════════════════╗\n"
            f"  ║  Kiro — AWS Builder ID login               ║\n"
            f"  ╠══════════════════════════════════════════════╣\n"
            f"  ║                                            ║\n"
            f"  ║  1. Open: {auth['verification_uri']}\n"
            f"  ║  2. Enter code: {auth['user_code']}\n"
            f"  ║                                            ║\n"
            f"  ║  Waiting for authorization...              ║\n"
            f"  ╚══════════════════════════════════════════════╝\n",
            flush=True,
        )

        token = _oidc_poll_for_token(
            client_id, client_secret,
            auth["device_code"], auth["interval"],
        )
        if token.get("refresh_token"):
            logger.info("Kiro: OIDC login successful")
            return token["refresh_token"]
        return None

    except Exception as e:
        logger.warning("Kiro: OIDC login failed: %s", e)
        print(f"\n  Kiro OIDC login failed: {e}\n", flush=True)
        return None


# ── Gateway .env management ───────────────────────────────────────────────

def _setup_gateway_env() -> bool:
    """Ensure gateway .env has REFRESH_TOKEN. Returns True if configured.

    Priority: credentials.json (rotated) → kiro-cli SQLite (social/pro) →
    OIDC device flow (builder id / free tier).
    """
    env_path = _GATEWAY_DIR / ".env"

    # Check if credentials.json has a rotated token that differs from .env
    creds_token = _extract_refresh_token_from_creds_json()
    if creds_token and env_path.exists():
        content = env_path.read_text()
        if f'REFRESH_TOKEN="{creds_token}"' not in content:
            import re
            content = re.sub(
                r'REFRESH_TOKEN="[^"]*"',
                f'REFRESH_TOKEN="{creds_token}"',
                content,
            )
            env_path.write_text(content)
            logger.info("Kiro: synced rotated token from credentials.json to .env")

    if env_path.exists():
        content = env_path.read_text()
        if "REFRESH_TOKEN" in content:
            parts = content.split('REFRESH_TOKEN="')
            if len(parts) > 1 and len(parts[1].split('"')[0]) > 10:
                return True

    token = _extract_refresh_token()
    if not token:
        # Try OIDC device flow as fallback
        print(
            "\n  Kiro: no existing credentials found.\n"
            "  Trying AWS Builder ID login (free tier)...\n",
            flush=True,
        )
        token = _oidc_login()

    if not token:
        return False

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        f'# Kiro Gateway — auto-configured by hermes-kiro plugin\n'
        f'PROXY_API_KEY="{_PROXY_KEY}"\n'
        f'REFRESH_TOKEN="{token}"\n'
        f'KIRO_API_REGION="us-east-1"\n'
        f'ACCOUNT_SYSTEM=true\n'
        f'DEBUG_MODE=errors\n'
        f'TRUNCATION_RECOVERY=true\n'
    )
    logger.info("Kiro: gateway .env configured")
    return True


def _gateway_healthy() -> bool:
    """Check if the gateway responds on /v1/models."""
    try:
        req = urllib.request.Request(
            f"http://localhost:{_GATEWAY_PORT}/v1/models",
            headers={"Authorization": f"Bearer {_PROXY_KEY}"},
        )
        urllib.request.urlopen(req, timeout=2.0)
        return True
    except Exception:
        return False


def _auth_healthy() -> bool:
    """Check if the gateway's kiro auth is working (models returned)."""
    try:
        req = urllib.request.Request(
            f"http://localhost:{_GATEWAY_PORT}/v1/models",
            headers={"Authorization": f"Bearer {_PROXY_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read())
            models = data.get("data", [])
            return len(models) > 0
    except Exception:
        return False


def _clear_stale_tokens() -> None:
    """Remove consumed/expired tokens so re-login can proceed."""
    env_path = _GATEWAY_DIR / ".env"
    if env_path.exists():
        import re
        content = env_path.read_text()
        content = re.sub(r'REFRESH_TOKEN="[^"]*"', 'REFRESH_TOKEN=""', content)
        env_path.write_text(content)
        logger.info("Kiro: cleared stale REFRESH_TOKEN from .env")

    if _CREDS_JSON.exists():
        _CREDS_JSON.unlink()
        logger.info("Kiro: removed stale credentials.json")


def _restart_gateway() -> bool:
    """Kill and restart the gateway process."""
    pid_file = _PID_FILE
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # check if alive
            os.kill(pid, 15)  # SIGTERM
            time.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, 9)  # SIGKILL
            except OSError:
                pass
        except (OSError, ValueError):
            pass
        pid_file.unlink(missing_ok=True)

    # Free the port
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1)
        if s.connect_ex(("127.0.0.1", _GATEWAY_PORT)) == 0:
            s.close()
            subprocess.run(["fuser", "-k", f"{_GATEWAY_PORT}/tcp"],
                         capture_output=True, timeout=5)
            time.sleep(1)
    finally:
        s.close()

    return _start_gateway()


def _recover_auth() -> bool:
    """Attempt to recover from auth failure. Returns True if recovery succeeded.

    Recovery order:
    1. Re-extract from kiro-cli SQLite (user may have re-logged in)
    2. OIDC device flow (no interaction needed from plugin side)
    3. Prompt user for manual re-login

    Clears stale tokens before attempting recovery so the gateway picks
    up fresh credentials on restart.
    """
    _clear_stale_tokens()

    # Try 1: kiro-cli SQLite (user re-logged in while we were broken)
    token = _extract_refresh_token()
    if token:
        logger.info("Kiro: found fresh token in kiro-cli SQLite")
        _setup_gateway_env()
        return _restart_gateway()

    # Try 2: OIDC device flow
    print(
        "\n  Kiro session expired. Attempting automatic recovery...\n"
        "  (AWS Builder ID — free tier models)\n",
        flush=True,
    )
    token = _oidc_login()
    if token:
        _setup_gateway_env()
        if _restart_gateway():
            print("  Recovery successful. Models should be available.\n", flush=True)
            return True

    # Try 3: nothing worked — tell the user what to do
    print(
        "\n  ╔══════════════════════════════════════════════════╗\n"
        "  ║  Kiro session expired — re-login required      ║\n"
        "  ╠══════════════════════════════════════════════════╣\n"
        "  ║                                              ║\n"
        "  ║  For Pro (Opus models):                      ║\n"
        "  ║    kiro-cli login --use-device-flow          ║\n"
        "  ║    (pick Google or GitHub in the browser)    ║\n"
        "  ║                                              ║\n"
        "  ║  For Free tier:                              ║\n"
        "  ║    Restart Hermes and select Kiro again.     ║\n"
        "  ║    The OIDC device flow will start.          ║\n"
        "  ║                                              ║\n"
        "  ║  After login: restart Hermes or re-select    ║\n"
        "  ║  Kiro in /model to reconnect.               ║\n"
        "  ╚══════════════════════════════════════════════════╝\n",
        flush=True,
    )
    return False


def _gateway_installed() -> bool:
    """Check if kiro-gateway is cloned."""
    return (_GATEWAY_DIR / "main.py").exists()


def _clone_gateway() -> bool:
    """Clone kiro-gateway if not already installed. Returns True on success."""
    if _gateway_installed():
        return True

    with _GATEWAY_CLONE_LOCK:
        if _gateway_installed():
            return True
        try:
            logger.info("Kiro: cloning kiro-gateway...")
            subprocess.run(
                [
                    "git", "clone",
                    "https://github.com/jwadow/kiro-gateway.git",
                    str(_GATEWAY_DIR),
                ],
                capture_output=True,
                timeout=60,
                check=True,
            )
            logger.info("Kiro: gateway cloned to %s", _GATEWAY_DIR)
            return True
        except Exception as e:
            logger.warning("Kiro: failed to clone gateway: %s", e)
            return False


def _start_gateway() -> bool:
    """Start gateway synchronously. Returns True if running after call."""
    if _gateway_healthy():
        return True

    if not _gateway_installed():
        return False

    _setup_gateway_env()

    env_path = _GATEWAY_DIR / ".env"
    if not env_path.exists():
        return False

    try:
        log_path = _PID_FILE.parent / "gateway.log"
        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.Popen(
            ["python3", "main.py"],
            cwd=str(_GATEWAY_DIR),
            stdout=open(str(log_path), "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _PID_FILE.write_text(str(proc.pid))

        # Wait for gateway to be ready (up to 10s)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if _gateway_healthy():
                logger.info("Kiro: gateway started (PID %d)", proc.pid)
                return True
            time.sleep(0.5)

        logger.warning("Kiro: gateway started but not healthy within timeout")
        return False
    except Exception as e:
        logger.warning("Kiro: failed to start gateway: %s", e)
        return False


def _is_kiro_cli_installed() -> bool:
    """Check if kiro-cli is available."""
    for candidate in (
        Path.home() / ".local" / "bin" / "kiro-cli",
        Path("/usr/local/bin/kiro-cli"),
    ):
        if candidate.exists():
            return True
    return False


# ── Thinking mode ─────────────────────────────────────────────────────────

_THINKING_MODELS = {
    "claude-opus-4.7",
    "claude-opus-4.6",
    "claude-opus-4.5",
    "claude-sonnet-4.6",
    "claude-sonnet-4.5",
    "claude-haiku-4.5",
    "claude-sonnet-4",
    "claude-3.7-sonnet",
}


def _add_thinking_variants(models: list[str]) -> list[str]:
    """Append -thinking variants for Claude models that support it."""
    extended = list(models)
    for m in models:
        base = m.removesuffix("-thinking")
        if base in _THINKING_MODELS and f"{base}-thinking" not in extended:
            extended.append(f"{base}-thinking")
    return extended


# ── Provider profile ─────────────────────────────────────────────────────

class KiroProfile(ProviderProfile):
    """Kiro provider with lazy gateway setup in fetch_models."""

    default_max_tokens: int | None = 8192

    def build_api_kwargs_extras(
        self,
        *,
        reasoning_config: dict | None = None,
        supports_reasoning: bool = False,
        **context,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Pass reasoning config through to the gateway.

        If the model name ends with -thinking, extended thinking is
        automatically enabled with a default budget of 4096 tokens.
        Explicit reasoning_config overrides default thinking settings.
        """
        extra_body: dict[str, Any] = {}

        model = context.get("model", "")
        if model and model.endswith("-thinking"):
            # Default thinking config when using -thinking suffix
            if reasoning_config is None:
                reasoning_config = {"enabled": True, "budget_tokens": 4096}
            supports_reasoning = True

        if supports_reasoning and reasoning_config is not None:
            rc = dict(reasoning_config)
            if rc.get("enabled") is not False:
                extra_body["reasoning"] = rc
        return extra_body, {}

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> list[str] | None:
        """List models from the gateway, auto-setting up if needed.

        This is called by Hermes when the user picks Kiro in /model.
        We use it as a natural integration point for lazy setup and
        auth recovery.
        """
        # Step 1: clone gateway if missing
        if not _gateway_installed():
            logger.info("Kiro: gateway not installed, cloning...")
            if not _clone_gateway():
                return None

        # Step 2: configure auth
        if not _setup_gateway_env():
            print(
                "\n  Kiro setup incomplete. Options:\n"
                "    Pro (Opus models):  kiro-cli login --use-device-flow\n"
                "    Free (Sonnet/Haiku): select Kiro again to start OIDC login\n",
                flush=True,
            )
            return None

        # Step 3: start gateway if needed
        if not _gateway_healthy():
            logger.info("Kiro: gateway not running, starting...")
            if not _start_gateway():
                return None

        # Step 4: auth health check + auto-recovery
        if not _auth_healthy():
            logger.warning("Kiro: auth unhealthy, attempting recovery...")
            if not _recover_auth():
                return None  # recovery failed, fallback_models shown

        # Step 5: fetch from gateway
        models = super().fetch_models(api_key=_PROXY_KEY, timeout=timeout)
        if not models:
            # Double-check: maybe auth broke between health check and fetch
            if not _auth_healthy():
                logger.warning("Kiro: auth broke during fetch, retrying recovery...")
                if not _recover_auth():
                    return None
                models = super().fetch_models(api_key=_PROXY_KEY, timeout=timeout)

        if models:
            models = _add_thinking_variants(models)
        return models


# ── Provider profile ─────────────────────────────────────────────────────

kiro = KiroProfile(
    name="kiro",
    aliases=("kiro-pro",),
    env_vars=("KIRO_PROXY_API_KEY",),
    display_name="Kiro",
    description=(
        "Kiro — Claude Opus, Sonnet, Haiku (Pro + free tier)"
    ),
    signup_url="https://kiro.dev",
    base_url=_GATEWAY_URL,
    fallback_models=(
        "claude-opus-4.7",
        "claude-opus-4.6",
        "claude-opus-4.5",
        "claude-sonnet-4.6",
        "claude-sonnet-4.5",
        "claude-haiku-4.5",
    ),
    auth_type="api_key",
)

register_provider(kiro)

# ── Pre-warm: ensure proxy key is available (prevents API key prompt) ─────
if not os.environ.get("KIRO_PROXY_API_KEY"):
    os.environ["KIRO_PROXY_API_KEY"] = _PROXY_KEY

_ENV_PATH = Path.home() / ".hermes" / ".env"
try:
    if _ENV_PATH.exists():
        content = _ENV_PATH.read_text()
        if "KIRO_PROXY_API_KEY" not in content:
            _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_ENV_PATH, "a") as f:
                f.write(f"\nKIRO_PROXY_API_KEY={_PROXY_KEY}\n")
            logger.info("Kiro: added KIRO_PROXY_API_KEY to .env")
except Exception:
    pass

# ── Pre-warm: attempt setup at import time (non-blocking) ─────────────────
if _gateway_installed():
    if _setup_gateway_env():
        threading.Thread(target=_start_gateway, daemon=True).start()
    elif not _gateway_healthy() and _KIRO_CLI_DB.exists():
        pass
    elif not _KIRO_CLI_DB.exists() and not _is_kiro_cli_installed():
        # No kiro-cli — OIDC will be offered in fetch_models
        pass
