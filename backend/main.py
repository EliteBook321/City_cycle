"""CityCycle FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import ALLOWED_ORIGINS, APP_VERSION, DATASET_PATH
from backend.models.model_loader import load_metadata, load_model
from backend.routes import forecast, insights, metrics, actions, setup

app = FastAPI(title="CityCycle Demand Intelligence API", version=APP_VERSION, description="Citywide hourly bike rental forecasting and operational decision support.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "Authorization"])
app.include_router(forecast.router)
app.include_router(insights.router)
app.include_router(metrics.router)
app.include_router(actions.router)
app.include_router(setup.router)

@app.get("/api/health")
def health():
    metadata = load_metadata()
    try:
        model_available = load_model() is not None and bool(metadata)
    except Exception:
        model_available = False
    return {"status": "ok", "application_version": APP_VERSION, "model_available": model_available, "dataset_available": DATASET_PATH.exists(), "model_name": metadata.get("model_name") if model_available else None, "model_version": metadata.get("model_version") if model_available else None}

@app.get("/api/model/info")
def model_info():
    metadata = load_metadata()
    try:
        available = load_model() is not None and bool(metadata)
    except Exception:
        available = False
    return {"available": available, "metadata": metadata if available else {}, "message": None if available else "Model unavailable. Install the source dataset and run python -m backend.models.train_model."}
