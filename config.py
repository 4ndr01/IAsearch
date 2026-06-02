import os
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_AGENT_ID = os.getenv("MISTRAL_AGENT_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
ANALYSIS_INTERVAL = int(os.getenv("ANALYSIS_INTERVAL", "900"))
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "2.0"))

CRYPTO_WATCHLIST = [
    {"id": "bitcoin", "ticker": "BTC", "name": "Bitcoin"},
]

ETF_WATCHLIST = [
    {"ticker": "SPY", "name": "S&P 500 ETF"},
]
