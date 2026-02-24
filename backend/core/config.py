from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://medical_user:medical_pass@localhost:5432/medical_data")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"
    
    # Data paths
    data_path: str = "/data"
    raw_data_path: str = "/data/raw"
    processed_data_path: str = "/data/processed"
    log_path: str = "/data/logs"
    
    # External APIs
    pubmed_api_key: Optional[str] = os.getenv("PUBMED_API_KEY")
    reddit_client_id: Optional[str] = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret: Optional[str] = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = os.getenv("REDDIT_USER_AGENT", "MedicusLabs/1.0")
    
    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Scraping
    default_rate_limit: float = 1.0  # requests per second
    relevance_threshold: float = 0.7
    batch_size: int = 100
    
    # Admin authentication
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")  # bcrypt hash
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Default disease terms for monitoring
    default_disease_terms: List[str] = [
        "diabetes",
        "COVID-19",
        "cancer",
        "hypertension",
        "heart disease",
        "alzheimer's disease",
        "parkinson's disease",
        "multiple sclerosis",
        "rheumatoid arthritis",
        "chronic kidney disease"
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()