#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="$HOME/.hermes/plugins/model-providers/kiro"
REPO="https://github.com/TabooHarmony/hermes-kiro-plugin.git"

echo "  Hermes Kiro Plugin"
echo

if [ -d "$PLUGIN_DIR" ]; then
    echo "Already installed at $PLUGIN_DIR"
    echo "To reinstall: rm -rf $PLUGIN_DIR && curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash"
    exit 0
fi

mkdir -p "$(dirname "$PLUGIN_DIR")"
git clone "$REPO" "$PLUGIN_DIR" --quiet

echo "Installed."
echo

if command -v kiro-cli &>/dev/null; then
    if kiro-cli whoami &>/dev/null; then
        echo "Auth: logged in."
        echo "Ready. Run: hermes model"
    else
        echo "Next: kiro-cli login --use-device-flow"
    fi
else
    echo "Next steps:"
    echo "  1. curl -fsSL https://cli.kiro.dev/install | bash"
    echo "  2. kiro-cli login --use-device-flow"
    echo "  3. hermes model"
fi
