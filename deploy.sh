#!/bin/bash
set -e

echo "============================================"
echo "  Active Communities Monitor - Deployment"
echo "============================================"

APP_DIR="/var/www/html/activecommunities.owera.ca"
SERVICE_NAME="activecommunities"

# Navigate to project directory
cd "$APP_DIR"

# Pull the latest version
echo "⬇  Pulling latest code from main..."
git reset --hard HEAD
git clean -fd
git pull origin main

# Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "⬇  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Sync dependencies into .venv (creates venv automatically)
echo "📦 Syncing Python dependencies with uv..."
uv sync

# Install Playwright browser binaries
echo "🎭 Installing Playwright Chromium..."
uv run playwright install chromium
uv run playwright install-deps chromium

# Ensure .env exists (do NOT overwrite if already present)
if [ ! -f ".env" ]; then
    echo "⚠  No .env found. Please create one from .env.example before the monitor can run."
fi

# Restart the systemd service (if running under systemd)
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🔄 Restarting $SERVICE_NAME service..."
    systemctl restart "$SERVICE_NAME"
    echo "✅ Service restarted."
elif [ -f "/etc/supervisor/conf.d/${SERVICE_NAME}.conf" ]; then
    echo "🔄 Reloading supervisor process..."
    supervisorctl restart "$SERVICE_NAME"
    echo "✅ Supervisor process restarted."
else
    echo "ℹ  No systemd/supervisor service found. Start manually:"
    echo "   uv run python register.py --headless"
fi

echo ""
echo "✅ Deployment finished!"
