import time
import asyncio
from typing import Optional, Callable, Any
from framework.models import FailureType, RecoveryAction


FAILURE_TO_RECOVERY: dict[FailureType, RecoveryAction] = {
    FailureType.TOOL_FAILURE: RecoveryAction.RETRY_WITH_BACKOFF,
    FailureType.CONTEXT_OVERFLOW: RecoveryAction.TRUNCATE_CONTEXT,
    FailureType.TIMEOUT: RecoveryAction.RETRY_WITH_BACKOFF,
    FailureType.RATE_LIMIT: RecoveryAction.RETRY_WITH_BACKOFF,
    FailureType.HALLUCINATION: RecoveryAction.ESCALATE_TO_HUMAN,
    FailureType.LOOP_DETECTED: RecoveryAction.ABORT,
    FailureType.GOAL_DRIFT: RecoveryAction.FALLBACK_RESPONSE,
    FailureType.PROMPT_INJECTION: RecoveryAction.QUARANTINE,
    FailureType.INDIRECT_INJECTION: RecoveryAction.QUARANTINE,
    FailureType.AGENT_MANIPULATION: RecoveryAction.QUARANTINE,
    FailureType.UNKNOWN: RecoveryAction.RETRY,
}


class RecoveryStrategies:
    def __init__(self, max_retries: int = 3, base_backoff: float = 1.0):
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._retry_counts: dict[str, int] = {}

    def get_recovery_action(self, failure_type: FailureType) -> RecoveryAction:
        return FAILURE_TO_RECOVERY.get(failure_type, RecoveryAction.RETRY)

    async def execute_recovery(
        self,
        agent_id: str,
        failure_type: FailureType,
        retry_fn: Optional[Callable] = None,
        context: Optional[list] = None,
        task: Optional[str] = None,
    ) -> tuple[bool, Any, str]:
        action = self.get_recovery_action(failure_type)
        key = f"{agent_id}:{failure_type}"

        if action == RecoveryAction.RETRY:
            return await self._retry(key, retry_fn)

        elif action == RecoveryAction.RETRY_WITH_BACKOFF:
            return await self._retry_with_backoff(key, retry_fn)

        elif action == RecoveryAction.TRUNCATE_CONTEXT:
            return await self._truncate_and_retry(key, retry_fn, context)

        elif action == RecoveryAction.ESCALATE_TO_HUMAN:
            return False, None, self._escalate_message(agent_id, failure_type, task)

        elif action == RecoveryAction.QUARANTINE:
            return False, None, f"QUARANTINED: Agent {agent_id} halted due to {failure_type.value}. Security team notified."

        elif action == RecoveryAction.ABORT:
            self._retry_counts.pop(key, None)
            return False, None, f"ABORTED: Agent {agent_id} aborted due to {failure_type.value}."

        elif action == RecoveryAction.FALLBACK_RESPONSE:
            return True, self._fallback_response(task), "Used fallback response due to goal drift."

        return False, None, "No recovery strategy matched."

    async def _retry(self, key: str, retry_fn: Optional[Callable]) -> tuple[bool, Any, str]:
        count = self._retry_counts.get(key, 0)
        if count >= self.max_retries or retry_fn is None:
            return False, None, f"Max retries ({self.max_retries}) exceeded."
        self._retry_counts[key] = count + 1
        try:
            result = await retry_fn() if asyncio.iscoroutinefunction(retry_fn) else retry_fn()
            self._retry_counts.pop(key, None)
            return True, result, f"Recovered on retry attempt {count + 1}."
        except Exception as e:
            return False, None, f"Retry failed: {str(e)}"

    async def _retry_with_backoff(self, key: str, retry_fn: Optional[Callable]) -> tuple[bool, Any, str]:
        count = self._retry_counts.get(key, 0)
        if count >= self.max_retries or retry_fn is None:
            return False, None, f"Max retries ({self.max_retries}) exceeded after backoff."
        backoff = self.base_backoff * (2 ** count)
        await asyncio.sleep(backoff)
        return await self._retry(key, retry_fn)

    async def _truncate_and_retry(
        self, key: str, retry_fn: Optional[Callable], context: Optional[list]
    ) -> tuple[bool, Any, str]:
        if context:
            original_len = len(context)
            del context[1:max(2, len(context) // 2)]
            truncated_len = len(context)
            msg = f"Context truncated from {original_len} to {truncated_len} messages."
        else:
            msg = "No context to truncate."
        success, result, detail = await self._retry(key, retry_fn)
        return success, result, f"{msg} {detail}"

    def _escalate_message(self, agent_id: str, failure_type: FailureType, task: Optional[str]) -> str:
        return (
            f"ESCALATED TO HUMAN REVIEW: Agent '{agent_id}' produced a potentially hallucinated response "
            f"for task: '{task}'. Failure type: {failure_type.value}. "
            f"Do not use this output without manual verification."
        )

    def _fallback_response(self, task: Optional[str]) -> str:
        return (
            f"Unable to complete task: '{task}'. "
            f"The agent deviated from the original goal. Please rephrase and try again."
        )
