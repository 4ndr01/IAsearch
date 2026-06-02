"""
Dashboard Streamlit — Alertes BTC + SP500 avec analyse Mistral AI
"""

import time
import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import CHECK_INTERVAL, ANALYSIS_INTERVAL, ALERT_THRESHOLD, CRYPTO_WATCHLIST, ETF_WATCHLIST, PINECONE_API_KEY
from data_fetcher import fetch_crypto_prices, fetch_etf_prices
from agent import run_analysis
from news_fetcher import fetch_all_news
from rag import index_articles

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agent IA — BTC & SP500",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .alert-critical { background:#3d1a1a; border-left:4px solid #ff4b4b; padding:12px 16px; border-radius:4px; margin:6px 0; }
  .alert-warning  { background:#3d2f0a; border-left:4px solid #ffa500; padding:12px 16px; border-radius:4px; margin:6px 0; }
  .alert-info     { background:#0a2a3d; border-left:4px solid #4b9fff; padding:12px 16px; border-radius:4px; margin:6px 0; }
  .alert-title    { font-weight:700; font-size:15px; margin-bottom:4px; }
  .alert-body     { font-size:13px; color:#ccc; }
  .alert-reco     { font-style:italic; color:#aaa; font-size:12px; margin-top:4px; }
  .alert-meta     { font-size:11px; color:#666; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
for key, default in [
    ("btc_history", []),
    ("spy_history", []),
    ("alerts", []),
    ("last_analysis_time", 0.0),
    ("last_news_time", 0.0),
    ("latest_news", []),
    ("price_history", []),
    ("last_crypto", {}),
    ("last_etf", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Fetch prices ──────────────────────────────────────────────────────────────
crypto_prices = fetch_crypto_prices(CRYPTO_WATCHLIST)
etf_prices = fetch_etf_prices(ETF_WATCHLIST)

now = datetime.datetime.utcnow()

# Record history points
btc_price = crypto_prices.get("BTC", {}).get("price")
spy_price = etf_prices.get("SPY", {}).get("price")
if btc_price:
    st.session_state.btc_history.append({"time": now, "BTC": btc_price})
    if len(st.session_state.btc_history) > 120:
        st.session_state.btc_history.pop(0)
if spy_price:
    st.session_state.spy_history.append({"time": now, "SPY": spy_price})
    if len(st.session_state.spy_history) > 120:
        st.session_state.spy_history.pop(0)

# Snapshot for Mistral context
snapshot = {
    "timestamp": now.isoformat(),
    "crypto": {k: {"price": v.get("price"), "change_24h": v.get("change_24h")} for k, v in crypto_prices.items() if "error" not in v},
    "etf":    {k: {"price": v.get("price"), "change_24h": v.get("change_24h")} for k, v in etf_prices.items() if "error" not in v},
}
st.session_state.price_history.append(snapshot)
if len(st.session_state.price_history) > 60:
    st.session_state.price_history.pop(0)

# Threshold alerts (fast, no AI)
threshold_alerts = []
all_current  = {**crypto_prices, **etf_prices}
all_previous = {**st.session_state.last_crypto, **st.session_state.last_etf}
if all_previous:
    for ticker, data in all_current.items():
        prev = all_previous.get(ticker, {})
        p_now, p_prev = data.get("price"), prev.get("price")
        if p_now and p_prev and p_prev != 0:
            delta = abs((p_now - p_prev) / p_prev) * 100
            if delta >= ALERT_THRESHOLD:
                direction = "▲" if p_now > p_prev else "▼"
                threshold_alerts.append(f"{ticker} {direction} {delta:.2f}% depuis la dernière vérification")
st.session_state.last_crypto = crypto_prices
st.session_state.last_etf    = etf_prices

# News fetch + indexation (every 30 min)
NEWS_INTERVAL = 1800
_news_just_fetched = False
if time.time() - st.session_state.last_news_time >= NEWS_INTERVAL:
    with st.spinner("Récupération des actualités…"):
        try:
            articles = fetch_all_news()
            st.session_state.latest_news = articles[:20]
            if PINECONE_API_KEY:
                index_articles(articles)
        except Exception:
            st.session_state.latest_news = []
        st.session_state.last_news_time = time.time()
        _news_just_fetched = True

# AI analysis (every ANALYSIS_INTERVAL)
time_since = time.time() - st.session_state.last_analysis_time
if time_since >= ANALYSIS_INTERVAL:
    with st.spinner("Analyse Mistral AI en cours…"):
        new_alerts = run_analysis({"crypto": crypto_prices, "etf": etf_prices}, st.session_state.price_history)
    st.session_state.alerts = new_alerts + st.session_state.alerts
    if len(st.session_state.alerts) > 50:
        st.session_state.alerts = st.session_state.alerts[:50]
    st.session_state.last_analysis_time = time.time()

next_analysis_in = max(0, int(ANALYSIS_INTERVAL - (time.time() - st.session_state.last_analysis_time)))

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"## 📈 Agent IA — BTC & S&P 500")
st.caption(f"UTC {now.strftime('%Y-%m-%d %H:%M:%S')}  |  Prochaine analyse Mistral dans **{next_analysis_in}s**  |  Rafraîchissement toutes les {CHECK_INTERVAL}s")

if threshold_alerts:
    for msg in threshold_alerts:
        st.warning(f"⚡ Alerte seuil : {msg}")

# ── Metric cards ──────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

btc  = crypto_prices.get("BTC", {})
spy  = etf_prices.get("SPY", {})

with col1:
    p = btc.get("price")
    c = btc.get("change_24h")
    st.metric("Bitcoin (BTC)", f"${p:,.2f}" if p else "N/A", f"{c:+.2f}% (24h)" if c is not None else None)

with col2:
    p = spy.get("price")
    c = spy.get("change_24h")
    st.metric("S&P 500 — SPY", f"${p:,.2f}" if p else "N/A", f"{c:+.2f}% (24h)" if c is not None else None)

with col3:
    nb = len([a for a in st.session_state.alerts if a.get("severity") == "critical"])
    st.metric("Alertes critiques", nb)

with col4:
    nb = len([a for a in st.session_state.alerts if a.get("severity") == "warning"])
    st.metric("Alertes warning", nb)

st.divider()

# ── News panel ───────────────────────────────────────────────────────────────
st.divider()
st.subheader(f"Dernières actualités ")

if st.session_state.latest_news:
    col_a, col_b = st.columns(2)
    for i, article in enumerate(st.session_state.latest_news[:10]):
        tags = " ".join(f"`{t}`" for t in article.get("tags", []))
        col = col_a if i % 2 == 0 else col_b
        col.markdown(
            f"**[{article['source']}]** {tags}  \n"
            f"[{article['title']}]({article['url']})  \n"
            f"<span style='color:#888;font-size:12px'>{article.get('published','')[:10]}</span>",
            unsafe_allow_html=True,
        )
else:
    st.info("Récupération des actualités en cours…")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if _news_just_fetched:
    st.rerun()
time.sleep(CHECK_INTERVAL)
st.rerun()

