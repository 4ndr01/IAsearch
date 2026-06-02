"""
Mistral AI agent: analyzes live market data (BTC + SP500) and generates structured alerts.
Uses Mistral function calling in an agentic loop.
"""

import json
from datetime import datetime
from mistralai.client.sdk import Mistral
from config import MISTRAL_API_KEY

_client: Mistral | None = None


def _get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=MISTRAL_API_KEY)
    return _client


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "emit_alert",
            "description": (
                "Emit a market alert when you detect something actionable: "
                "significant price movement, trend reversal, or opportunity. "
                "Only call this for genuinely notable findings."
            ),
            "parameters": {
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
                        "description": "Confidence in the analysis (0-100)",
                    },
                },
                "required": ["severity", "asset", "title", "analysis", "recommendation", "confidence"],
            },
        },
    }
]

SYSTEM_PROMPT = """You are a professional financial market AI agent specializing in
Bitcoin (BTC) and the S&P 500 (SPY). Your role is to monitor live market data,
identify significant patterns, and generate actionable alerts.

When analyzing data:
- Flag moves > 2% in 24h as "warning"
- Flag moves > 5% in 24h as "critical"
- Look for divergences between BTC and SPY (risk-on/risk-off correlation)
- Note when BTC and SPY move in opposite directions — often a macro signal
- Be concise and specific — no generic commentary

Always use the emit_alert tool to communicate findings. Generate at least one
summary alert and individual alerts for each notable asset."""


def run_analysis(prices: dict, price_history: list[dict]) -> list[dict]:
    """
    Run the Mistral agent analysis loop.
    Returns a list of alert dicts produced via emit_alert function calls.
    """
    if not MISTRAL_API_KEY:
        return [{
            "severity": "critical",
            "asset": "SYSTEM",
            "title": "MISTRAL_API_KEY manquante",
            "analysis": "Configurez votre clé API dans le fichier .env",
            "recommendation": "Ajoutez MISTRAL_API_KEY=... dans .env",
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

Identify all notable signals and emit alerts using the emit_alert function.
"""

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    alerts = []

    for _ in range(5):  # max 5 agentic turns
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        msg = choice.message

        # Append assistant turn to history
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            break

        # Process each function call
        for tc in msg.tool_calls:
            if tc.function.name == "emit_alert":
                args = json.loads(tc.function.arguments)
                args["generated_at"] = datetime.utcnow().isoformat()
                alerts.append(args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": "Alert recorded.",
            })

        if choice.finish_reason != "tool_calls":
            break

    return alerts
