#!/usr/bin/env bash
# Render build script — runs during deploy
set -o errexit

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🗄️  Running database migrations..."
python -m alembic upgrade head

echo "✅ Build complete!"
