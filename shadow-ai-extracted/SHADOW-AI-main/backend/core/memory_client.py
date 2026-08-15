import os
import requests


class MemoryClient:
    def __init__(self):
        self.base = os.getenv("MEMORY_BACKEND_URL", "").strip().rstrip("/")
        self.key = os.getenv("MEMORY_API_KEY", "").strip()
        self.timeout = int(os.getenv("MEMORY_TIMEOUT_SECONDS", "8"))

    def enabled(self):
        return bool(self.base)

    def _headers(self):
        return {"X-Memory-Key": self.key} if self.key else {}

    def search(self, user_id, query):
        if not self.enabled():
            return []
        try:
            r = requests.post(f"{self.base}/memory/search", headers=self._headers(), json={"user_id": user_id, "query": query, "limit": 8}, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("memories", [])
        except Exception as exc:
            print(f"[Memory/search] {type(exc).__name__}: {exc}")
            return []

    def save(self, user_id, content, importance=3):
        if not self.enabled() or not content.strip():
            return False
        try:
            r = requests.post(f"{self.base}/memory/save", headers=self._headers(), json={"user_id": user_id, "content": content.strip(), "importance": importance}, timeout=self.timeout)
            r.raise_for_status()
            return True
        except Exception as exc:
            print(f"[Memory/save] {type(exc).__name__}: {exc}")
            return False

    def save_message(self, user_id, role, content):
        if not self.enabled() or not content.strip():
            return False
        try:
            r = requests.post(f"{self.base}/conversation/message", headers=self._headers(), json={"user_id": user_id, "role": role, "content": content}, timeout=self.timeout)
            r.raise_for_status()
            return True
        except Exception as exc:
            print(f"[Memory/message] {type(exc).__name__}: {exc}")
            return False
