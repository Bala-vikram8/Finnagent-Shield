import re
from typing import List
from framework.models import InjectionScanResult


DIRECT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?",
    r"disregard\s+(?:your\s+)?(?:previous|above|system)\s+(?:instructions?|prompt)",
    r"you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)",
    r"new\s+(?:system\s+)?(?:prompt|instruction|role|persona)",
    r"forget\s+(?:everything|all|your\s+instructions?)",
    r"act\s+as\s+(?:if\s+you\s+are\s+)?(?:an?\s+)?(?:unrestricted|evil|jailbreak)",
    r"do\s+not\s+follow\s+(?:your\s+)?(?:guidelines?|rules?|instructions?)",
    r"\[\[.*?(inject|override|system|prompt).*?\]\]",
    r"<\s*(?:system|override|inject)\s*>",
]

INDIRECT_INJECTION_PATTERNS = [
    r"if\s+you\s+(?:are\s+)?(?:reading|processing|analyzing)\s+this",
    r"hidden\s+(?:message|instruction|command)",
    r"(?:as|when)\s+(?:an?\s+)?ai\s+(?:reading|processing)",
    r"note\s+to\s+(?:the\s+)?(?:ai|model|assistant|llm)",
    r"ai\s+(?:instruction|command|override)",
    r"base64\s*(?:encoded|decode)",
    r"<!--.*?(?:inject|override|instruction).*?-->",
]

FINANCIAL_SUSPICIOUS_PATTERNS = [
    r"transfer\s+(?:all\s+)?funds?\s+to",
    r"(?:wire|send)\s+\$[\d,]+\s+to",
    r"bypass\s+(?:compliance|kyc|aml|audit)",
    r"do\s+not\s+(?:log|record|report)\s+this",
    r"delete\s+(?:all\s+)?(?:logs?|records?|audit)",
    r"approve\s+(?:this\s+)?(?:transaction|transfer)\s+without",
]


class InjectionDetector:
    def __init__(self, sensitivity: str = "high"):
        self.sensitivity = sensitivity
        self.all_patterns = (
            DIRECT_INJECTION_PATTERNS
            + INDIRECT_INJECTION_PATTERNS
            + FINANCIAL_SUSPICIOUS_PATTERNS
        )

    def scan(self, content: str, source: str = "unknown") -> InjectionScanResult:
        detected: List[str] = []
        content_lower = content.lower()

        for pattern in DIRECT_INJECTION_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                detected.append(f"Direct injection pattern: {pattern[:50]}")

        for pattern in INDIRECT_INJECTION_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                detected.append(f"Indirect injection pattern: {pattern[:50]}")

        for pattern in FINANCIAL_SUSPICIOUS_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                detected.append(f"Financial manipulation pattern: {pattern[:50]}")

        is_malicious = len(detected) > 0
        confidence = min(1.0, len(detected) * 0.35)

        if is_malicious:
            sanitized = self._sanitize(content)
            recommendation = (
                f"BLOCK: Malicious content detected from source '{source}'. "
                f"Quarantine and escalate to security team."
            )
        else:
            sanitized = content
            recommendation = "PASS: Content appears safe to process."

        return InjectionScanResult(
            is_malicious=is_malicious,
            confidence=confidence,
            detected_patterns=detected,
            sanitized_content=sanitized,
            recommendation=recommendation,
        )

    def _sanitize(self, content: str) -> str:
        sanitized = content
        for pattern in self.all_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE | re.DOTALL)
        return sanitized

    def scan_tool_output(self, tool_name: str, output: str) -> InjectionScanResult:
        result = self.scan(output, source=f"tool:{tool_name}")
        if result.is_malicious:
            result.recommendation = (
                f"CRITICAL: Tool '{tool_name}' returned potentially malicious content. "
                f"This is an indirect injection attempt via tool output."
            )
        return result

    def scan_agent_message(self, from_agent: str, to_agent: str, message: str) -> InjectionScanResult:
        result = self.scan(message, source=f"agent:{from_agent}")
        if result.is_malicious:
            result.recommendation = (
                f"CRITICAL: Agent '{from_agent}' sent suspicious message to '{to_agent}'. "
                f"Agent-to-agent manipulation attempt detected."
            )
        return result
