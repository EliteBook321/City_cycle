"""Fetch and validate the original UCI dataset; never generate substitute records."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Lock
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile
import pandas as pd
from backend.config import DATASET_PATH
from backend.models.train_model import FEATURES, TARGET, train
from backend.models.model_loader import load_metadata

UCI_ARCHIVE_URL = "https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip"
_INITIALIZE_LOCK = Lock()


def dataset_sha256(path: Path = DATASET_PATH) -> str | None:
    if not path.exists():
        return None
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_original_dataset(path: Path = DATASET_PATH) -> dict:
    """Download hour.csv from UCI and atomically install it after schema checks."""
    request = Request(UCI_ARCHIVE_URL, headers={"User-Agent": "CityCycle-Hackathon-Demo/1.0"})
    with urlopen(request, timeout=35) as response:
        payload = response.read(15 * 1024 * 1024 + 1)
    if len(payload) > 15 * 1024 * 1024:
        raise ValueError("UCI archive exceeded the 15 MB safety limit.")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            members = [name for name in archive.namelist() if Path(name).name.lower() == "hour.csv"]
            if len(members) != 1:
                raise ValueError("UCI archive did not contain exactly one hour.csv file.")
            csv_bytes = archive.read(members[0])
    except BadZipFile as exc:
        raise ValueError("UCI returned an invalid dataset archive.") from exc
    required = set(FEATURES + [TARGET, "dteday"])
    try:
        preview = pd.read_csv(BytesIO(csv_bytes), nrows=5)
    except (ValueError, pd.errors.ParserError) as exc:
        raise ValueError("The downloaded hour.csv could not be parsed.") from exc
    missing = sorted(required - set(preview.columns))
    if missing:
        raise ValueError(f"Downloaded source CSV is missing required columns: {', '.join(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    temporary.write_bytes(csv_bytes)
    temporary.replace(path)
    return {"path": str(path), "bytes": len(csv_bytes), "sha256": dataset_sha256(path)}


def initialize_project(force_retrain: bool = False) -> dict:
    """Ensure authentic source data and a matching trained artifact are available."""
    with _INITIALIZE_LOCK:
        downloaded = None
        if not DATASET_PATH.exists():
            downloaded = download_original_dataset()
        current_hash = dataset_sha256()
        metadata = load_metadata()
        try:
            artifact_ready = load_model() is not None
        except Exception:
            artifact_ready = False
        model_ready = (
            not force_retrain
            and artifact_ready
            and metadata.get("dataset_sha256") == current_hash
            and metadata.get("features") == FEATURES
        )
        if model_ready:
            return {"dataset_downloaded": downloaded is not None, "model_trained": False, "model_available": True, "dataset_path": str(DATASET_PATH), "dataset_sha256": current_hash, "message": "Original dataset and matching trained model are ready."}
        metrics = train(DATASET_PATH)
        return {"dataset_downloaded": downloaded is not None, "model_trained": True, "model_available": True, "dataset_path": str(DATASET_PATH), "dataset_sha256": current_hash, "training": {key: value for key, value in metrics.items() if key not in {"test_series", "feature_importance"}}, "message": "Original UCI data was validated and model evaluation completed."}
