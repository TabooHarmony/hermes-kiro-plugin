# Hermes Kiro Plugin

Native model-provider plugin for Kiro Pro — Claude Opus 4.7, Sonnet 4.6, DeepSeek 3.2, and more through your existing Kiro subscription. Appears directly in the `hermes model` picker. No Docker required.

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

## First-time setup

Login once via kiro-cli (pick Google or GitHub):

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli login --use-device-flow
```

After that, select Kiro from `hermes model` and everything configures itself:

```
hermes model
  kiro → claude-opus-4.7
```

The plugin automatically:
- Clones kiro-gateway
- Extracts your refresh token from kiro-cli's local session
- Starts the gateway on localhost:8000
- Registers all available models

## Models

Available models depend on your Kiro tier. Pro ($20/mo via Google/GitHub login) unlocks the Opus line.

**Pro tier:** claude-opus-4.7, claude-opus-4.6, claude-opus-4.5, claude-sonnet-4.6

**Free tier:** claude-sonnet-4.5, claude-sonnet-4, claude-haiku-4.5, claude-3.7-sonnet, deepseek-3.2, glm-5, minimax-m2.5, minimax-m2.1, qwen3-coder-next

## Architecture

```
kiro-cli (auth)  →  kiro-gateway (:8000)  →  Hermes (provider: kiro)
     ↑                                              ↑
  OAuth token                              OpenAI-compatible HTTP
```

The gateway is [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway) — a FastAPI proxy that translates OpenAI chat completions into Kiro's AWS CodeWhisperer protocol.

## Credits

- [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway) — first to connect Kiro models to Hermes. The Docker approach that proved the concept.
- [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway) — the underlying gateway proxy.
- [TabooHarmony](https://github.com/TabooHarmony) — native Hermes plugin packaging.
- [NousResearch](https://github.com/NousResearch/hermes-agent) — the agent runtime this plugin extends.

## Troubleshooting

**Empty model list:** Run `kiro-cli login --use-device-flow`. Must pick Google or GitHub, not Builder ID.

**No Opus models:** Requires Pro subscription via social login.

**Gateway won't start:** Token may be stale. Re-run the login command.
