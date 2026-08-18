import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from scripts.shared_utils import NOTE_MAX_LEN

STATUS_FLOW = ["queued", "scaffolded", "extracted", "analyzed", "assembled"]
FAILED = "failed"
SKIP_STATUSES = {"assembled", "failed"}


class JsonStateStore:
    def __init__(self, state_path: str):
        self.state_path = Path(state_path)
        if not self.state_path.exists():
            self._save({"items": [], "summary": {}})

    def _load(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent, suffix=".tmp")
        try:
            os.write(fd, json.dumps(data, indent=2).encode("utf-8"))
            os.close(fd)
            fd = -1
            Path(tmp).replace(self.state_path)
        except Exception:
            if fd >= 0:
                os.close(fd)
            Path(tmp).unlink(missing_ok=True)
            raise

    def get_all_items(self) -> list[dict]:
        return self._load()["items"]

    def get_pending_items(self) -> list[dict]:
        return [i for i in self.get_all_items() if i.get("status") not in SKIP_STATUSES]

    def get_item(self, item_id: str) -> dict | None:
        return next((i for i in self.get_all_items() if i["id"] == item_id), None)

    def upsert_item(self, item: dict) -> None:
        data = self._load()
        for existing in data["items"]:
            if existing["id"] == item["id"]:
                existing.update(item)
                break
        else:
            data["items"].append(item)
        self._save(data)

    def update_item(self, item_id: str, updates: dict) -> None:
        data = self._load()
        for item in data["items"]:
            if item["id"] == item_id:
                item.update(updates)
                break
        self._save(data)

    def set_status(self, item_id: str, status: str, notes: str = None) -> None:
        updates = {"status": status}
        if notes is not None:
            updates["notes"] = notes[:NOTE_MAX_LEN]
        self.update_item(item_id, updates)

    def add_item(self, item: dict) -> None:
        self.upsert_item(item)

    def write_summary(self) -> None:
        data = self._load()
        counts = {}
        for item in data["items"]:
            s = item.get("status", "queued")
            counts[s] = counts.get(s, 0) + 1
        data["summary"] = {
            "total": len(data["items"]),
            "status_counts": counts,
            "last_updated": datetime.now().isoformat(),
        }
        self._save(data)