import anthropic
import json
import random
import asyncio
from typing import Optional
from agents.base_agent import AgentShield
from config import ANTHROPIC_API_KEY, MODEL


SIMULATED_MARKET_DATA = {
    "AAPL": {"price": 189.50, "pe_ratio": 28.4, "market_cap": "2.94T", "revenue_growth": "0.9%"},
    "MSFT": {"price": 415.20, "pe_ratio": 35.1, "market_cap": "3.08T", "revenue_growth": "17.6%"},
    "JPM": {"price": 198.30, "pe_ratio": 11.2, "market_cap": "571B", "revenue_growth": "21.3%"},
    "GS": {"price": 495.10, "pe_ratio": 14.8, "market_cap": "166B", "revenue_growth": "8.2%"},
    "DEFAULT": {"price": 100.00, "pe_ratio": 15.0, "market_cap": "50B", "revenue_growth": "5.0%"},
}

SIMULATED_FILINGS = {
    "AAPL": "Apple Inc Q4 2024 10-K: Total revenue $391.04B, Net income $93.74B. Risk factors include supply chain concentration and regulatory pressures in EU.",
    "MSFT": "Microsoft Corp Q4 2024 10-K: Total revenue $245.1B, cloud segment Azure grew 29% YoY. AI integration across all product lines accelerating.",
    "JPM": "JPMorgan Chase Q3 2024 10-Q: Net revenue $42.7B, provisions for credit losses $3.1B. CET1 ratio 15.3%, above regulatory minimum.",
    "GS": "Goldman Sachs Q3 2024 10-Q: Net revenues $12.7B, FICC net revenues $2.96B. Asset management AUM reached $2.8T.",
    "DEFAULT": "Latest SEC filing: Revenue growth consistent with sector average. No material adverse events reported.",
}

TOOLS = [
    {
        "name": "get_market_data",
        "description": "Retrieves current market data for a stock ticker including price, P/E ratio, market cap, and revenue growth.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol e.g. AAPL"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_sec_filing",
        "description": "Retrieves the latest SEC filing summary for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "check_compliance_flags",
        "description": "Checks if a company has any active regulatory compliance flags or sanctions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"}
            },
            "required": ["ticker"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    ticker = tool_input.get("ticker", "DEFAULT").upper()

    if tool_name == "get_market_data":
        data = SIMULATED_MARKET_DATA.get(ticker, SIMULATED_MARKET_DATA["DEFAULT"])
        return json.dumps({"ticker": ticker, **data})

    elif tool_name == "get_sec_filing":
        filing = SIMULATED_FILINGS.get(ticker, SIMULATED_FILINGS["DEFAULT"])
        return filing

    elif tool_name == "check_compliance_flags":
        flags = []
        if ticker in ["XYZ", "BAD"]:
            flags = ["OFAC sanctions match", "AML investigation pending"]
        return json.dumps({"ticker": ticker, "flags": flags, "status": "FLAGGED" if flags else "CLEAR"})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class FinancialResearchAgent:
    def __init__(self):
        self.agent_id = "financial-research-agent-v1"
        self.shield = AgentShield(agent_id=self.agent_id)
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.system_prompt = """You are a financial research analyst AI. Your job is to:
1. Retrieve market data and SEC filings for requested companies
2. Analyze the financial health and risk profile
3. Produce a structured research report with factual data only
4. Flag any compliance or regulatory concerns

Important rules:
- Only report numbers retrieved from tools, never invent figures
- Always cite the data source for each claim
- Flag uncertainty explicitly if data is unavailable
- Never recommend buy/sell, only provide factual analysis"""

    async def run(self, task: str, inject_test: Optional[str] = None) -> dict:
        print(f"\n{'='*60}")
        print(f"FINAGENT SHIELD: Starting agent run")
        print(f"Task: {task}")
        print(f"{'='*60}")

        run = self.shield.start_run(task)

        if self.shield.is_circuit_open():
            self.shield.end_run(status="blocked")
            return {
                "status": "blocked",
                "reason": "Circuit breaker is open. Too many recent failures. Agent is cooling down.",
                "run_id": run.run_id,
            }

        input_to_scan = inject_test if inject_test else task
        if not self.shield.scan_input(input_to_scan, source="user_input"):
            self.shield.end_run(status="blocked")
            return {
                "status": "blocked",
                "reason": "Input blocked due to detected injection attempt.",
                "run_id": run.run_id,
            }

        messages = [{"role": "user", "content": task}]
        result = None
        max_iterations = 10

        for iteration in range(max_iterations):
            print(f"\n[Iteration {iteration + 1}] Calling Claude...")
            try:
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=self.system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
            except Exception as e:
                failure_type, description = self.shield.handle_exception(e)
                print(f"[ERROR] {description}")
                success, recovered_result, msg = await self.shield.recover(
                    failure_type=failure_type,
                    retry_fn=None,
                )
                self.shield.end_run(status="failed")
                return {"status": "failed", "reason": msg, "run_id": run.run_id}

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        result = block.text

                failure = self.shield.check_response(result or "", task)
                if failure:
                    print(f"[WARNING] Response quality failure detected: {failure.value}")
                    success, recovered_result, msg = await self.shield.recover(failure_type=failure)
                    if not success:
                        self.shield.end_run(result=msg, status="escalated")
                        return {"status": "escalated", "reason": msg, "run_id": run.run_id}
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        print(f"[TOOL] Calling: {block.name} with {block.input}")
                        raw_output = execute_tool(block.name, block.input)

                        is_safe, sanitized_output = self.shield.scan_tool_output(block.name, raw_output)
                        if not is_safe:
                            print(f"[SECURITY] Tool output from {block.name} flagged as malicious!")
                            self.shield.end_run(status="blocked")
                            return {
                                "status": "blocked",
                                "reason": f"Indirect injection detected in tool output from {block.name}",
                                "run_id": run.run_id,
                            }

                        print(f"[TOOL RESULT] {sanitized_output[:100]}...")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": sanitized_output,
                        })

                messages.append({"role": "user", "content": tool_results})

        self.shield.end_run(result=result, status="completed")
        summary = self.shield.get_run_summary()

        return {
            "status": "completed",
            "result": result,
            "run_id": run.run_id,
            "failure_count": len(summary.get("failures", [])) if summary else 0,
            "injection_attempts": len(summary.get("injections", [])) if summary else 0,
        }
