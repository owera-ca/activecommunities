#!/bin/bash
set -e

echo "============================================"
echo "  Active Communities Monitor - Deployment"
echo "============================================"

APP_DIR="/var/www/activecommunities"
SERVICE_NAME="activecommunities"

# Navigate to project directory
cd "$APP_DIR"

# Pull the latest version
echo "⬇  Pulling latest code from main..."
git reset --hard HEAD
git clean -fd
git pull origin main

# Activate virtual environment (create if missing)
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install / update Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Install Playwright browser binaries
echo "🎭 Installing Playwright Chromium..."
playwright install chromium
playwright install-deps chromium

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
    echo "   source venv/bin/activate && python register.py --headless"
fi

echo ""
echo "✅ Deployment finished!"
