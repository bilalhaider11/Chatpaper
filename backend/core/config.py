from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv() 

class Settings(BaseModel):
    secret_key: str = os.getenv("SECRET_KEY")
    algorithm: str = os.getenv("ALGORITHM")
    database: str = os.getenv("DATABASE")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    google_client_id:str = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret:str = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_url:str = os.getenv("REDIRECT_URL")
    frontend_url: str = os.getenv("FRONTEND_URL")
    jwt_secret_key:str = os.getenv("JWT_SECRET_KEY")

    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    chat_flush_interval_seconds: int = int(os.getenv("CHAT_FLUSH_INTERVAL_SECONDS", "50"))
    chat_stream_chunk_size: int = int(os.getenv("CHAT_STREAM_CHUNK_SIZE", "12"))

settings = Settings()