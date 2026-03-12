"""Hash-keyed file cache for raw API responses."""

from __future__ import annotations

import hashlib
import json
import time
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
