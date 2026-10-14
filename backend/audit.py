"""Append-only audit trail: output/audit_trail.json.

The file is one JSON array that only grows. Each record is appended by rewriting just the
closing bracket (`…}` → `…},\n{new}\n]`), so earlier runs are never wiped and the file stays
valid JSON at every point. Records written:

  run_started / run_finished      one board run (with run_id)
  agent_started / agent_finished  one agent loop (prompt in, structured output out, usage)
  agent_step                      every step of a PydanticAI agent loop: the user prompt, each
                                  model response (text, tool calls + args, model served, tokens),
                                  each batch of tool results (full content), and the end
  delegation                      who asked whom for what, and the reply
  human_decision                  approvals decided by a human on the dashboard

Shop facts are never read from here — they come from the MCP server only.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
MAX_FIELD_CHARS = 6000  # long tool results are clipped (and marked) so the file stays readable

_lock = threading.Lock()


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + f"… [clipped {len(value) - MAX_FIELD_CHARS} chars]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value


def append(record_type: str, **data: Any) -> None:
    """Append one record. Never raises into an agent run: an audit failure is printed, not fatal."""
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "type": record_type, **_clip(data)}
    text = json.dumps(record, default=str, ensure_ascii=False)
    try:
        with _lock:
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
                AUDIT_PATH.write_text(f"[\n{text}\n]\n", encoding="utf-8")
                return
            with AUDIT_PATH.open("r+b") as f:
                size = f.seek(0, os.SEEK_END)
                f.seek(max(size - 4096, 0))
                tail = f.read()
                stripped = tail.rstrip()
                if not stripped.endswith(b"]"):
                    raise ValueError(f"{AUDIT_PATH.name} does not end with ']' — not appending to a corrupted file")
                empty = stripped[:-1].rstrip().endswith(b"[")  # records are objects, so "[" here means "[]"
                f.seek(size - len(tail) + len(stripped) - 1)  # position of the closing bracket
                f.truncate()
                f.write(f"{'' if empty else ','}\n{text}\n]\n".encode("utf-8"))
    except Exception as exc:  # pragma: no cover - auditing must not crash the shop
        print(f"[audit] failed to append {record_type}: {exc}")


def read_all() -> list[dict]:
    """Every record so far (for run summaries on the dashboard). Returns [] if the file is missing or unreadable."""
    try:
        with _lock:
            return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
