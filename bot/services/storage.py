"""Simple JSON-based persistent storage for guild settings and role configs."""

import json
import logging
import os

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class JSONStorage:
    """Read/write a JSON file as a dict, with auto-save."""

    def __init__(self, filename: str):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.path = os.path.join(DATA_DIR, filename)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load %s: %s — starting fresh.", self.path, e)
        return {}

    def save(self) -> None:
        """Write current data to disk."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Failed to save %s: %s", self.path, e)

    def get(self, key: str, default=None):
        return self._data.get(str(key), default)

    def set(self, key: str, value) -> None:
        self._data[str(key)] = value
        self.save()

    def delete(self, key: str) -> None:
        self._data.pop(str(key), None)
        self.save()

    def all(self) -> dict:
        return self._data.copy()
