#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.hermes/plugins/model-providers/kiro"
REPO="https://github.com/TabooHarmony/hermes-kiro-plugin.git"

FORCE=false
if [[ "${1:-}" == "--force" ]]; then
    FORCE=true
fi

echo "  Hermes Kiro Plugin"
echo

if [ -d "$PLUGIN_DIR/.git" ]; then
    # Already installed — check version
    CURRENT=$(grep "^version:" "$PLUGIN_DIR/plugin.yaml" 2>/dev/null | awk '{print $2}' || echo "unknown")
    REMOTE_VERSION=$(curl -fsSL "https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/plugin.yaml" 2>/dev/null | grep "^version:" | awk '{print $2}' || echo "unknown")

    if [ "$FORCE" = true ]; then
        echo "Forcing reinstall..."
        rm -rf "$PLUGIN_DIR"
    elif [ "$CURRENT" != "$REMOTE_VERSION" ] && [ "$REMOTE_VERSION" != "unknown" ]; then
        echo "Update available: $CURRENT -> $REMOTE_VERSION"
        echo ""
        echo "To update:"
        echo "  curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash -s -- --force"
        echo ""
        echo "No data will be lost — only plugin files are replaced."
        exit 0
    else
        echo "Already installed (v$CURRENT)."
        echo "To reinstall: curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash -s -- --force"
        exit 0
    fi
fi

mkdir -p "$(dirname "$PLUGIN_DIR")"
git clone "$REPO" "$PLUGIN_DIR" --quiet

VERSION=$(grep "^version:" "$PLUGIN_DIR/plugin.yaml" | awk '{print $2}')
echo "Installed v$VERSION."
echo

if command -v kiro-cli &>/dev/null; then
    if kiro-cli whoami &>/dev/null; then
        echo "Auth: logged in with kiro-cli (Pro)."
        echo "Ready. Run: hermes model"
    else
        echo "Next: kiro-cli login --use-device-flow"
        echo "      (pick Google or GitHub, not Builder ID)"
    fi
else
    echo "Kiro-cli not found. Free tier via OIDC device flow will"
    echo "start automatically when you select Kiro in hermes model."
    echo ""
    echo "For Pro (Opus models), install kiro-cli first:"
    echo "  curl -fsSL https://cli.kiro.dev/install | bash"
    echo "  kiro-cli login --use-device-flow"
fi
