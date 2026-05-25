import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
ANALYSIS_INTERVAL = int(os.getenv("ANALYSIS_INTERVAL", "300"))
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "2.0"))

CRYPTO_WATCHLIST = [
    {"id": "bitcoin",  "ticker": "BTC", "name": "Bitcoin"},
    {"id": "ethereum", "ticker": "ETH", "name": "Ethereum"},
    {"id": "solana",   "ticker": "SOL", "name": "Solana"},
    {"id": "binancecoin", "ticker": "BNB", "name": "BNB"},
]

ETF_WATCHLIST = [
    {"ticker": "SPY",  "name": "S&P 500 ETF"},
    {"ticker": "QQQ",  "name": "Nasdaq-100 ETF"},
    {"ticker": "GLD",  "name": "Gold ETF"},
    {"ticker": "TLT",  "name": "20y Treasury ETF"},
    {"ticker": "ARKK", "name": "ARK Innovation ETF"},
]
