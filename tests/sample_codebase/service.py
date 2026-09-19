"""Application service orchestration for sample testing codebase."""

from typing import Optional
from tests.sample_codebase.models import StorageBackend, UserProfile, UserRole


class UserService:
    """Service managing user profiles and storage interactions."""

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def register_user(self, user_id: str, username: str, email: str, role: UserRole = UserRole.VIEWER) -> UserProfile:
        """Register and persist a new user profile."""
        if not username:
            raise ValueError("Username cannot be empty")

        profile = UserProfile(user_id=user_id, username=username, email=email, role=role)
        payload = {
            "user_id": profile.user_id,
            "username": profile.username,
            "email": profile.email,
            "role": profile.role.value,
        }
        self.storage.save(user_id, payload)
        return profile

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Fetch user profile by user_id."""
        data = self.storage.fetch(user_id)
        if not data:
            return None
        return UserProfile(
            user_id=data["user_id"],
            username=data["username"],
            email=data["email"],
            role=UserRole(data["role"]),
        )
