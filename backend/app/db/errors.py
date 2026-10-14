"""Persistence-layer exceptions. Services map them to API error codes (roadmap 9.3.4)."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base class for DB-layer domain errors."""


class NotFoundError(PersistenceError):
    def __init__(self, entity: str, key: str) -> None:
        super().__init__(f"{entity} '{key}' not found")
        self.entity = entity
        self.key = key


class DuplicateError(PersistenceError):
    def __init__(self, entity: str, key: str) -> None:
        super().__init__(f"{entity} '{key}' already exists")
        self.entity = entity
        self.key = key


class RunImmutableError(PersistenceError):
    """The run is terminal (FINAL_RESULT/ABORTED); its results may not change. -> RUN_IMMUTABLE."""


class ImmutableRowError(PersistenceError):
    """An append-only/immutable row was updated or deleted (programming error)."""
