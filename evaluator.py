"""
core/evaluator.py — MARK XL Self-Evaluation System
Inspired by OpenJarvis evaluation architecture.

The evaluator asks the LLM: "Did the response actually solve the user's request?"
If not, it returns a structured failure report so the agent can retry or replan.

This is the #1 thing that separates a demo bot from a real assistant.
Silent failures get caught instead of being silently swallowed.

Usage:
    from core.evaluator import Evaluator
    ev = Evaluator()
    result = ev.evaluate(user_request, assistant_response, tool_results)
    if not result.passed:
        print(f"Failed: {result.reason}")
        # trigger replan or retry
"""
from __future__ import annotations
import logging
import re
import json
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    passed: bool
    score: float          # 0.0 – 1.0
    reason: str = ""
    suggestions: list[str] = field(default_factory=list)
    needs_retry: bool = False
    needs_replan: bool = False


_EVAL_SYSTEM = """You are a strict quality-control evaluator for an AI assistant.

Given:
1. The user's original request
2. The assistant's final response
3. Any tool results that were produced

Your job: assess whether the assistant ACTUALLY completed the user's request.

Score 0.0–1.0:
  1.0 = fully completed, correct, actionable
  0.7 = mostly done, minor gaps
  0.4 = partial, important parts missing
  0.0 = failed, wrong, or refused

Respond with ONLY valid JSON:
{
  "passed": true|false,
  "score": 0.0-1.0,
  "reason": "one sentence explaining your verdict",
  "suggestions": ["what could be improved"],
  "needs_retry": false,
  "needs_replan": false
}

passed = score >= 0.6
needs_retry = transient failure (network, timeout) — same approach could work
needs_replan = wrong approach — different tools/strategy needed"""


class Evaluator:
    """
    Evaluates whether a response actually solved the user's request.
    Gracefully degrades: if the LLM call fails, returns passed=True
    so execution isn't blocked.
    """

    def __init__(self, enabled: bool = True, threshold: float = 0.6) -> None:
        self.enabled = enabled
        self.threshold = threshold

    def evaluate(
        self,
        user_request: str,
        assistant_response: str,
        tool_results: list[tuple[str, str]] | None = None,
    ) -> EvalResult:
        if not self.enabled:
            return EvalResult(passed=True, score=1.0, reason="Evaluation disabled")

        tool_summary = ""
        if tool_results:
            lines = [f"  [{t}]: {r[:200]}" for t, r in tool_results[:5]]
            tool_summary = "Tool results:\n" + "\n".join(lines)

        prompt = (
            f"User request: {user_request}\n\n"
            f"Assistant response:\n{assistant_response[:600]}\n\n"
            f"{tool_summary}"
        )

        try:
            from core.llm_client import call_llm_text
            raw = call_llm_text(prompt, system=_EVAL_SYSTEM)
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            data = json.loads(raw)
            score = float(data.get("score", 0.5))
            return EvalResult(
                passed=score >= self.threshold,
                score=score,
                reason=data.get("reason", ""),
                suggestions=data.get("suggestions", []),
                needs_retry=bool(data.get("needs_retry", False)),
                needs_replan=bool(data.get("needs_replan", False)),
            )
        except Exception as e:
            logger.debug("Evaluator failed (non-fatal): %s", e)
            # Graceful degradation: don't block on eval failure
            return EvalResult(passed=True, score=0.5, reason=f"Eval unavailable: {e}")

    def quick_check(self, response: str) -> bool:
        """
        Fast heuristic check without an LLM call.
        Returns False if the response looks like an obvious failure.
        """
        lower = response.lower()
        failure_phrases = [
            "i cannot", "i can't", "i'm unable", "i don't have access",
            "i apologize", "error occurred", "something went wrong",
            "failed to", "could not complete", "not able to",
        ]
        return not any(p in lower for p in failure_phrases)
