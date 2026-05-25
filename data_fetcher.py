"""
Price fetching module.
- Crypto + ETFs: Yahoo Finance (no API key required)
- Falls back to demo/mock mode when network is unavailable
"""

import random
import time
import yfinance as yf
from datetime import datetime


# --- Mock prices for offline/demo mode ---
_MOCK_SEED: dict[str, float] = {
    "BTC": 68_250.00, "ETH": 3_640.00, "SOL": 172.50, "BNB": 605.00,
    "SPY": 528.40,    "QQQ": 449.10,   "GLD": 232.80, "TLT": 93.40, "ARKK": 48.20,
}
_mock_prices: dict[str, float] = dict(_MOCK_SEED)


def _random_walk(base: float, volatility: float = 0.003) -> float:
    """Simulate a small random price move."""
    return round(base * (1 + random.gauss(0, volatility)), 4)


def _mock_ticker(ticker: str, name: str) -> dict:
    """Return simulated price data when real API is unavailable."""
    prev = _mock_prices.get(ticker, _MOCK_SEED.get(ticker, 100.0))
    current = _random_walk(prev)
    _mock_prices[ticker] = current
    seed = _MOCK_SEED.get(ticker, 100.0)
    change_24h = round(((current - seed) / seed) * 100, 2)
    return {
        "name": name,
        "price": current,
        "change_24h": change_24h,
        "prev_close": round(prev, 4),
        "source": "DEMO (données simulées)",
        "timestamp": datetime.utcnow().isoformat(),
    }


def _fetch_yf_ticker(yf_symbol: str) -> dict | None:
    """
    Fetch real price data from Yahoo Finance.
    Returns None if the fetch fails (network issue, blocked host, etc.).
    """
    try:
        tk = yf.Ticker(yf_symbol)
        info = tk.fast_info
        price = info.last_price
        if not price:
            return None
        prev_close = info.previous_close
        change_pct = None
        if price and prev_close and prev_close != 0:
            change_pct = round(((price - prev_close) / prev_close) * 100, 2)
        return {
            "price": round(float(price), 4),
            "change_24h": change_pct,
            "prev_close": round(float(prev_close), 4) if prev_close else None,
            "source": "Yahoo Finance",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception:
        return None


def fetch_crypto_prices(crypto_list: list[dict]) -> dict:
    """Fetch live crypto prices (Yahoo Finance). Falls back to demo mode."""
    result = {}
    for item in crypto_list:
        yf_symbol = item.get("yf_symbol", f"{item['ticker']}-USD")
        data = _fetch_yf_ticker(yf_symbol)
        if data:
            data["name"] = item["name"]
            result[item["ticker"]] = data
        else:
            result[item["ticker"]] = _mock_ticker(item["ticker"], item["name"])
    return result


def fetch_etf_prices(etf_list: list[dict]) -> dict:
    """Fetch ETF prices (Yahoo Finance). Falls back to demo mode."""
    result = {}
    for item in etf_list:
        data = _fetch_yf_ticker(item["ticker"])
        if data:
            data["name"] = item["name"]
            result[item["ticker"]] = data
        else:
            result[item["ticker"]] = _mock_ticker(item["ticker"], item["name"])
    return result
