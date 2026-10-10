"""Load model artifacts without ever fabricating predictions."""
import json
from functools import lru_cache
from pathlib import Path
import joblib
from backend.config import MODEL_ARTIFACT_PATH, MODEL_INFO_PATH


def load_model(artifact_path: Path = MODEL_ARTIFACT_PATH):
    if not artifact_path.exists():
        return None
    modified_ns = artifact_path.stat().st_mtime_ns
    return _load_cached(str(artifact_path), modified_ns)


@lru_cache(maxsize=2)
def _load_cached(artifact_path: str, modified_ns: int):
    """Load once per artifact version; modification time invalidates retrained models."""
    del modified_ns
    return joblib.load(artifact_path)


def load_metadata() -> dict:
    if not MODEL_INFO_PATH.exists():
        return {}
    try:
        return json.loads(MODEL_INFO_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
