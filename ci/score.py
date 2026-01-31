# ci/score.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse


CAPABILITY_TERMS = [
    # product / platform
    "platform", "api", "sdk", "integration", "webhook", "dashboard",
    "rules", "model", "ml", "machine learning", "graph", "signals",
    "decision", "decisioning", "risk engine", "case management",
    # fraud/risk/identity/compliance
    "fraud", "scam", "chargeback", "ato", "account takeover",
    "identity", "kyc", "kyb", "aml", "ofac", "pep", "watchlist",
    "device", "fingerprint", "behavior", "biometrics", "vpn", "proxy",
    # sales/positioning
    "use case", "solution", "segment", "industry", "customer", "pricing",
    "latency", "accuracy", "coverage", "false positive",
]

FLUFF_TERMS = [
    "in this article", "table of contents", "newsletter", "subscribe",
    "thought leadership", "what is", "why it matters", "future of",
    "introduction", "definitions",
]

ENGINEERING_SIGNALS = [
    "engineering", "architecture", "latency", "pipeline", "deployment",
    "feature store", "model training", "inference", "distributed",
    "postgres", "kafka", "graphql", "rest", "gRPC".lower(),
]


def path(url: str) -> str:
    return urlparse(url).path or "/"


def is_blog(url: str) -> bool:
    return (path(url).startswith("/blog") or "/blog/" in path(url))


def tokenize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def term_score(text: str, terms: list[str], weight: float = 1.0) -> float:
    t = tokenize(text)
    score = 0.0
    for term in terms:
        if term in t:
            score += weight
    return score


def freshness_hint(url: str) -> float:
    """
    Very rough: if URL contains YYYY/MM or YYYY-MM-DD, use it.
    Returns 0..1 where 1 is "recent-ish". Unknown => 0.5.
    """
    p = path(url)
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", p)
    if not m:
        m = re.search(r"(20\d{2})[/-](\d{1,2})", p)
    if not m:
        return 0.5

    try:
        y = int(m.group(1))
        mo = int(m.group(2))
        d = int(m.group(3)) if m.lastindex and m.lastindex >= 3 else 1
        dt = datetime(y, mo, d)
        age_days = (datetime.now() - dt).days
        if age_days < 90:
            return 1.0
        if age_days < 365:
            return 0.8
        if age_days < 730:
            return 0.6
        return 0.3
    except Exception:
        return 0.5


@dataclass
class PageScores:
    capability: float
    fluff: float
    engineering: float
    freshness: float
    total: float
    keep: bool


def score_page(url: str, title: str, headings: list[str], text: str) -> PageScores:
    blob = " | ".join([title or "", " ".join(headings or []), text or ""])

    cap = term_score(blob, CAPABILITY_TERMS, weight=1.0)
    eng = term_score(blob, ENGINEERING_SIGNALS, weight=1.2)
    fluff = term_score(blob, FLUFF_TERMS, weight=1.0)
    fresh = freshness_hint(url)

    # total: reward capability + engineering, penalize fluff; nudge freshness for blogs
    total = (cap + eng) - (1.2 * fluff)
    if is_blog(url):
        total = total * (0.7 + 0.6 * fresh)  # older blogs get downweighted

    # keep rule: strong capability/engineering OR non-blog with decent signal
    keep = (cap + eng >= 2) and (fluff <= 4)
    if not is_blog(url):
        keep = True

    return PageScores(
        capability=cap,
        fluff=fluff,
        engineering=eng,
        freshness=fresh,
        total=total,
        keep=keep,
    )

