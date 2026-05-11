# Hermes Kiro Plugin

Native model-provider plugin for Kiro Pro — Claude Opus 4.7, Sonnet 4.6, DeepSeek 3.2, and more. Appears directly in `hermes model`. No Docker required.

Requires Kiro Pro ($20/mo via Google or GitHub social login). Builder ID / free tier is not supported — we tested it and the OIDC tokens get 403'd by Kiro's API.

Built on [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway), the first project to bridge Kiro's models into Hermes. This plugin takes that concept native — no containers, no manual `hermes config set` commands. Select Kiro from the model picker and the gateway starts automatically.

## Install

One command:

```bash
curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/TabooHarmony/hermes-kiro-plugin ~/.hermes/plugins/model-providers/kiro
```

## Setup

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli login --use-device-flow     # pick Google or GitHub
hermes model                         # select Kiro → pick a model
```

The plugin auto-configures: clones kiro-gateway, extracts your refresh token, starts the proxy, registers models.

## Models

claude-opus-4.7   claude-sonnet-4.6   claude-sonnet-4.5   claude-haiku-4.5
claude-opus-4.6   claude-sonnet-4     claude-3.7-sonnet    qwen3-coder-next
claude-opus-4.5   deepseek-3.2        glm-5                minimax-m2.5 / m2.1

## Architecture

```
kiro-cli (auth)  →  kiro-gateway (:8000)  →  Hermes (provider: kiro)
     ↑                                              ↑
  OAuth token                              OpenAI-compatible HTTP
```

## Credits

- [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway) — first to connect Kiro to Hermes. Proved the concept.
- [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway) — underlying proxy.
- [TabooHarmony](https://github.com/TabooHarmony) — native plugin packaging.

## Troubleshooting

**Empty model list / connection errors:** Run `kiro-cli login --use-device-flow`. Must pick Google or GitHub.

**Gateway crash:** Token stale. Re-run login.

**Builder ID / free tier:** Not supported. Kiro's API returns 403 on OIDC tokens from Builder ID accounts.
