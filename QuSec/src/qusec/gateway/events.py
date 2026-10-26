"""
Event Emitter Subsystem for QuSec Platform Bridge.
Publishes structured JSON events to connected social media clients,
web applications, and terminal UI subscribers.
"""

import time
import json
import asyncio
import threading
from typing import List, Dict, Any, Callable


class EventEmitter:
    """
    Thread-safe event broadcaster supporting async queues and synchronous callbacks.
    """

    def __init__(self):
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._async_queues: List[asyncio.Queue] = []
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.max_history = 100

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        """Register synchronous event listener."""
        with self._lock:
            self._subscribers.append(callback)

    def register_async_queue(self, q: asyncio.Queue):
        """Register asyncio queue for WebSocket / SSE streaming."""
        with self._lock:
            self._async_queues.append(q)

    def unregister_async_queue(self, q: asyncio.Queue):
        """Remove asyncio queue."""
        with self._lock:
            if q in self._async_queues:
                self._async_queues.remove(q)

    def emit(self, event_name: str, data: Dict[str, Any]):
        """Publish an event across all registered channels."""
        event = {
            "event": event_name,
            "timestamp": time.time(),
            "iso_time": time.strftime("%H:%M:%S"),
            "data": data,
        }

        with self._lock:
            self._history.append(event)
            if len(self._history) > self.max_history:
                self._history.pop(0)

            # Synchronous callbacks
            for cb in list(self._subscribers):
                try:
                    cb(event)
                except Exception:
                    pass

            # Async queues
            for q in list(self._async_queues):
                try:
                    q.put_nowait(event)
                except Exception:
                    pass

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch the most recent events."""
        with self._lock:
            return list(self._history[-limit:])
