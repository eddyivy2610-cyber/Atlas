"""Domain models for sample testing codebase."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class UserRole(str, Enum):
    """User privilege roles."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class StorageBackend(ABC):
    """Abstract interface for storage adapters."""

    @abstractmethod
    def save(self, key: str, payload: dict) -> bool:
        """Persist data record."""
        pass

    @abstractmethod
    def fetch(self, key: str) -> Optional[dict]:
        """Fetch record by key."""
        pass


@dataclass
class UserProfile:
    """User profile value object."""
    user_id: str
    username: str
    email: str
    role: UserRole = UserRole.VIEWER


class InMemoryStorage(StorageBackend):
    """In-memory dictionary storage implementation."""

    def __init__(self):
        self._store: dict[str, dict] = {}
        self.access_count: int = 0

    def save(self, key: str, payload: dict) -> bool:
        self._store[key] = payload
        self.access_count += 1
        return True

    def fetch(self, key: str) -> Optional[dict]:
        self.access_count += 1
        return self._store.get(key)
