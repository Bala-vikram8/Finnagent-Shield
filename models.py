from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class FailureType(str, Enum):
    TOOL_FAILURE = "tool_failure"
    CONTEXT_OVERFLOW = "context_overflow"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    HALLUCINATION = "hallucination"
    LOOP_DETECTED = "loop_detected"
    GOAL_DRIFT = "goal_drift"
    PROMPT_INJECTION = "prompt_injection"
    INDIRECT_INJECTION = "indirect_injection"
    AGENT_MANIPULATION = "agent_manipulation"
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(str, Enum):
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    TRUNCATE_CONTEXT = "truncate_context"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    QUARANTINE = "quarantine"
    ABORT = "abort"
    FALLBACK_RESPONSE = "fallback_response"


class FailureEvent(BaseModel):
    event_id: str = ""
    timestamp: str = ""
    agent_id: str
    failure_type: FailureType
    severity: FailureSeverity
    description: str
    raw_error: Optional[str] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    recovery_action: Optional[RecoveryAction] = None
    recovery_successful: Optional[bool] = None
    post_mortem: Optional[str] = None

    def model_post_init(self, __context):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class AgentRun(BaseModel):
    run_id: str = ""
    agent_id: str
    task: str
    status: str = "running"
    start_time: str = ""
    end_time: Optional[str] = None
    failure_events: List[FailureEvent] = []
    result: Optional[str] = None
    total_tokens: int = 0

    def model_post_init(self, __context):
        if not self.run_id:
            self.run_id = str(uuid.uuid4())
        if not self.start_time:
            self.start_time = datetime.utcnow().isoformat()


class InjectionScanResult(BaseModel):
    is_malicious: bool
    confidence: float
    detected_patterns: List[str]
    sanitized_content: Optional[str] = None
    recommendation: str


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
