"""Terminal display: live dashboard + alert history using Rich."""

from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

console = Console()

SEVERITY_STYLE = {
    "info":     ("cyan",   "ℹ"),
    "warning":  ("yellow", "⚠"),
    "critical": ("red bold", "🚨"),
}

_alert_history: list[dict] = []


def _fmt_price(val: float | None) -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    if val >= 1_000:
        return f"[white]${val:,.2f}[/white]"
    return f"[white]${val:.4f}[/white]"


def _fmt_change(val: float | None) -> str:
    if val is None:
        return "[dim]—[/dim]"
    color = "green" if val >= 0 else "red"
    arrow = "▲" if val >= 0 else "▼"
    return f"[{color}]{arrow} {abs(val):.2f}%[/{color}]"


def render_dashboard(crypto_prices: dict, etf_prices: dict, next_analysis_in: int) -> None:
    """Render the full terminal dashboard."""
    console.clear()

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    header = Text(f"  📈 AGENT ALERTES BOURSE EN DIRECT  |  {now}  ", style="bold white on dark_blue")
    console.print(Panel(header, border_style="blue"))

    # --- Crypto table ---
    crypto_table = Table(
        title="[bold cyan]Crypto[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        min_width=44,
    )
    crypto_table.add_column("Actif",    style="bold white", width=10)
    crypto_table.add_column("Prix",     justify="right", width=14)
    crypto_table.add_column("24h",      justify="right", width=10)
    crypto_table.add_column("Vol 24h",  justify="right", width=14)

    for ticker, data in crypto_prices.items():
        if "error" in data:
            crypto_table.add_row(ticker, "[red]Erreur[/red]", "—", "—")
            continue
        vol = data.get("volume_24h")
        vol_str = f"${vol/1e9:.2f}B" if vol and vol >= 1e9 else (f"${vol/1e6:.1f}M" if vol else "—")
        crypto_table.add_row(
            f"{ticker}",
            _fmt_price(data.get("price")),
            _fmt_change(data.get("change_24h")),
            f"[dim]{vol_str}[/dim]",
        )

    # --- ETF table ---
    etf_table = Table(
        title="[bold green]ETFs US[/bold green]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold green",
        min_width=44,
    )
    etf_table.add_column("Ticker", style="bold white", width=8)
    etf_table.add_column("Nom",    width=20)
    etf_table.add_column("Prix",   justify="right", width=10)
    etf_table.add_column("24h",    justify="right", width=10)

    for ticker, data in etf_prices.items():
        if "error" in data:
            etf_table.add_row(ticker, data.get("name", ""), "[red]Erreur[/red]", "—")
            continue
        etf_table.add_row(
            ticker,
            f"[dim]{data.get('name', '')}[/dim]",
            _fmt_price(data.get("price")),
            _fmt_change(data.get("change_24h")),
        )

    console.print(Columns([crypto_table, etf_table], equal=False, expand=False))

    # --- Recent alerts ---
    if _alert_history:
        console.rule("[bold yellow]Dernières alertes IA[/bold yellow]")
        for alert in reversed(_alert_history[-6:]):
            _render_alert(alert, compact=True)

    # --- Status bar ---
    console.print(
        f"\n[dim]Prochaine analyse IA dans [bold]{next_analysis_in}s[/bold]  |  "
        f"Données: Yahoo Finance  |  Agent: Mistral Small  |  Ctrl+C pour quitter[/dim]"
    )


def render_alerts(alerts: list[dict]) -> None:
    """Render fresh AI-generated alerts prominently."""
    if not alerts:
        return
    _alert_history.extend(alerts)
    console.rule("[bold magenta]🤖 Analyse IA — Nouvelles alertes[/bold magenta]")
    for alert in alerts:
        _render_alert(alert, compact=False)


def _render_alert(alert: dict, compact: bool) -> None:
    severity = alert.get("severity", "info")
    style, icon = SEVERITY_STYLE.get(severity, ("white", "•"))
    asset = alert.get("asset", "?")
    title = alert.get("title", "")
    ts = alert.get("generated_at", "")[:19].replace("T", " ")
    conf = alert.get("confidence", 0)

    if compact:
        console.print(
            f"  [{style}]{icon} [{asset}][/{style}]  {title}  "
            f"[dim]{ts}  confiance:{conf}%[/dim]"
        )
        return

    body = (
        f"[bold]Analyse:[/bold] {alert.get('analysis', '')}\n"
        f"[bold]Recommandation:[/bold] [italic]{alert.get('recommendation', '')}[/italic]\n"
        f"[dim]Confiance: {conf}%  |  {ts}[/dim]"
    )
    console.print(
        Panel(
            body,
            title=f"[{style}]{icon}  [{severity.upper()}]  {asset}  —  {title}[/{style}]",
            border_style=style.split()[0],
            padding=(0, 1),
        )
    )
