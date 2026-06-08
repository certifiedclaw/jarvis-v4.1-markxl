"""
smart_context.py — JARVIS v3 Context Compression (stub / implementation)

Both agent.py and main_window.py reference:
    from smart_context import compress_if_needed

This module provides that function. It trims the session message list when it
exceeds a token budget so the LLM context window doesn't overflow.

If you want full summarisation, set ENABLE_SUMMARIZE = True and ensure
the router is passed (it uses the fast model to produce a summary).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Approximate characters-per-token ratio for estimation (conservative)
_CHARS_PER_TOKEN = 4
# Default budget in tokens before compression kicks in
DEFAULT_TOKEN_BUDGET = 3000
# Whether to summarise the dropped messages (requires a live router)
ENABLE_SUMMARIZE = False


def _estimate_tokens(messages: list[dict]) -> int:
    total = sum(len(str(m.get("content", ""))) for m in messages)
    return total // _CHARS_PER_TOKEN


def compress_if_needed(
    messages: list[dict],
    router=None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> list[dict]:
    """
    Return a (possibly shortened) copy of `messages` that fits within
    `token_budget` tokens.

    Strategy:
    1. If the session is within budget, return as-is.
    2. Drop oldest non-system messages until under budget.
    3. Optionally replace the dropped block with a one-line summary
       produced by the router (when ENABLE_SUMMARIZE=True and router is live).

    Parameters
    ----------
    messages : list of {"role": str, "content": str}
        The full conversation / session history.
    router : optional router object with .chat_sync()
        Used for summarisation when ENABLE_SUMMARIZE is True.
    token_budget : int
        Maximum tokens to allow in the returned list.

    Returns
    -------
    list of message dicts — same structure, possibly shorter.
    """
    if not messages:
        return messages

    if _estimate_tokens(messages) <= token_budget:
        return messages

    # Separate system messages (always kept) from the rest
    system_msgs = [m for m in messages if m.get("role") == "system"]
    conv_msgs   = [m for m in messages if m.get("role") != "system"]

    # Drop oldest conversation turns until we're under budget
    dropped: list[dict] = []
    while conv_msgs and _estimate_tokens(system_msgs + conv_msgs) > token_budget:
        dropped.append(conv_msgs.pop(0))

    # Optionally summarise the dropped block
    if dropped and ENABLE_SUMMARIZE and router is not None:
        try:
            dropped_text = "\n".join(
                f"{m['role']}: {m['content'][:300]}" for m in dropped
            )
            summary_prompt = (
                f"Summarise these earlier messages in 1-2 sentences:\n{dropped_text}"
            )
            summary = router.chat_sync([{"role": "user", "content": summary_prompt}])
            summary_msg = {"role": "system", "content": f"[Earlier context] {summary}"}
            result = system_msgs + [summary_msg] + conv_msgs
        except Exception as exc:
            logger.warning("smart_context summarisation failed: %s", exc)
            result = system_msgs + conv_msgs
    else:
        if dropped:
            logger.debug(
                "smart_context: dropped %d messages to fit token budget", len(dropped)
            )
        result = system_msgs + conv_msgs

    return result
