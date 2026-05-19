"""Creates the PostgreSQL database if it does not already exist."""

import sys
import os
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from core.config import settings


def create_database() -> None:
    url = urlparse(settings.database)
    db_name = url.path.lstrip("/")

    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname="postgres",
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if cur.fetchone():
        print(f"      Database '{db_name}' already exists — skipped.")
    else:
        cur.execute(f'CREATE DATABASE "{db_name}"')
        print(f"      Database '{db_name}' created.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    create_database()
