"""Hash-keyed file cache for raw API responses + UI session persistence."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path


class FileCache:
    """Simple disk-based JSON cache using SHA-256 keys."""

    def __init__(self, cache_dir: str = ".cache", ttl_seconds: int = 86400 * 7):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds

    @staticmethod
    def _make_key(query: str, source: str, params: str = "") -> str:
        raw = f"{source}:{query}:{params}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, query: str, source: str, params: str = "") -> dict | list | None:
        key = self._make_key(query, source, params)
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > self._ttl:
            path.unlink(missing_ok=True)
            return None
        return data.get("payload")

    def put(self, query: str, source: str, payload: dict | list, params: str = "") -> None:
        key = self._make_key(query, source, params)
        path = self._path(key)
        data = {"_cached_at": time.time(), "payload": payload}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def clear(self) -> int:
        """Remove all cached files. Returns count deleted."""
        count = 0
        for f in self._dir.glob("*.json"):
            f.unlink()
            count += 1
        return count


class UIResultCache:
    """Persistent disk cache for the last search/analysis result displayed in the UI.

    Survives browser refreshes, Streamlit session resets, and computer sleep/wake
    cycles as long as the server process (or the cache directory) persists.
    Layout: ``.cache/ui_last_result.json``
    """

    _PATH = Path(".cache/ui_last_result.json")

    @classmethod
    def save(cls, result: dict, query: str) -> None:
        """Persist *result* (full search/analyze response dict) to disk."""
        cls._PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "saved_at": datetime.utcnow().isoformat(),
            "query": query,
            "result": result,
        }
        try:
            cls._PATH.write_text(
                json.dumps(data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass  # non-fatal — cache is best-effort

    @classmethod
    def load(cls) -> dict | None:
        """Return the cached data dict, or None if nothing is stored."""
        if not cls._PATH.exists():
            return None
        try:
            return json.loads(cls._PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    @classmethod
    def clear(cls) -> None:
        """Delete the cached result file."""
        cls._PATH.unlink(missing_ok=True)
