"""Seeds the database with an initial admin user."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings
from core.database import SessionLocal
from core.password import hash_password
from models.auth import User, UserRole

ADMIN_EMAIL = "admin@chatpaper.com"
from sqlalchemy import update

def seed_admin() -> None:
    db = SessionLocal()
    try:
        # Update users with no name
        updated = (
            db.query(User)
            .filter(User.name.is_(None))
            .update({User.name: "user"})
        )

        if updated:
            print(f"      Updated {updated} users with missing names.")

        if db.query(User).filter(User.email == ADMIN_EMAIL).first():
            db.commit()
            print(f"      Admin '{ADMIN_EMAIL}' already exists — skipped.")
            return

        admin = User(
            email=ADMIN_EMAIL,
            name="Admin",
            password=hash_password(settings.admin_password),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"      Admin user created — {ADMIN_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
