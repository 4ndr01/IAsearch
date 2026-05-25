"""
Agent IA — Alertes de prix bourse en direct
Crypto (CoinGecko) + ETFs US (Yahoo Finance) + Analyse Claude AI
"""

import time
import sys
from datetime import datetime

from config import (
    ANTHROPIC_API_KEY,
    CHECK_INTERVAL,
    ANALYSIS_INTERVAL,
    ALERT_THRESHOLD,
    CRYPTO_WATCHLIST,
    ETF_WATCHLIST,
)
from data_fetcher import fetch_crypto_prices, fetch_etf_prices
from agent import run_analysis
from alerts import console, render_dashboard, render_alerts


def _check_threshold_alerts(current: dict, previous: dict | None) -> list[str]:
    """Detect assets that crossed the ALERT_THRESHOLD between two checks."""
    triggered = []
    if not previous:
        return triggered
    for ticker, data in current.items():
        prev = previous.get(ticker, {})
        p_now = data.get("price")
        p_prev = prev.get("price")
        if p_now and p_prev and p_prev != 0:
            delta = abs((p_now - p_prev) / p_prev) * 100
            if delta >= ALERT_THRESHOLD:
                direction = "▲" if p_now > p_prev else "▼"
                triggered.append(
                    f"{ticker} {direction} {delta:.2f}% depuis la dernière vérification"
                )
    return triggered


def main() -> None:
    if not ANTHROPIC_API_KEY:
        console.print(
            "[bold red]⚠  ANTHROPIC_API_KEY non configurée.[/bold red]\n"
            "Créez un fichier [bold].env[/bold] à partir de [bold].env.example[/bold] "
            "et ajoutez votre clé Anthropic.\n"
            "L'agent continuera à afficher les prix mais l'analyse IA sera désactivée."
        )
        time.sleep(3)

    console.print("[bold cyan]Démarrage de l'agent...[/bold cyan]")

    price_history: list[dict] = []
    last_crypto: dict = {}
    last_etf: dict = {}
    last_analysis_time = 0.0

    try:
        while True:
            loop_start = time.time()

            # --- Fetch prices ---
            crypto_prices = fetch_crypto_prices(CRYPTO_WATCHLIST)
            etf_prices = fetch_etf_prices(ETF_WATCHLIST)

            # --- Store snapshot for AI context ---
            snapshot = {
                "timestamp": datetime.utcnow().isoformat(),
                "crypto": {
                    k: {"price": v.get("price"), "change_24h": v.get("change_24h")}
                    for k, v in crypto_prices.items() if "error" not in v
                },
                "etf": {
                    k: {"price": v.get("price"), "change_24h": v.get("change_24h")}
                    for k, v in etf_prices.items() if "error" not in v
                },
            }
            price_history.append(snapshot)
            if len(price_history) > 60:
                price_history.pop(0)

            # --- Threshold alerts (fast, no AI) ---
            all_current = {**crypto_prices, **etf_prices}
            all_previous = {**last_crypto, **last_etf}
            threshold_hits = _check_threshold_alerts(all_current, all_previous)
            if threshold_hits:
                for msg in threshold_hits:
                    console.print(f"[bold yellow]⚡ ALERTE SEUIL:[/bold yellow] {msg}")

            last_crypto = crypto_prices
            last_etf = etf_prices

            # --- AI analysis (every ANALYSIS_INTERVAL seconds) ---
            time_since_analysis = loop_start - last_analysis_time
            if time_since_analysis >= ANALYSIS_INTERVAL:
                console.print("[dim]Analyse IA en cours...[/dim]")
                all_prices = {"crypto": crypto_prices, "etf": etf_prices}
                alerts = run_analysis(all_prices, price_history)
                render_alerts(alerts)
                last_analysis_time = time.time()

            # --- Render dashboard ---
            next_analysis_in = max(
                0, int(ANALYSIS_INTERVAL - (time.time() - last_analysis_time))
            )
            render_dashboard(crypto_prices, etf_prices, next_analysis_in)

            # --- Wait until next check ---
            elapsed = time.time() - loop_start
            sleep_time = max(0, CHECK_INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        console.print("\n[bold]Agent arrêté.[/bold]")
        sys.exit(0)


if __name__ == "__main__":
    main()
