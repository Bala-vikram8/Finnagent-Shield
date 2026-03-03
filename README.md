# FinAgent Shield

A production-grade reliability and security framework for AI agents operating in regulated financial environments.

Banks and fintech companies are deploying AI agents to read financial reports, flag compliance issues,
and research securities. The problem is when these agents fail, they fail silently. You get no structured
insight into whether the agent hallucinated a figure, got stuck in a loop, hit a tool timeout, or was
manipulated by a malicious document it read.

In a normal application you get error logs. With AI agents you get nothing useful.
In financial services that is not acceptable.

FinAgent Shield wraps your agents with a three layer protection system.

---

## What It Does

**Layer 1: Failure Classification and Circuit Breaking**
Every agent failure is automatically classified into one of three categories. Operational failures
like tool timeouts and rate limits. Reasoning failures like hallucination, goal drift, and reasoning
loops. Adversarial failures like prompt injection and agent-to-agent manipulation. Each failure type
triggers a specific recovery action instead of blind retrying.

**Layer 2: Adversarial Input Detection**
Every input boundary is scanned before the agent acts on it. User input, tool outputs, and
agent-to-agent messages are all checked for injection patterns. The tool output scanner is the
critical one because indirect injection through documents and API responses is the most dangerous
and least solved attack vector in production agent systems.

**Layer 3: Compliance Audit Logging**
Every decision the agent makes, every failure it hits, and every recovery action it takes is written
to a structured audit trail. Financial companies are legally required to explain automated decisions
to regulators. This framework gives them that out of the box.

---

## Architecture
```
finagent-shield/
├── framework/
│   ├── models.py              Pydantic models for failures, runs, and events
│   ├── failure_classifier.py  Classifies exceptions and responses into failure types
│   ├── circuit_breaker.py     Circuit breaker pattern adapted for agent pipelines
│   ├── injection_detector.py  Scans all input boundaries for injection patterns
│   ├── recovery_strategies.py Maps each failure type to a specific recovery action
│   └── audit_logger.py        Structured SQLite audit log for compliance
├── agents/
│   ├── base_agent.py          AgentShield wrapper you apply to any agent
│   └── financial_agent.py     Example financial research agent using the framework
├── dashboard/
│   └── api.py                 FastAPI monitoring and audit API
├── main.py                    CLI entry point
└── config.py                  Environment configuration
```

---

## Failure Taxonomy

| Category | Failure Type | Recovery Action |
|---|---|---|
| Operational | tool_failure | Retry with exponential backoff |
| Operational | context_overflow | Truncate context and retry |
| Operational | timeout | Retry with exponential backoff |
| Operational | rate_limit | Retry with exponential backoff |
| Reasoning | hallucination | Escalate to human review |
| Reasoning | loop_detected | Abort |
| Reasoning | goal_drift | Fallback response |
| Adversarial | prompt_injection | Quarantine and block |
| Adversarial | indirect_injection | Quarantine and block |
| Adversarial | agent_manipulation | Quarantine and block |

---

## Setup

**Prerequisites**
- Python 3.11 or higher
- Anthropic API key

**Installation**
```bash
git clone https://github.com/yourusername/finagent-shield
cd finagent-shield
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your Anthropic API key to the .env file.
```
ANTHROPIC_API_KEY=your_key_here
```

---

## Running the Project

**Normal financial research task**
```bash
python main.py run
```
Runs the financial research agent against AAPL and JPM. Calls market data,
SEC filing, and compliance tools. Produces a structured analysis report.

**Simulate a direct prompt injection attack**
```bash
python main.py inject-test
```
Tests the input scanner detecting and blocking a direct injection in user input.

**Simulate an indirect tool injection attack**
```bash
python main.py tool-inject-test
```
Tests the tool output scanner catching malicious content returned by an external tool.

**View recent agent runs**
```bash
python main.py runs
```

**View the security and failure report**
```bash
python main.py report
```

**Start the monitoring dashboard**
```bash
python main.py dashboard
```
Opens at http://localhost:8000. Full API docs at http://localhost:8000/docs.

**Dashboard endpoints**
- GET /runs - All recent agent runs with status
- GET /runs/{run_id} - Full audit trail for a specific run
- GET /security/report - Aggregated failure and injection report
- GET /health - Health check

---

## Applying AgentShield to Your Own Agent
```python
from agents.base_agent import AgentShield

shield = AgentShield(agent_id="my-agent")
run = shield.start_run(task="Analyze quarterly earnings for JPM")

if not shield.scan_input(user_input, source="user"):
    return {"blocked": "Injection detected in user input"}

is_safe, clean_output = shield.scan_tool_output("get_filing", raw_tool_output)
if not is_safe:
    return {"blocked": "Indirect injection in tool output"}

failure = shield.check_response(agent_response, task)
if failure:
    success, result, message = await shield.recover(failure_type=failure)

shield.end_run(result=final_output, status="completed")
summary = shield.get_run_summary()
```

---

## Why This Matters for Financial Services

Every company deploying AI agents in finance hits three walls that no existing framework solves.

First they cannot see why their agents fail which means they cannot fix them or explain them to auditors.

Second they have no protection against adversarial documents. A manipulated PDF or API response
can hijack your agent's next action. Scanning at the tool output boundary is the critical gap
nobody is addressing in production agent systems today.

Third they have no audit trail. Regulators can ask at any time what automated decisions were made
and why. Without structured logging you are exposed. FinAgent Shield writes a compliance-ready
audit trail by default on every single run.

---

## Tech Stack

- Python 3.11
- Anthropic Claude API
- FastAPI
- Pydantic v2
- SQLite
- Uvicorn

---

## Contributing

PRs welcome. Priority areas are LLM-based hallucination judge to replace the heuristic classifier,
webhook alerting for critical failures, and Docker deployment configuration.
