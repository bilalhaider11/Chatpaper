"""Seeds the database with an initial admin user."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from core.database import SessionLocal
from models.auth import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_EMAIL = "admin@chatpaper.com"
ADMIN_PASSWORD = "admin123"


def seed_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == ADMIN_EMAIL).first():
            print(f"      Admin '{ADMIN_EMAIL}' already exists — skipped.")
            return

        admin = User(
            email=ADMIN_EMAIL,
            password=pwd_context.hash(ADMIN_PASSWORD),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"      Admin user created — {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
