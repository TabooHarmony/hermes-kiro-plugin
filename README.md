# Hermes Kiro Plugin

Native Kiro provider for [Hermes Agent](https://github.com/NousResearch/hermes-agent).  
Claude Opus 4.7, Sonnet 4.6, DeepSeek 3.2, and more via your Kiro Pro subscription.

## How it works

```
kiro-cli (auth)  --→  kiro-gateway (:8000)  --→  Hermes
social login          OpenAI-compatible API       /model claude-opus-4.7
```

The plugin handles everything automatically:
- Clones [kiro-gateway](https://github.com/jwadow/kiro-gateway) on first use
- Extracts your refresh token from kiro-cli's local session
- Auto-starts the gateway when you select Kiro in Hermes

## Setup

### 1. Install

```bash
# Standard Hermes plugin — drop it in
mkdir -p ~/.hermes/plugins/model-providers/kiro
# Copy plugin.yaml and __init__.py to that directory
```

Or if packaged for the skills hub:
```bash
hermes skills install kiro-gateway
```

### 2. Login to Kiro (one time)

```bash
kiro-cli login --use-device-flow
# Open the URL, pick Google or GitHub (NOT Builder ID)
```

Kiro-cli can be installed with:
```bash
curl -fsSL https://cli.kiro.dev/install | bash
```

### 3. Select Kiro in Hermes

```bash
hermes model
# Select "Kiro" from the provider list
# Base URL: hit Enter (default: http://localhost:8000/v1)
# Pick a model — Opus 4.7, Sonnet 4.6, etc.
```

The gateway auto-starts and models are fetched live.

## Available Models

| Model | Tier | Notes |
|---|---|---|
| claude-opus-4.7 | Pro | Flagship reasoning |
| claude-opus-4.6 | Pro | |
| claude-opus-4.5 | Pro | |
| claude-sonnet-4.6 | Pro | |
| claude-sonnet-4.5 | Free+Pro | |
| claude-haiku-4.5 | Free+Pro | Fast/cheap |
| claude-sonnet-4 | Free+Pro | |
| claude-3.7-sonnet | Free+Pro | |
| deepseek-3.2 | Free+Pro | |
| glm-5 | Free+Pro | |
| minimax-m2.5 | Free+Pro | |
| minimax-m2.1 | Free+Pro | |
| qwen3-coder-next | Free+Pro | |

Free tier: Builder ID. Pro tier: Google/GitHub social login ($20/mo).

## Troubleshooting

**"Kiro requires a one-time login" message:**  
Run `kiro-cli login --use-device-flow` and pick Google or GitHub.

**403 errors or no models:**  
Your login used Builder ID. Re-login with Google or GitHub (social login, not Builder ID).

**"No API key configured" prompt:**  
The plugin auto-sets the proxy key. Select Kiro again or restart Hermes.

**Gateway crash:**  
The refresh token may be stale. Re-run `kiro-cli login --use-device-flow`.

**No Opus 4.7:**  
Requires Pro subscription via Google or GitHub social login.

## Architecture

- **`__init__.py`** — ProviderProfile subclass with `fetch_models` hook for lazy setup
- **`plugin.yaml`** — kind: model-provider metadata
- **Gateway** — [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway) v2.4-dev.10, cloned to `~/.kiro-gateway`
- **Auth** — Refresh token extracted from kiro-cli SQLite (`kirocli:social:token`), persisted in gateway `.env`

## License

MIT
