"""
core/loop_guard.py — MARK XL Loop Guard
Ported from OpenJarvis agents/loop_guard.py, adapted for flat architecture.

Detects when the LLM is stuck calling the same tool with the same args in a loop
and breaks the cycle by injecting a hard stop or forcing a different approach.

Usage in main.py _process_message:
    from core.loop_guard import LoopGuard
    guard = LoopGuard(max_repeats=2, window=4)
    # in tool call loop:
    if guard.check(tool_name, tool_args):
        break  # loop detected, stop
    guard.record(tool_name, tool_args)
"""
from __future__ import annotations
import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GuardVerdict:
    blocked: bool
    reason: str = ""


class LoopGuard:
    """
    Tracks recent (tool, args) pairs and blocks if the same call
    repeats too many times within a rolling window.
    """

    def __init__(self, max_repeats: int = 2, window: int = 6) -> None:
        self._max_repeats = max_repeats
        self._window = window
        self._history: deque[str] = deque(maxlen=window)

    def _fingerprint(self, tool: str, args: dict | str) -> str:
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        payload = json.dumps({"t": tool, "a": args}, sort_keys=True, default=str)
        return hashlib.md5(payload.encode()).hexdigest()[:12]

    def check(self, tool: str, args: dict | str) -> GuardVerdict:
        """
        Call BEFORE executing a tool.
        Returns GuardVerdict(blocked=True) if loop detected.
        """
        fp = self._fingerprint(tool, args)
        count = sum(1 for h in self._history if h == fp)
        if count >= self._max_repeats:
            reason = (
                f"Tool '{tool}' called with identical arguments "
                f"{count + 1} times in the last {self._window} calls. "
                "Breaking loop."
            )
            logger.warning("[LoopGuard] %s", reason)
            return GuardVerdict(blocked=True, reason=reason)
        return GuardVerdict(blocked=False)

    def record(self, tool: str, args: dict | str) -> None:
        """Call AFTER executing a tool to update history."""
        self._history.append(self._fingerprint(tool, args))

    def reset(self) -> None:
        """Reset between top-level user requests."""
        self._history.clear()

    def inject_break_message(self, tool: str) -> str:
        """Return a tool result that tells the LLM to stop looping."""
        return (
            f"[LOOP GUARD] Repeated call to '{tool}' blocked. "
            "You are in a loop. Stop calling this tool. "
            "Synthesize a final answer from what you already have, "
            "or tell the user you cannot complete this task."
        )
