import time
from typing import Dict
from framework.models import CircuitBreakerState, FailureType, FailureSeverity


CRITICAL_FAILURES = {
    FailureType.PROMPT_INJECTION,
    FailureType.INDIRECT_INJECTION,
    FailureType.AGENT_MANIPULATION,
}

HIGH_FAILURES = {
    FailureType.HALLUCINATION,
    FailureType.LOOP_DETECTED,
}


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,
        half_open_attempts: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_attempts = half_open_attempts

        self._states: Dict[str, CircuitBreakerState] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._half_open_attempts: Dict[str, int] = {}

    def get_state(self, agent_id: str) -> CircuitBreakerState:
        state = self._states.get(agent_id, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.OPEN:
            last_fail = self._last_failure_time.get(agent_id, 0)
            if time.time() - last_fail >= self.recovery_timeout:
                self._states[agent_id] = CircuitBreakerState.HALF_OPEN
                self._half_open_attempts[agent_id] = 0
                return CircuitBreakerState.HALF_OPEN

        return state

    def is_open(self, agent_id: str) -> bool:
        return self.get_state(agent_id) == CircuitBreakerState.OPEN

    def record_failure(
        self,
        agent_id: str,
        failure_type: FailureType,
        severity: FailureSeverity,
    ) -> CircuitBreakerState:
        if failure_type in CRITICAL_FAILURES:
            self._trip(agent_id)
            return CircuitBreakerState.OPEN

        if severity == FailureSeverity.CRITICAL:
            self._trip(agent_id)
            return CircuitBreakerState.OPEN

        self._failure_counts[agent_id] = self._failure_counts.get(agent_id, 0) + 1
        self._last_failure_time[agent_id] = time.time()

        if self._failure_counts[agent_id] >= self.failure_threshold:
            self._trip(agent_id)
            return CircuitBreakerState.OPEN

        return self.get_state(agent_id)

    def record_success(self, agent_id: str):
        state = self.get_state(agent_id)
        if state == CircuitBreakerState.HALF_OPEN:
            attempts = self._half_open_attempts.get(agent_id, 0) + 1
            self._half_open_attempts[agent_id] = attempts
            if attempts >= self.half_open_attempts:
                self._reset(agent_id)
        elif state == CircuitBreakerState.CLOSED:
            self._failure_counts[agent_id] = max(0, self._failure_counts.get(agent_id, 0) - 1)

    def _trip(self, agent_id: str):
        self._states[agent_id] = CircuitBreakerState.OPEN
        self._last_failure_time[agent_id] = time.time()

    def _reset(self, agent_id: str):
        self._states[agent_id] = CircuitBreakerState.CLOSED
        self._failure_counts[agent_id] = 0
        self._half_open_attempts[agent_id] = 0

    def get_stats(self, agent_id: str) -> dict:
        return {
            "state": self.get_state(agent_id).value,
            "failure_count": self._failure_counts.get(agent_id, 0),
            "last_failure": self._last_failure_time.get(agent_id),
        }
