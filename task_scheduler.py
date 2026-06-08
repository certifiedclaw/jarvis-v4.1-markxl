"""
task_scheduler.py — JARVIS v3 Task Scheduler (stub / minimal implementation)

Provides a simple cron-style scheduler that the agent can register periodic
tasks with. Extend with APScheduler or a custom QThread for full functionality.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)


class ScheduledTask:
    def __init__(self, name: str, fn: Callable, interval_sec: float):
        self.name         = name
        self.fn           = fn
        self.interval_sec = interval_sec
        self.last_run: float = 0.0


class TaskScheduler:
    """Simple background thread that fires registered tasks at their intervals."""

    def __init__(self, agent=None, config=None):
        self.agent  = agent
        self.config = config
        self._tasks: list[ScheduledTask] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Public API ─────────────────────────────────────────────────────────

    def register(self, name: str, fn: Callable, interval_sec: float = 3600.0):
        self._tasks.append(ScheduledTask(name, fn, interval_sec))
        log.info("Scheduled task registered: %s (every %.0fs)", name, interval_sec)

    def as_tools(self) -> dict[str, Callable]:
        """Expose register_task as an agent tool so the LLM can schedule work."""
        def register_task(name: str, prompt: str, interval_minutes: float = 60):
            """Register a recurring prompt with the agent."""
            def _run():
                if self.agent:
                    try:
                        self.agent.run(prompt)
                    except Exception as exc:
                        log.warning("Scheduled task '%s' failed: %s", name, exc)
            self.register(name, _run, interval_sec=interval_minutes * 60)
            return f"✅ Scheduled '{name}' every {interval_minutes} minutes."

        return {"register_task": register_task}

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="TaskScheduler")
        self._thread.start()
        log.info("TaskScheduler started (%d tasks)", len(self._tasks))

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("TaskScheduler stopped")

    # ── Internal ───────────────────────────────────────────────────────────

    def _loop(self):
        while not self._stop_event.is_set():
            now = time.monotonic()
            for task in self._tasks:
                if now - task.last_run >= task.interval_sec:
                    task.last_run = now
                    try:
                        task.fn()
                    except Exception as exc:
                        log.warning("Task '%s' raised: %s", task.name, exc)
            self._stop_event.wait(timeout=10)   # tick every 10 s
