from io import BytesIO
from zipfile import ZipFile
import pandas as pd
from backend.models.train_model import FEATURES, TARGET
from backend.services import dataset_service


class MemoryResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit=-1):
        return self.data[:limit] if limit >= 0 else self.data


def test_download_installs_only_validated_source_hour_csv(tmp_path, monkeypatch):
    columns = FEATURES + [TARGET, "dteday", "casual", "registered"]
    row = {column: 0 for column in columns}
    row.update({"yr": 0, "season": 1, "mnth": 1, "hr": 0, "weathersit": 1, "dteday": "2011-01-01", "cnt": 5})
    csv_bytes = pd.DataFrame([row]).to_csv(index=False).encode("utf-8")
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w") as archive:
        archive.writestr("Bike-Sharing-Dataset/hour.csv", csv_bytes)
        archive.writestr("Bike-Sharing-Dataset/day.csv", "not used")
    monkeypatch.setattr(dataset_service, "urlopen", lambda request, timeout: MemoryResponse(archive_buffer.getvalue()))

    destination = tmp_path / "data" / "hour.csv"
    result = dataset_service.download_original_dataset(destination)

    saved = pd.read_csv(destination)
    assert len(saved) == 1
    assert set(FEATURES + [TARGET, "dteday"]).issubset(saved.columns)
    assert result["bytes"] == len(csv_bytes)
    assert len(result["sha256"]) == 64
