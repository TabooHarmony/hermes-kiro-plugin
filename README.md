# Hermes Kiro Plugin

<img width="212" height="212" alt="image" src="https://github.com/user-attachments/assets/a39f48fe-f1b7-46b8-a997-c583658cb0e0" />


Native model-provider plugin for **paid** Kiro plans, bringing various models, includuding Opus and Sonnet, through your existing Kiro subscription. Appears directly in the `hermes model` picker
Built on [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway) to bridge Kiro's models into Hermes. This project implements this into user-friendly plugin. 
Select Kiro from the model picker and the gateway starts automatically.

## Install

Inside your Hermes envioroment, run:
```bash
curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash
```

## Setup

Login once via kiro-cli (pick Google or GitHub):

```bash
curl -fsSL https://cli.kiro.dev/install | bash
kiro-cli login --use-device-flow
```

After that, select Kiro from `hermes model` and everything configures itself:

```
hermes model
  kiro → claude-opus-4.6
```

The plugin will automatically:
- Clones kiro-gateway
- Extracts your refresh token from kiro-cli's local session
- Starts the gateway on localhost:8000
- Registers all available models

## Architecture

```
kiro-cli (auth)  →  kiro-gateway (:8000)  →  Hermes (provider: kiro)
     ↑                                              ↑
  OAuth token                              OpenAI-compatible HTTP
```

The gateway is [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway), a FastAPI proxy that translates OpenAI chat completions into Kiro's AWS CodeWhisperer protocol.

## Credits

- [EMRD95/Kiro-Hermes-Gateway](https://github.com/EMRD95/Kiro-Hermes-Gateway): first to connect Kiro models to Hermes, helped me troubleshoot.
- [jwadow/kiro-gateway](https://github.com/jwadow/kiro-gateway): the underlying gateway proxy.
- [NousResearch](https://github.com/NousResearch/hermes-agent): the agent runtime this plugin extends.
