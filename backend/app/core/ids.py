"""Identifier helpers. All generated IDs are UUIDv4 strings (roadmap 7.1)."""

from __future__ import annotations

import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True
