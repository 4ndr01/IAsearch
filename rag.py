"""
RAG pipeline: embed news with Mistral → store in Pinecone → retrieve relevant context.
"""

import time
from datetime import datetime, timezone
from pinecone import Pinecone, ServerlessSpec
from mistralai.client import Mistral
from config import MISTRAL_API_KEY, PINECONE_API_KEY

PINECONE_INDEX  = "news-rag"
EMBED_MODEL     = "mistral-embed"
EMBED_DIM       = 1024
EMBED_BATCH     = 32

_pc: Pinecone | None = None
_index = None
_mistral: Mistral | None = None


def _get_mistral() -> Mistral:
    global _mistral
    if _mistral is None:
        _mistral = Mistral(api_key=MISTRAL_API_KEY)
    return _mistral


def _get_index():
    global _pc, _index
    if _index is not None:
        return _index

    _pc = Pinecone(api_key=PINECONE_API_KEY)

    existing = [i.name for i in _pc.list_indexes()]
    if PINECONE_INDEX not in existing:
        _pc.create_index(
            name=PINECONE_INDEX,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not _pc.describe_index(PINECONE_INDEX).status["ready"]:
            time.sleep(1)

    _index = _pc.Index(PINECONE_INDEX)
    return _index


def _embed(texts: list[str]) -> list[list[float]]:
    client = _get_mistral()
    embeddings = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        resp = client.embeddings.create(model=EMBED_MODEL, inputs=batch)
        embeddings.extend([d.embedding for d in resp.data])
    return embeddings


NEWS_MAX_AGE_DAYS = 7


def _parse_published_ts(published: str) -> int:
    """Parse ISO 8601 date string to Unix timestamp, fallback to now."""
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return int(datetime.now(timezone.utc).timestamp())


def delete_old_articles(max_age_days: int = NEWS_MAX_AGE_DAYS, index=None) -> None:
    """Delete articles older than max_age_days from Pinecone."""
    if not PINECONE_API_KEY:
        return
    if index is None:
        index = _get_index()
    cutoff_ts = int(datetime.now(timezone.utc).timestamp()) - max_age_days * 86400
    try:
        index.delete(filter={"published_ts": {"$lt": cutoff_ts}})
    except Exception:
        pass


def index_articles(articles: list[dict]) -> int:
    """Embed and upsert only new articles into Pinecone. Returns number indexed."""
    if not articles or not PINECONE_API_KEY:
        return 0

    index = _get_index()

    # Filter out articles already in Pinecone to avoid redundant embedding calls
    all_ids = [a["id"] for a in articles]
    existing_ids: set[str] = set()
    for i in range(0, len(all_ids), 100):
        batch_ids = all_ids[i:i + 100]
        fetched = index.fetch(ids=batch_ids)
        existing_ids.update(fetched.vectors.keys())

    new_articles = [a for a in articles if a["id"] not in existing_ids]
    if not new_articles:
        return 0

    texts   = [a["text"] for a in new_articles]
    vectors = _embed(texts)

    upserts = []
    for article, vector in zip(new_articles, vectors):
        pub_ts = _parse_published_ts(article.get("published", ""))
        upserts.append({
            "id":     article["id"],
            "values": vector,
            "metadata": {
                "title":        article["title"][:200],
                "summary":      article["summary"][:400],
                "url":          article["url"],
                "source":       article["source"],
                "published":    article["published"],
                "published_ts": pub_ts,
                "tags":         ",".join(article.get("tags", [])),
            },
        })

    for i in range(0, len(upserts), 100):
        index.upsert(vectors=upserts[i:i + 100])

    delete_old_articles(index=index)

    return len(upserts)


def retrieve_news(query: str, k: int = 6) -> list[dict]:
    """Embed query and retrieve k most relevant articles from Pinecone."""
    if not PINECONE_API_KEY:
        return []
    try:
        index  = _get_index()
        vector = _embed([query])[0]
        result = index.query(vector=vector, top_k=k, include_metadata=True)
        return [m.metadata for m in result.matches]
    except Exception:
        return []


def rag_context(k: int = 5) -> str:
    """Build a news context string to inject into the agent prompt."""
    query   = "Bitcoin BTC S&P 500 SPY market price movement analysis"
    results = retrieve_news(query, k=k)
    if not results:
        return ""

    lines = ["=== ACTUALITÉS RÉCENTES (contexte RAG) ==="]
    for r in results:
        pub = r.get("published", "")[:10]
        lines.append(f"[{r.get('source', '')} {pub}] {r.get('title', '')}")
        if r.get("summary"):
            lines.append(f"  {r['summary'][:200]}")
    return "\n".join(lines)
