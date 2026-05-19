# Chatpaper — Backend

FastAPI backend for the Chatpaper application. Handles authentication, file uploads, and conversation management.

## Tech Stack

- **Language:** Python 3.11+
- **Framework:** FastAPI 0.109
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Auth:** JWT via python-jose + passlib
- **Admin:** SQLAdmin
- **Server:** Uvicorn

## Project Structure

```
backend/
├── api/
│   └── routers/
│       ├── auth/         # Auth routes (login, register, user management)
│       ├── file_handling/ # File upload/download routes
│       └── conversation.py # Conversation management routes
├── core/
│   ├── main.py           # FastAPI app factory, middleware, mounts
│   ├── config.py         # Settings loaded from .env
│   ├── database.py       # SQLAlchemy engine & session
│   ├── auth.py           # JWT utilities
│   └── dependencies.py   # Shared FastAPI dependencies
├── models/               # SQLAlchemy models
├── schema/               # Pydantic schemas
├── services/             # Business logic
├── alembic/              # Database migration files
├── main.py               # Entry point
└── requirements.txt
```

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in this directory:

```env
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
DATABASE=sqlite:///./chatpaper.db
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Generate a secure `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn main:app --reload
```

Server runs at `http://localhost:8000`.

## Useful URLs

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Interactive API docs (Swagger UI) |
| `http://localhost:8000/redoc` | ReDoc API docs |
| `http://localhost:8000/admin` | SQLAdmin dashboard |

## API Routes

### Auth — `/api/auth`

| Method | Route | Description | Access |
|--------|-------|-------------|--------|
| POST | `/token` | Login, returns JWT | Public |
| POST | `/users/` | Register a new user | Public |
| GET | `/users/` | List all users | Admin |
| GET | `/users/me/` | Get current user | Authorized |
| GET | `/users/{user_id}` | Get user by ID | Admin |
| PATCH | `/users/{user_id}` | Update user | Admin |
| DELETE | `/users/{user_id}` | Delete user | Admin |

### Files — `/api/files`

File upload and retrieval endpoints.

### Conversation — `/api/conversation`

| Method | Route | Description | Access |
|--------|-------|-------------|--------|
| POST | `/inconversationlist` | Create a conversation list | Authorized |
| PATCH | `/conversation-title/{id}` | Update conversation title | Authorized |

## Creating a Migration

After changing a model, generate and apply a new migration:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```
