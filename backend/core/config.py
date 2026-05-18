from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv() 

class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY")
    algorithm: str = os.getenv("ALGORITHM")
    database: str = os.getenv("DATABASE")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

settings = Settings()