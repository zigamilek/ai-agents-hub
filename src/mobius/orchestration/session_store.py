from __future__ import annotations

from collections import OrderedDict, deque
from threading import Lock


class StickySessionStore:
    def __init__(self, *, history_size: int = 3, max_sessions: int = 4096) -> None:
        self._history_size = max(1, history_size)
        self._max_sessions = max(64, max_sessions)
        self._domains_by_session: OrderedDict[str, deque[str]] = OrderedDict()
        self._lock = Lock()

    def reset(self, session_key: str) -> None:
        with self._lock:
            self._domains_by_session.pop(session_key, None)

    def latest_domain(self, session_key: str) -> str | None:
        history = self.recent_domains(session_key)
        if not history:
            return None
        return history[-1]

    def recent_domains(self, session_key: str) -> list[str]:
        with self._lock:
            history = self._domains_by_session.get(session_key)
            if not history:
                return []
            # Refresh LRU position.
            self._domains_by_session.move_to_end(session_key)
            return list(history)

    def remember_domain(self, session_key: str, domain: str) -> None:
        with self._lock:
            history = self._domains_by_session.get(session_key)
            if history is None:
                history = deque(maxlen=self._history_size)
                self._domains_by_session[session_key] = history
            history.append(domain)
            self._domains_by_session.move_to_end(session_key)
            while len(self._domains_by_session) > self._max_sessions:
                self._domains_by_session.popitem(last=False)
