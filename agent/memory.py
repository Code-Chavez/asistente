import os
import json
from typing import Dict, Any, Optional


class PreferencesMemory:
    def __init__(self, path: Optional[str] = None):
        base = os.path.dirname(__file__)
        self.path = path or os.path.join(base, "preferences.json")
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            else:
                self.data = {"stats": {}}
        except Exception:
            self.data = {"stats": {}}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record_outcome(self, action: str, success: bool):
        stats = self.data.setdefault("stats", {})
        a = stats.setdefault(action, {"success": 0, "fail": 0})
        if success:
            a["success"] += 1
        else:
            a["fail"] += 1
        self._save()

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        return self.data.get("stats", {})


class ConversationalMemory:
    def __init__(self, path: Optional[str] = None, max_history: int = 10):
        base = os.path.dirname(__file__)
        self.path = path or os.path.join(base, "chat_history.json")
        self.max_history = max_history
        self.history: list[Dict[str, str]] = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
        except Exception:
            self.history = []

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self._save()

    def get_history(self) -> list[Dict[str, str]]:
        return self.history
