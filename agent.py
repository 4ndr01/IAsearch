"""
Mistral Agents API: analyse BTC + SP500 via un agent pré-configuré sur console.mistral.ai.
Envoie les prix en contexte et parse la réponse JSON structurée.
"""

import json
import re
from datetime import datetime
from mistralai.client import Mistral
from config import MISTRAL_API_KEY, MISTRAL_AGENT_ID

_client: Mistral | None = None


def _get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=MISTRAL_API_KEY)
    return _client


JSON_SCHEMA = """
[
  {
    "severity": "info|warning|critical",
    "asset": "BTC ou SPY",
    "title": "Titre court (max 60 chars)",
    "analysis": "2-4 phrases d'analyse technique et contextuelle",
    "recommendation": "Suggestion actionnable: surveiller, acheter, prendre profit, etc.",
    "confidence": 0-100
  }
]
"""

PROMPT_TEMPLATE = """Analyse ces données de marché en temps réel et génère des alertes.

=== PRIX ACTUELS (UTC {time}) ===
{prices}

=== HISTORIQUE RÉCENT ({n} derniers snapshots) ===
{history}

Règles:
- Variation > 2% en 24h → severity "warning"
- Variation > 5% en 24h → severity "critical"
- Surveille la divergence BTC/SPY (signal macro)
- Sois concis et spécifique

Réponds UNIQUEMENT avec un tableau JSON valide dans ce format (sans markdown, sans commentaire):
{schema}
"""


def _parse_alerts(text: str) -> list[dict]:
    """Extrait et parse le JSON de la réponse texte de l'agent."""
    text = text.strip()

    # Retire les blocs markdown éventuels ```json ... ```
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        # Tentative : extraire le premier tableau JSON trouvé dans le texte
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    return [{
        "severity": "info",
        "asset": "SYSTEM",
        "title": "Réponse non parseable",
        "analysis": text[:200],
        "recommendation": "Vérifier le prompt de l'agent sur console.mistral.ai",
        "confidence": 0,
    }]


def run_analysis(prices: dict, price_history: list[dict]) -> list[dict]:
    """
    Lance une analyse via l'agent Mistral pré-configuré.
    Retourne une liste d'alertes structurées.
    """
    if not MISTRAL_API_KEY:
        return [{
            "severity": "critical", "asset": "SYSTEM",
            "title": "MISTRAL_API_KEY manquante",
            "analysis": "Configurez votre clé API dans le fichier .env",
            "recommendation": "Ajoutez MISTRAL_API_KEY=... dans .env",
            "confidence": 100,
        }]

    if not MISTRAL_AGENT_ID:
        return [{
            "severity": "critical", "asset": "SYSTEM",
            "title": "MISTRAL_AGENT_ID manquant",
            "analysis": "Configurez l'ID de votre agent Mistral dans le fichier .env",
            "recommendation": "Ajoutez MISTRAL_AGENT_ID=ag_... dans .env",
            "confidence": 100,
        }]

    client = _get_client()
    recent = price_history[-10:] if len(price_history) > 10 else price_history

    prompt = PROMPT_TEMPLATE.format(
        time=datetime.utcnow().strftime("%H:%M:%S"),
        prices=json.dumps(prices, indent=2),
        history=json.dumps(recent, indent=2),
        n=len(recent),
        schema=JSON_SCHEMA,
    )

    try:
        response = client.beta.conversations.start(
            agent_id=MISTRAL_AGENT_ID,
            agent_version=0,
            inputs=[{"role": "user", "content": prompt}],
        )
        text = response.outputs[0].content if response.outputs else ""
        alerts = _parse_alerts(text)
    except Exception as e:
        return [{
            "severity": "critical", "asset": "SYSTEM",
            "title": "Erreur API Mistral",
            "analysis": str(e),
            "recommendation": "Vérifier la clé API et l'agent_id",
            "confidence": 0,
        }]

    # Horodatage
    now = datetime.utcnow().isoformat()
    for alert in alerts:
        alert.setdefault("generated_at", now)

    return alerts
