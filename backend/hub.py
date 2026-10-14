"""In-memory event log the dashboard follows over SSE.

Every agent step, delegation, approval, and DB change is appended here. Clients stream
from /api/events?since=N, so a reloaded dashboard replays the current run and then keeps
listening. Token usage is tallied per agent as model responses arrive.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator


class EventHub:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.usage: dict[str, dict] = {}
        self.run_id = 0
        self._cond = asyncio.Condition()
        self._started = time.perf_counter()

    def clear(self) -> None:
        self.events.clear()
        self.usage.clear()
        self.run_id += 1
        self._started = time.perf_counter()

    def emit(self, event_type: str, **data: Any) -> None:
        event = {
            "seq": len(self.events),
            "run_id": self.run_id,
            "type": event_type,
            "t_ms": round((time.perf_counter() - self._started) * 1000),
            "ts": time.time(),
            **data,
        }
        if event_type == "agent_step" and data.get("kind") == "model_response":
            self._tally(data.get("agent", "?"), data.get("usage") or {})
            event["usage_totals"] = self.totals()
        self.events.append(event)
        asyncio.get_event_loop().create_task(self._notify())

    async def _notify(self) -> None:
        async with self._cond:
            self._cond.notify_all()

    def _tally(self, agent: str, u: dict) -> None:
        row = self.usage.setdefault(agent, {"agent": agent, "requests": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0})
        row["requests"] += 1
        row["input_tokens"] += u.get("input_tokens", 0)
        row["output_tokens"] += u.get("output_tokens", 0)
        row["cached_tokens"] += u.get("cache_read_tokens", 0)

    def totals(self) -> dict:
        rows = list(self.usage.values())
        return {
            "by_agent": rows,
            "requests": sum(r["requests"] for r in rows),
            "input_tokens": sum(r["input_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
        }

    async def stream(self, since: int = 0) -> AsyncIterator[dict]:
        i, run_id = since, self.run_id
        while True:
            if run_id != self.run_id:  # log was cleared for a new run — start from its top
                i, run_id = 0, self.run_id
            while i < len(self.events):
                yield self.events[i]
                i += 1
            async with self._cond:
                try:
                    await asyncio.wait_for(self._cond.wait(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"type": "ping", "seq": -1}


hub = EventHub()
