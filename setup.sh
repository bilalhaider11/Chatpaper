#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo ""
echo "=== Chatpaper Setup ==="
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────

echo "[1/7] Creating Python virtual environment..."
cd "$BACKEND_DIR"
python3 -m venv venv

echo "[2/7] Installing backend dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "[3/7] Setting up .env file..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    cat > "$BACKEND_DIR/.env" <<EOF
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
DATABASE=postgresql://postgres:postgres@localhost:5432/chatbot
ACCESS_TOKEN_EXPIRE_MINUTES=600
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PASSWORD
EOF
    echo "      .env created."
else
    echo "      .env already exists — skipped."
fi

echo "[4/7] Creating database..."
python3 scripts/create_db.py

echo "[5/7] Running database migrations..."
alembic upgrade head

echo "[6/7] Seeding admin user..."
python3 scripts/seed.py

deactivate

# ── Frontend ──────────────────────────────────────────────────────────────────

echo "[7/7] Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --silent

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "=== Setup complete! ==="
echo ""
if [ -n "${ADMIN_PASSWORD:-}" ]; then
    echo "Admin credentials (saved to backend/.env):"
    echo "  Username : admin"
    echo "  Password : $ADMIN_PASSWORD"
    echo ""
fi
echo "To start the backend:"
echo "  cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo ""
echo "To start the frontend (in a separate terminal):"
echo "  cd frontend && npm run dev"
echo ""