#!/bin/bash
# Hermes Kiro Plugin — one-line installer
set -e

PLUGIN_DIR="$HOME/.hermes/plugins/model-providers/kiro"

if [ -d "$PLUGIN_DIR" ]; then
    echo "Kiro plugin already installed at $PLUGIN_DIR"
    echo "To reinstall: rm -rf $PLUGIN_DIR && curl -fsSL https://raw.githubusercontent.com/TabooHarmony/hermes-kiro-plugin/master/install.sh | bash"
    exit 0
fi

echo "Installing Hermes Kiro plugin..."
git clone https://github.com/TabooHarmony/hermes-kiro-plugin.git "$PLUGIN_DIR" --quiet
echo "Done. Plugin installed at $PLUGIN_DIR"
echo ""
echo "Next steps:"
echo "  1. Install kiro-cli:  curl -fsSL https://cli.kiro.dev/install | bash"
echo "  2. Login:             kiro-cli login --use-device-flow"
echo "  3. Select Kiro:       hermes model  →  Kiro  →  pick a model"
