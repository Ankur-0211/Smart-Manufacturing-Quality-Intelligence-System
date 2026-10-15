"""In-process LRU cache of stage results (roadmap §9.5.2, Plan §13.3). No Redis.

Key = SHA-256 of (stage_name, canonical JSON of the stage input slice, canonical JSON of the
upstream context, module_version, constraints_version). Stage modules are pure (roadmap B4), so a
hit is exactly the result a fresh call would return. Changing module or constraints versions
changes the key, so stale results are never served.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _normalise(value: Any) -> Any:
    """Make numerically equal values hash equally: 12 and 12.0 -> 12.0 (bools stay bools)."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, Mapping):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_normalise(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def stage_cache_key(
    stage_name: str,
    inputs: Mapping[str, Any],
    upstream: Mapping[str, Any],
    module_version: str,
    constraints_version: str,
) -> str:
    payload = canonical_json(
        _normalise([stage_name, inputs, upstream, module_version, constraints_version])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class CacheStats:
    size: int
    maxsize: int
    hits: int
    misses: int


class StageCache:
    """Thread-safe LRU. ``maxsize=0`` disables caching. Values are deep-copied in and out so callers
    can never mutate a cached result."""

    def __init__(self, maxsize: int = 5000) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._data.get(key)
            if value is None:
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return copy.deepcopy(value)

    def put(self, key: str, value: Mapping[str, Any]) -> None:
        if self.maxsize <= 0:
            return
        with self._lock:
            self._data[key] = copy.deepcopy(dict(value))
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(len(self._data), self.maxsize, self.hits, self.misses)
