"""
Claude AI agent: analyzes live market data and generates structured alerts.
Uses tool-use agentic loop so Claude can request additional data if needed.
"""

import json
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


TOOLS = [
    {
        "name": "emit_alert",
        "description": (
            "Emit a market alert when you detect something actionable: "
            "significant price movement, trend reversal, or opportunity. "
            "Only call this for genuinely notable findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "description": "info=FYI, warning=notable move, critical=sharp move or risk",
                },
                "asset": {"type": "string", "description": "Ticker symbol, e.g. BTC, SPY"},
                "title": {"type": "string", "description": "Short alert title (max 60 chars)"},
                "analysis": {
                    "type": "string",
                    "description": "2-4 sentence technical and contextual analysis",
                },
                "recommendation": {
                    "type": "string",
                    "description": "Actionable suggestion: watch, buy dip, take profit, etc.",
                },
                "confidence": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Confidence in the analysis (0-100)",
                },
            },
            "required": ["severity", "asset", "title", "analysis", "recommendation", "confidence"],
        },
    }
]

SYSTEM_PROMPT = """You are a professional financial market AI agent specializing in
cryptocurrencies and US ETFs. Your role is to monitor live market data, identify
significant patterns, and generate actionable alerts.

When analyzing data:
- Flag moves > 2% in 24h as "warning"
- Flag moves > 5% in 24h as "critical"
- Look for divergences between correlated assets (e.g., BTC vs ETH, SPY vs QQQ)
- Note macro context (Gold vs bonds, risk-on vs risk-off signals)
- Be concise and specific — no generic commentary

Always use the emit_alert tool to communicate findings. Generate at least one
summary alert and individual alerts for notable assets.
"""


def run_analysis(prices: dict, price_history: list[dict]) -> list[dict]:
    """
    Run the Claude agent analysis loop.
    Returns a list of alert dicts produced via emit_alert tool calls.
    """
    if not ANTHROPIC_API_KEY:
        return [{
            "severity": "critical",
            "asset": "SYSTEM",
            "title": "ANTHROPIC_API_KEY manquante",
            "analysis": "Configurez votre clé API dans le fichier .env",
            "recommendation": "Ajoutez ANTHROPIC_API_KEY=sk-ant-... dans .env",
            "confidence": 100,
        }]

    client = _get_client()

    recent_snapshots = price_history[-10:] if len(price_history) > 10 else price_history

    user_message = f"""
Analyze the following live market data and generate alerts.

=== CURRENT PRICES (UTC {datetime.utcnow().strftime('%H:%M:%S')}) ===
{json.dumps(prices, indent=2)}

=== RECENT PRICE SNAPSHOTS (last {len(recent_snapshots)} checks) ===
{json.dumps(recent_snapshots, indent=2)}

Identify all notable signals and emit alerts using the emit_alert tool.
"""

    messages = [{"role": "user", "content": user_message}]
    alerts = []

    for _ in range(5):  # max 5 agentic turns
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "emit_alert":
                alert = dict(block.input)
                alert["generated_at"] = datetime.utcnow().isoformat()
                alerts.append(alert)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Alert recorded.",
                })

        if response.stop_reason == "end_turn" or not tool_results:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return alerts
