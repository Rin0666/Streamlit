"""Revocable, expiring sessions. Passwords and raw tokens are never retained."""
from __future__ import annotations

import hashlib
import secrets
import threading
import time

from dashboard.access import DirectoryUser


class SessionStore:
    def __init__(self, lifetime_seconds: int = 8 * 60 * 60):
        self.lifetime_seconds = lifetime_seconds
        self._sessions: dict[str, tuple[DirectoryUser, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, user: DirectoryUser | str) -> str:
        if isinstance(user, str):
            user = DirectoryUser(user)
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._sessions = {key: value for key, value in self._sessions.items()
                              if value[1] > now}
            self._sessions[self._digest(token)] = (user, now + self.lifetime_seconds)
        return token

    def resolve(self, token: object) -> str | None:
        user = self.resolve_user(token)
        return user.username if user else None

    def resolve_user(self, token: object) -> DirectoryUser | None:
        if not isinstance(token, str) or len(token) != 43:
            return None
        digest = self._digest(token)
        with self._lock:
            session = self._sessions.get(digest)
            if session is None:
                return None
            if session[1] <= time.time():
                self._sessions.pop(digest, None)
                return None
            return session[0]

    def revoke(self, token: object) -> None:
        if isinstance(token, str):
            with self._lock:
                self._sessions.pop(self._digest(token), None)
