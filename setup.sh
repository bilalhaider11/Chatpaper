#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo ""
echo "=== Chatpaper Setup ==="
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────

echo "[1/5] Creating Python virtual environment..."
cd "$BACKEND_DIR"
python3 -m venv venv

echo "[2/5] Installing backend dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[3/5] Setting up .env file..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$BACKEND_DIR/.env" <<EOF
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
DATABASE=sqlite:///./chatpaper.db
ACCESS_TOKEN_EXPIRE_MINUTES=30
EOF
    echo "      .env created with a generated SECRET_KEY."
else
    echo "      .env already exists — skipped."
fi

echo "[4/5] Running database migrations..."
alembic upgrade head

deactivate

# ── Frontend ──────────────────────────────────────────────────────────────────

echo "[5/5] Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the backend:"
echo "  cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo ""
echo "To start the frontend (in a separate terminal):"
echo "  cd frontend && npm run dev"
echo ""
