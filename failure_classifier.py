import re
from typing import Optional, Tuple
from framework.models import FailureType, FailureSeverity


SEVERITY_MAP = {
    FailureType.TOOL_FAILURE: FailureSeverity.MEDIUM,
    FailureType.CONTEXT_OVERFLOW: FailureSeverity.MEDIUM,
    FailureType.TIMEOUT: FailureSeverity.MEDIUM,
    FailureType.RATE_LIMIT: FailureSeverity.LOW,
    FailureType.HALLUCINATION: FailureSeverity.HIGH,
    FailureType.LOOP_DETECTED: FailureSeverity.HIGH,
    FailureType.GOAL_DRIFT: FailureSeverity.MEDIUM,
    FailureType.PROMPT_INJECTION: FailureSeverity.CRITICAL,
    FailureType.INDIRECT_INJECTION: FailureSeverity.CRITICAL,
    FailureType.AGENT_MANIPULATION: FailureSeverity.CRITICAL,
    FailureType.UNKNOWN: FailureSeverity.MEDIUM,
}

HALLUCINATION_PATTERNS = [
    r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:billion|trillion|million)\b",
    r"\b(?:100|[1-9]\d{2,})%\b",
    r"as of \d{4}",
    r"according to (?:my|internal) (?:data|knowledge|training)",
]

LOOP_KEYWORDS = [
    "as i mentioned",
    "as stated before",
    "repeating my previous",
    "i already said",
    "like i said earlier",
]


class FailureClassifier:
    def __init__(self):
        self.call_history: list[str] = []

    def classify_exception(self, error: Exception) -> Tuple[FailureType, str]:
        error_str = str(error).lower()

        if any(k in error_str for k in ["timeout", "timed out", "deadline"]):
            return FailureType.TIMEOUT, "Agent execution timed out"

        if any(k in error_str for k in ["rate limit", "429", "too many requests"]):
            return FailureType.RATE_LIMIT, "Rate limit hit on external API"

        if any(k in error_str for k in ["context length", "token limit", "max tokens", "context window"]):
            return FailureType.CONTEXT_OVERFLOW, "Context window exceeded"

        if any(k in error_str for k in ["tool", "function call", "api error", "connection", "404", "500"]):
            return FailureType.TOOL_FAILURE, f"Tool execution failed: {str(error)[:200]}"

        return FailureType.UNKNOWN, f"Unclassified error: {str(error)[:200]}"

    def classify_response(self, response: str, task: str) -> Optional[Tuple[FailureType, str]]:
        response_lower = response.lower()

        if self._detect_loop(response_lower):
            return FailureType.LOOP_DETECTED, "Agent is repeating itself indicating a reasoning loop"

        if self._detect_hallucination_signals(response):
            return FailureType.HALLUCINATION, "Response contains suspicious numerical claims or unsupported assertions"

        if self._detect_goal_drift(response_lower, task.lower()):
            return FailureType.GOAL_DRIFT, "Agent response does not align with the original task"

        return None

    def _detect_loop(self, response_lower: str) -> bool:
        self.call_history.append(response_lower[:100])
        if len(self.call_history) > 5:
            recent = self.call_history[-3:]
            if len(set(recent)) == 1:
                return True
        return any(kw in response_lower for kw in LOOP_KEYWORDS)

    def _detect_hallucination_signals(self, response: str) -> bool:
        matches = 0
        for pattern in HALLUCINATION_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                matches += 1
        return matches >= 2

    def _detect_goal_drift(self, response_lower: str, task_lower: str) -> bool:
        task_keywords = set(task_lower.split())
        response_keywords = set(response_lower.split())
        overlap = task_keywords & response_keywords
        if len(task_keywords) > 3 and len(overlap) / len(task_keywords) < 0.1:
            return True
        return False

    def get_severity(self, failure_type: FailureType) -> FailureSeverity:
        return SEVERITY_MAP.get(failure_type, FailureSeverity.MEDIUM)
