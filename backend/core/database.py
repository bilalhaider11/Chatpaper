from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from Chatpaper.backend.core.config import settings  

SQLALCHEMY_DATABASE_URL = settings.database

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()