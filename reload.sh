#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🔄 Stopping existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 2

echo "🚀 Starting backend (port 8000)..."
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
nohup uvicorn main:app --reload --port 8000 > /tmp/coldbrew-backend.log 2>&1 &
BACKEND_PID=$!

echo "🚀 Starting frontend (port 3000)..."
cd "$SCRIPT_DIR/frontend"
nohup NEXT_PUBLIC_API_URL=http://localhost:8000 npx next dev -p 3000 > /tmp/coldbrew-frontend.log 2>&1 &
FRONTEND_PID=$!

echo "⏳ Waiting for services..."
for i in $(seq 1 15); do
  BACKEND_UP=$(curl -s --max-time 2 http://localhost:8000/api/health 2>/dev/null && echo "yes" || echo "no")
  FRONTEND_UP=$(curl -s --max-time 2 -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null || echo "000")

  if [ "$BACKEND_UP" != "no" ] && [ "$FRONTEND_UP" != "000" ]; then
    echo ""
    echo "✅ Backend:  http://localhost:8000  (PID $BACKEND_PID)"
    echo "✅ Frontend: http://localhost:3000  (PID $FRONTEND_PID)"
    exit 0
  fi
  printf "."
  sleep 1
done

echo ""
echo "⚠️  Timed out after 15s. Check logs:"
echo "   Backend:  /tmp/coldbrew-backend.log"
echo "   Frontend: /tmp/coldbrew-frontend.log"
exit 1
