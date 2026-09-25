"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BASE_DIR / "generated"
DATA_DIR = BASE_DIR / "data"

# Ensure runtime directories exist
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")

# OpenAI Configuration
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

# Server Configuration
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0").strip()
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
API_URL: str = (os.getenv("BACKEND_URL") or os.getenv("API_URL", f"http://localhost:{BACKEND_PORT}")).rstrip("/")

# HR Dispatch Configuration
HR_EMAIL: str = os.getenv("HR_EMAIL", "hr-admissions@company.mock").strip()

# Optional SMTP Configuration
SMTP_HOST: str = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "").strip()

# Application Constraints
MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")
