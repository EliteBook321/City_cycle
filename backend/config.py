"""Environment-backed configuration for CityCycle."""
from pathlib import Path
import os
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
DATASET_PATH = Path(os.getenv("DATASET_PATH", BACKEND_DIR / "data" / "hour.csv"))
MODEL_ARTIFACT_PATH = Path(os.getenv("MODEL_ARTIFACT_PATH", BACKEND_DIR / "models" / "artifacts" / "citycycle_model.joblib"))
METRICS_PATH = MODEL_ARTIFACT_PATH.with_name("metrics.json")
MODEL_INFO_PATH = MODEL_ARTIFACT_PATH.with_name("model_info.json")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000").split(",") if origin.strip()]
APP_VERSION = "1.0.0"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
