#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================================"
echo "  ColdBrew — Install Script"
echo "================================================"
echo ""

# --- Python backend ---
echo "📦 Setting up backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
  echo "   Creating Python virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
echo "   Installing Python dependencies..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "   Creating .env file (add your NOMADIC_SDK_API_KEY)..."
  echo "NOMADIC_SDK_API_KEY=" > .env
fi

echo "   ✅ Backend ready"
echo ""

# --- Node frontend ---
echo "📦 Setting up frontend..."
cd "$SCRIPT_DIR/frontend"

echo "   Installing Node dependencies..."
npm install --silent

echo "   ✅ Frontend ready"
echo ""

# --- Start services ---
echo "🚀 Starting services..."
bash "$SCRIPT_DIR/reload.sh"
