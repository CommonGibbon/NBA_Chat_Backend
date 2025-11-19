import json
import datetime
import os
from typing import Any

class TraceLogger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        self.filepath = f"logs/trace_{run_id}.jsonl"

    def log(self, component: str, event: str, payload: Any):
        """
        Writes a structured log entry.
        """
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "run_id": self.run_id,
            "component": component,
            "event": event,
            "payload": self._sanitize(payload)
        }
        
        with open(self.filepath, "a", encoding='utf-8') as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _sanitize(self, obj: Any) -> Any:
        """
        Helper to ensure objects are JSON serializable.
        For complex GenAI objects, we might want to convert to dict or str.
        """
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if hasattr(obj, "__dict__"):
            return str(obj) # Fallback for objects without explicit serialization
        return obj