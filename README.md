# Chatpaper

A full-stack AI-powered chatbot application for interacting with papers and documents. Built with a FastAPI backend and a React + TypeScript frontend.

## Project Structure

```
Chatpaper/
├── backend/          # FastAPI Python backend
└── frontend/
    └── chatbot_ui/   # React + TypeScript + Vite frontend
```

## Tech Stack

**Backend**
- Python 3.11+
- FastAPI 0.109
- SQLAlchemy 2.0 + Alembic (migrations)
- JWT Authentication (python-jose + passlib)
- SQLAdmin dashboard
- Uvicorn (ASGI server)

**Frontend**
- React 19 + TypeScript
- Vite
- Redux Toolkit
- React Router DOM
- Tailwind CSS
- Axios

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm or yarn

---

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd Chatpaper
```

### 2. Run the setup script

```bash
bash setup.sh
```

This single command will:
- Create a Python virtual environment and install backend dependencies
- Generate a `backend/.env` file with a secure `SECRET_KEY` (skipped if one already exists)
- Run database migrations (`alembic upgrade head`)
- Install frontend npm dependencies

Then start both servers as shown at the end of the script output.

---

### Manual Setup (alternative)

#### Backend Setup

```bash
cd backend
```

**Create and activate a virtual environment:**

```bash
python -m venv venv

# On Linux/macOS
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Create a `.env` file in the `backend/` directory:**

```env
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
DATABASE=sqlite:///./chatpaper.db
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

> For `SECRET_KEY`, generate a secure key with: `python -c "import secrets; print(secrets.token_hex(32))"`

**Run database migrations:**

```bash
alembic upgrade head
```

**Start the backend server:**

```bash
uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`.
API docs are available at `http://localhost:8000/docs`.
Admin panel is available at `http://localhost:8000/admin`.

---

### 3. Frontend Setup

Open a new terminal tab/window:

```bash
cd frontend
```

**Install dependencies:**

```bash
npm install
```

**Start the development server:**

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## Running Both Simultaneously

You need two terminal sessions running at the same time:

| Terminal | Command | URL |
|----------|---------|-----|
| Backend | `cd backend && uvicorn main:app --reload` | http://localhost:8000 |
| Frontend | `cd frontend && npm run dev` | http://localhost:5173 |

---

## API Overview

| Method | Route | Description | Access |
|--------|-------|-------------|--------|
| POST | `/api/auth/token` | Login (get JWT token) | Public |
| POST | `/api/auth/users/` | Register new user | Public |
| GET | `/api/auth/users/me/` | Get current user | Authorized |
| GET | `/api/auth/users/` | List all users | Admin |
| POST | `/api/conversation/inconversationlist` | Create conversation list | Authorized |
| GET | `/` | Health check | Public |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | Required |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `DATABASE` | SQLAlchemy database URL | Required |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry time | `30` |
