# Hermes Kiro Plugin

Native model-provider plugin for Kiro — Claude Opus 4.7, Sonnet 4.6, DeepSeek 3.2, and more. Appears directly in `hermes model`. No Docker required.

Two auth paths:
- **Pro ($20/mo):** kiro-cli social login (Google/GitHub) → Opus models
- **Free:** OIDC device flow (AWS Builder ID) → Sonnet, Haiku, DeepSeek, Qwen

Built on [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway), the first project to bridge Kiro's models into Hermes. This plugin takes that concept native — no containers, no manual `hermes config set` commands. Select Kiro from the model picker and the gateway starts automatically.

OIDC device flow inspired by [Quorinex/Kiro-Go](https://github.com/Quorinex/Kiro-Go).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash
```

## Setup

### Pro (Opus models)

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli login --use-device-flow     # pick Google or GitHub
hermes model                         # select Kiro → pick a model
```

### Free tier (no kiro-cli needed)

```
hermes model → Kiro
```

The plugin auto-detects that no credentials exist and initiates an OIDC device flow:
1. Prints a URL and code
2. Visit the URL, enter the code
3. Plugin polls for completion
4. Gateway auto-starts

## Thinking mode

Append `-thinking` to any Claude model:

```
claude-opus-4.7-thinking
claude-sonnet-4.5-thinking
claude-haiku-4.5-thinking
```

Enables extended thinking with a default budget of 4096 tokens.

## Models

claude-opus-4.7   claude-sonnet-4.6   claude-sonnet-4.5   claude-haiku-4.5
claude-opus-4.6   claude-sonnet-4     claude-3.7-sonnet    qwen3-coder-next
claude-opus-4.5   deepseek-3.2        glm-5                minimax-m2.5 / m2.1

## Architecture

```
kiro-cli / OIDC  →  kiro-gateway (:8000)  →  Hermes (provider: kiro)
     ↑                                              ↑
  auth token                              OpenAI-compatible HTTP
```

## Credits

- [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway) — first to connect Kiro to Hermes
- [Quorinex/Kiro-Go](https://github.com/Quorinex/Kiro-Go) — OIDC device flow, thinking mode convention
- [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway) — underlying proxy

## Troubleshooting

**Empty model list:** Run `kiro-cli login --use-device-flow` (Pro) or select Kiro again to trigger OIDC login (free).

**Gateway crash / 401:** Token stale. Re-login.

**No Opus models on free tier:** Builder ID only serves Sonnet/Haiku/DeepSeek/Qwen. Pro subscription needed for Opus.
