"""Kiro provider — Claude models via Kiro Pro subscription.

Registers Kiro as a provider in the model picker. Handles the full setup
chain automatically: gateway installation, auth extraction from kiro-cli,
gateway lifecycle. No manual steps required beyond initial kiro-cli login.

Architecture:
    kiro-cli (auth)  --→  kiro-gateway (:8000)  --→  Hermes (provider: kiro)
    social login          OpenAI-compatible            /model claude-opus-4.7

Setup (handled automatically by the provider):
    1. git clone kiro-gateway (auto)
    2. kiro-cli login --use-device-flow → browser OAuth (user does once)
    3. Plugin extracts token, configures .env, starts gateway (auto)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import threading
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


def _extract_refresh_token() -> str | None:
    """Extract refresh token from kiro-cli SQLite database.

    Prioritizes social login (Google/GitHub) over OIDC (Builder ID).
    Social tokens work for the full model lineup including Opus 4.7.
    """
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
                    logger.debug("Kiro: extracted refresh token from %s", key)
                    return rt
        db.close()
    except Exception as e:
        logger.debug("Kiro: failed to read SQLite: %s", e)
    return None


def _setup_gateway_env() -> bool:
    """Ensure gateway .env has REFRESH_TOKEN. Returns True if configured."""
    env_path = _GATEWAY_DIR / ".env"

    if env_path.exists():
        content = env_path.read_text()
        if "REFRESH_TOKEN" in content:
            parts = content.split('REFRESH_TOKEN="')
            if len(parts) > 1 and len(parts[1].split('"')[0]) > 10:
                return True

    token = _extract_refresh_token()
    if not token:
        return False

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        f'# Kiro Gateway — auto-configured by hermes-kiro plugin\n'
        f'PROXY_API_KEY="{_PROXY_KEY}"\n'
        f'REFRESH_TOKEN="{token}"\n'
        f'KIRO_API_REGION="us-east-1"\n'
        f'DEBUG_MODE=errors\n'
        f'TRUNCATION_RECOVERY=true\n'
    )
    logger.info("Kiro: gateway .env configured from kiro-cli session")
    return True


def _gateway_healthy() -> bool:
    """Check if the gateway responds on /v1/models."""
    import urllib.request

    try:
        req = urllib.request.Request(
            f"http://localhost:{_GATEWAY_PORT}/v1/models",
            headers={"Authorization": f"Bearer {_PROXY_KEY}"},
        )
        urllib.request.urlopen(req, timeout=2.0)
        return True
    except Exception:
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
        import time
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

        Kiro's Claude models (Opus 4.5+, Sonnet 4.5+, Haiku 4.5+) support
        extended thinking. The gateway translates reasoning config into the
        internal Kiro thinking format.
        """
        extra_body = {}
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
        We use it as a natural integration point for lazy setup.
        """
        # Step 1: clone gateway if missing
        if not _gateway_installed():
            logger.info("Kiro: gateway not installed, cloning...")
            if not _clone_gateway():
                return None  # fallback_models shown in picker

        # Step 2: configure auth from kiro-cli if available
        if not _setup_gateway_env():
            print(
                "\n  Kiro requires a one-time login. Run:\n"
                "    kiro-cli login --use-device-flow\n"
                "  Then pick Google or GitHub in the browser.\n"
                "  After login, select Kiro again in /model.\n",
                flush=True,
            )
            return None

        # Step 3: start gateway if needed
        if not _gateway_healthy():
            logger.info("Kiro: gateway not running, starting...")
            if not _start_gateway():
                return None

        # Step 4: fetch from gateway
        return super().fetch_models(api_key=_PROXY_KEY, timeout=timeout)


# ── Provider profile ─────────────────────────────────────────────────────

kiro = KiroProfile(
    name="kiro",
    aliases=("kiro-pro",),
    env_vars=("KIRO_PROXY_API_KEY",),  # gateway proxy key (auto-configured)
    display_name="Kiro",
    description=(
        "Kiro Pro (Claude, MiniMax, GLM — OAuth login)"
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
# Force-set in current process env — must override empty string from .env
if not os.environ.get("KIRO_PROXY_API_KEY"):
    os.environ["KIRO_PROXY_API_KEY"] = _PROXY_KEY

# Ensure persistence in .env for future restarts
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
    pass  # OS/env issue — non-critical

# ── Pre-warm: attempt setup at import time (non-blocking) ─────────────────
if _gateway_installed():
    if _setup_gateway_env():
        threading.Thread(target=_start_gateway, daemon=True).start()
    elif not _gateway_healthy() and _KIRO_CLI_DB.exists():
        # Kiro-cli exists but no token — user needs to login
        pass  # quiet — fetch_models will print instructions when called
    elif not _KIRO_CLI_DB.exists() and not _is_kiro_cli_installed():
        print(
            "\n  Kiro provider loaded but kiro-cli is not installed.\n"
            "  Install: curl -fsSL https://cli.kiro.dev/install | bash\n"
            "  Then: kiro-cli login --use-device-flow\n",
            flush=True,
        )
