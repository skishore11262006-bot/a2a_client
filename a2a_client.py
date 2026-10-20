import json
import uuid
from typing import Optional

import requests


class A2AClient:
    """Google A2A protocol client: discover a remote agent and talk to it."""

    def __init__(self, base_url: str, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.card: Optional[dict] = None
        self._rpc_id = 0

    def discover(self) -> dict:
        for path in ("/.well-known/agent.json", "/.well-known/agent-card.json"):
            try:
                r = requests.get(self.base_url + path, timeout=10)
                if r.status_code == 200:
                    self.card = r.json()
                    return self.card
            except Exception:
                continue
        raise RuntimeError(f"No A2A agent card found at {self.base_url}")

    @property
    def endpoint(self) -> str:
        if self.card and self.card.get("url"):
            return self.card["url"]
        return self.base_url + "/a2a"

    def _rpc(self, method: str, params: dict) -> dict:
        self._rpc_id += 1
        payload = {"jsonrpc": "2.0", "id": str(self._rpc_id),
                   "method": method, "params": params}
        r = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"A2A error: {data['error']}")
        return data.get("result")

    @staticmethod
    def _message(text: str, task_id: Optional[str] = None,
                 context_id: Optional[str] = None) -> dict:
        return {
            "kind": "message",
            "role": "user",
            "messageId": uuid.uuid4().hex,
            "taskId": task_id,
            "contextId": context_id,
            "parts": [{"type": "text", "text": text}],
        }

    def send(self, text: str, task_id: Optional[str] = None,
             context_id: Optional[str] = None) -> dict:
        task = self._rpc("message/send", {
            "message": self._message(text, task_id, context_id),
            "configuration": {"acceptedOutputModes": ["text"]},
        })
        return task

    def get_task(self, task_id: str) -> dict:
        return self._rpc("tasks/get", {"id": task_id})

    def cancel_task(self, task_id: str) -> dict:
        return self._rpc("tasks/cancel", {"id": task_id})

    @staticmethod
    def reply_text(task: dict) -> str:
        arts = task.get("artifacts") or []
        if arts:
            return "\n".join(
                p.get("text", "") for p in arts[0].get("parts", [])
                if p.get("type") == "text"
            )
        for m in reversed(task.get("history") or []):
            if m.get("role") == "assistant":
                return "\n".join(
                    p.get("text", "") for p in m.get("parts", [])
                    if p.get("type") == "text"
                )
        return ""

    def ask(self, text: str) -> str:
        task = self.send(text)
        return self.reply_text(task)

    def stream(self, text: str, context_id: Optional[str] = None):
        """Yield parsed SSE events from message/stream."""
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "message/stream",
            "params": {"message": self._message(text, None, context_id)},
        }
        with requests.post(self.endpoint, json=payload, stream=True,
                           timeout=self.timeout) as r:
            r.raise_for_status()
            event, data = None, []
            for line in r.iter_lines(decode_unicode=True):
                if line is None:
                    continue
                line = line.strip()
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data.append(line[5:].strip())
                elif line == "" and event:
                    try:
                        yield event, json.loads("\n".join(data))
                    except Exception:
                        pass
                    event, data = None, []


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
    q = " ".join(sys.argv[2:]) or "Hello, what can you do?"

    c = A2AClient(url)
    print("card:", c.discover().get("name"))
    task = c.send(q)
    print("state:", task["status"]["state"])
    print("reply:", c.reply_text(task))
