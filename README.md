# FinAgent Shield

A production-grade reliability and security framework for AI agents operating in regulated financial environments.

## What Problem This Solves

Banks, fintech companies, and trading firms are deploying AI agents to read financial reports, flag compliance issues, and research securities. The problem: when these agents fail, they fail silently. You get no structured insight into whether the agent hallucinated a figure, got stuck in a loop, hit a tool timeout, or was manipulated by a malicious document it read.

In a normal app, you get error logs. With AI agents, you get nothing useful. In finance, that is not acceptable.

FinAgent Shield wraps your agents with a three-layer protection system:

1. Failure classification and circuit breaking
2. Adversarial input detection (direct injection, indirect via tool output, agent-to-agent)
3. Structured compliance audit logging

## Architecture

```
finagent-shield/
├── framework/
│   ├── models.py              Pydantic models for failures, runs, events
│   ├── failure_classifier.py  Classifies failures into operational/reasoning/adversarial
│   ├── circuit_breaker.py     Circuit breaker pattern adapted for agent pipelines
│   ├── injection_detector.py  Detects prompt injection at every input boundary
│   ├── recovery_strategies.py Maps failure types to recovery actions
│   └── audit_logger.py        Structured SQLite audit log for compliance
├── agents/
│   ├── base_agent.py          AgentShield wrapper (apply to any agent)
│   └── financial_agent.py     Example financial research agent
├── dashboard/
│   └── api.py                 FastAPI monitoring and audit API
├── main.py                    CLI entry point
├── config.py                  Environment configuration
└── requirements.txt
```

## Failure Taxonomy

### Operational Failures
- TOOL_FAILURE: External API or tool call failed
- CONTEXT_OVERFLOW: Agent hit context window limit
- TIMEOUT: Execution exceeded time limit
- RATE_LIMIT: External API rate limit hit

### Reasoning Failures
- HALLUCINATION: Response contains suspicious numerical patterns or unsupported claims
- LOOP_DETECTED: Agent is repeating itself in a reasoning loop
- GOAL_DRIFT: Agent response does not align with the original task

### Adversarial Failures (Financial-Specific)
- PROMPT_INJECTION: Direct injection in user input
- INDIRECT_INJECTION: Malicious content returned by a tool (e.g. manipulated SEC filing)
- AGENT_MANIPULATION: One agent sending malicious instructions to another

## Recovery Actions Per Failure

| Failure Type | Recovery Action |
|---|---|
| Tool failure | Retry with exponential backoff |
| Context overflow | Truncate context and retry |
| Rate limit | Retry with backoff |
| Hallucination | Escalate to human review |
| Loop detected | Abort |
| Goal drift | Fallback response |
| Any injection | Quarantine and block |

## Setup

### Prerequisites

- Python 3.11+
- Anthropic API key

### Installation

```bash
git clone https://github.com/yourusername/finagent-shield
cd finagent-shield
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_key_here
```

## Running the Project

### Run a normal financial research task

```bash
python main.py run
```

This runs the financial research agent against AAPL and JPM, pulling market data, SEC filings, and compliance flags.

### Simulate a prompt injection attack

```bash
python main.py inject-test
```

Tests the input scanner catching a direct injection attempt in user input.

### Simulate an indirect tool injection attack

```bash
python main.py tool-inject-test
```

Tests the tool output scanner catching malicious content returned by a tool.

### View recent agent runs

```bash
python main.py runs
```

### View the security report

```bash
python main.py report
```

### Start the monitoring dashboard

```bash
python main.py dashboard
```

Then open http://localhost:8000/docs for the full API.

Available endpoints:
- GET /runs - All recent agent runs
- GET /runs/{run_id} - Full audit trail for a specific run
- GET /security/report - Aggregated security and failure report
- GET /health - Health check

## Using AgentShield in Your Own Agent

```python
from agents.base_agent import AgentShield

shield = AgentShield(agent_id="my-agent")
run = shield.start_run(task="Analyze quarterly earnings for JPM")

# Scan user input before processing
if not shield.scan_input(user_input, source="user"):
    return {"blocked": "Injection detected in user input"}

# Scan tool outputs before feeding back to the agent
is_safe, clean_output = shield.scan_tool_output("get_filing", raw_tool_output)
if not is_safe:
    return {"blocked": "Indirect injection in tool output"}

# Check agent responses for reasoning failures
failure = shield.check_response(agent_response, task)
if failure:
    success, result, message = await shield.recover(failure_type=failure)

# Handle exceptions with automatic classification
try:
    result = call_agent()
except Exception as e:
    failure_type, description = shield.handle_exception(e)
    await shield.recover(failure_type=failure_type, retry_fn=lambda: call_agent())

# Always close the run
shield.end_run(result=final_output, status="completed")

# Get the full audit trail
summary = shield.get_run_summary()
```

## Why This Matters for Financial Services

Financial companies deploying AI agents face three problems no existing framework solves:

1. They cannot see why their agents fail, which means they cannot fix them or explain them to auditors.

2. They have no protection against adversarial documents. A manipulated PDF in your RAG pipeline can hijack your agent's next action. Nobody is scanning for this at the tool boundary.

3. They have no audit trail. Regulators can ask at any time what automated decisions were made and why. Without structured logging you are exposed.

FinAgent Shield addresses all three directly.

## Tech Stack

- Python 3.11+
- Anthropic Claude API (claude-sonnet-4-20250514)
- FastAPI for monitoring dashboard
- Pydantic v2 for data models
- SQLite for audit persistence
- Uvicorn for serving the dashboard

## Contributing

PRs welcome. Focus areas:
- Additional financial tool simulators
- LLM-based hallucination judge (replacing heuristic classifier)
- Webhook support for alerting on critical failures
- Docker and Kubernetes deployment configs
