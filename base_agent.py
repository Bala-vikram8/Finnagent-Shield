import asyncio
from datetime import datetime
from typing import Optional, Callable, Any
from framework.models import AgentRun, FailureEvent, FailureType
from framework.failure_classifier import FailureClassifier
from framework.circuit_breaker import CircuitBreaker
from framework.injection_detector import InjectionDetector
from framework.recovery_strategies import RecoveryStrategies
from framework.audit_logger import AuditLogger


_circuit_breaker = CircuitBreaker()
_recovery = RecoveryStrategies()
_audit = AuditLogger()


class AgentShield:
    """
    Wraps any agent execution with:
    - Failure classification and circuit breaking
    - Prompt injection detection (direct, indirect, agent-to-agent)
    - Recovery strategies per failure type
    - Structured audit logging for compliance
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.classifier = FailureClassifier()
        self.injector = InjectionDetector()
        self.current_run: Optional[AgentRun] = None

    def start_run(self, task: str) -> AgentRun:
        self.current_run = AgentRun(agent_id=self.agent_id, task=task)
        _audit.log_run_start(self.current_run)
        return self.current_run

    def end_run(self, result: Optional[str] = None, status: str = "completed"):
        if self.current_run:
            self.current_run.result = result
            self.current_run.status = status
            _audit.log_run_end(self.current_run)

    def scan_input(self, content: str, source: str = "user") -> bool:
        result = self.injector.scan(content, source=source)
        if result.is_malicious and self.current_run:
            _audit.log_injection(
                run_id=self.current_run.run_id,
                agent_id=self.agent_id,
                source=source,
                confidence=result.confidence,
                patterns=result.detected_patterns,
                recommendation=result.recommendation,
            )
            self._log_failure(
                FailureType.PROMPT_INJECTION,
                description=result.recommendation,
                raw_error=str(result.detected_patterns),
            )
        return not result.is_malicious

    def scan_tool_output(self, tool_name: str, output: str) -> tuple[bool, str]:
        result = self.injector.scan_tool_output(tool_name, output)
        if result.is_malicious and self.current_run:
            _audit.log_injection(
                run_id=self.current_run.run_id,
                agent_id=self.agent_id,
                source=f"tool:{tool_name}",
                confidence=result.confidence,
                patterns=result.detected_patterns,
                recommendation=result.recommendation,
            )
            self._log_failure(
                FailureType.INDIRECT_INJECTION,
                description=result.recommendation,
            )
        return not result.is_malicious, result.sanitized_content or output

    def scan_agent_message(self, from_agent: str, message: str) -> tuple[bool, str]:
        result = self.injector.scan_agent_message(from_agent, self.agent_id, message)
        if result.is_malicious and self.current_run:
            _audit.log_injection(
                run_id=self.current_run.run_id,
                agent_id=self.agent_id,
                source=f"agent:{from_agent}",
                confidence=result.confidence,
                patterns=result.detected_patterns,
                recommendation=result.recommendation,
            )
            self._log_failure(
                FailureType.AGENT_MANIPULATION,
                description=result.recommendation,
            )
        return not result.is_malicious, result.sanitized_content or message

    def check_response(self, response: str, task: str) -> Optional[FailureType]:
        result = self.classifier.classify_response(response, task)
        if result:
            failure_type, description = result
            self._log_failure(failure_type, description=description)
            return failure_type
        _circuit_breaker.record_success(self.agent_id)
        return None

    def handle_exception(self, error: Exception) -> tuple[FailureType, str]:
        failure_type, description = self.classifier.classify_exception(error)
        severity = self.classifier.get_severity(failure_type)
        self._log_failure(failure_type, description=description, raw_error=str(error))
        _circuit_breaker.record_failure(self.agent_id, failure_type, severity)
        return failure_type, description

    def is_circuit_open(self) -> bool:
        return _circuit_breaker.is_open(self.agent_id)

    async def recover(
        self,
        failure_type: FailureType,
        retry_fn: Optional[Callable] = None,
        context: Optional[list] = None,
    ) -> tuple[bool, Any, str]:
        success, result, message = await _recovery.execute_recovery(
            agent_id=self.agent_id,
            failure_type=failure_type,
            retry_fn=retry_fn,
            context=context,
            task=self.current_run.task if self.current_run else None,
        )
        if self.current_run and self.current_run.failure_events:
            last_event = self.current_run.failure_events[-1]
            last_event.recovery_action = _recovery.get_recovery_action(failure_type)
            last_event.recovery_successful = success
            last_event.post_mortem = message
            _audit.log_failure(self.current_run.run_id, last_event)
        return success, result, message

    def _log_failure(self, failure_type: FailureType, description: str, raw_error: Optional[str] = None):
        severity = self.classifier.get_severity(failure_type)
        event = FailureEvent(
            agent_id=self.agent_id,
            failure_type=failure_type,
            severity=severity,
            description=description,
            raw_error=raw_error,
        )
        if self.current_run:
            self.current_run.failure_events.append(event)
            _audit.log_failure(self.current_run.run_id, event)

    def get_run_summary(self) -> Optional[dict]:
        if self.current_run:
            return _audit.get_run_summary(self.current_run.run_id)
        return None
