# Hermes Kiro Plugin

Claude Opus 4.7, Sonnet 4.6, DeepSeek 3.2, and more via your Kiro Pro subscription.

## Setup

### 1. One-time login

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli login --use-device-flow
```

Open the URL it prints. Pick **Google** or **GitHub** — not Builder ID.

### 2. Install the plugin

```bash
mkdir -p ~/.hermes/plugins/model-providers/kiro
cp __init__.py plugin.yaml ~/.hermes/plugins/model-providers/kiro/
```

### 3. Select Kiro

```bash
hermes model
# pick Kiro → pick a model
```

The gateway auto-clones, configures, and starts on first use.

## Models

| Model | Tier |
|---|---|
| claude-opus-4.7 | Pro |
| claude-opus-4.6 | Pro |
| claude-opus-4.5 | Pro |
| claude-sonnet-4.6 | Pro |
| claude-sonnet-4.5 | Free+Pro |
| claude-haiku-4.5 | Free+Pro |
| claude-sonnet-4 | Free+Pro |
| claude-3.7-sonnet | Free+Pro |
| deepseek-3.2 | Free+Pro |
| glm-5 | Free+Pro |
| minimax-m2.5 | Free+Pro |
| minimax-m2.1 | Free+Pro |
| qwen3-coder-next | Free+Pro |

Pro requires Google or GitHub social login ($20/mo). Builder ID = Free tier only.

## How it works

```
kiro-cli --→ kiro-gateway (:8000/v1) --→ Hermes
```

The plugin auto-clones [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway), extracts your refresh token from kiro-cli's local session, and starts the gateway when you select Kiro.

## Troubleshooting

**Empty model list or connection errors:** Run `kiro-cli login --use-device-flow` first. Pick Google or GitHub, not Builder ID.

**No Opus models:** Requires Pro subscription via social login.

**Gateway crash:** Token stale. Re-run the login command.
