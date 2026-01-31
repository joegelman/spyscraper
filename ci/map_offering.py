# ci/map_offering.py
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STOP_HEADINGS = {
    "overview", "resources", "learn", "contact", "company", "security",
    "privacy", "terms", "cookies", "careers", "press",
}

CAPABILITY_HINTS = [
    "api", "sdk", "webhook", "rules", "models", "signals", "graph", "dashboard",
    "case management", "workflow", "decisioning", "risk", "fraud",
    "kyc", "kyb", "aml", "ofac", "pep", "watchlist",
    "device", "fingerprint", "biometrics", "behavior", "proxy", "vpn",
    "chargeback", "ato",
]

def _load_jsonl(path: str) -> list[dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def _path(url: str) -> str:
    return urlparse(url).path or "/"

def _segment(url: str) -> str:
    p = _path(url).strip("/").split("/")
    return "/" + (p[0] if p and p[0] else "")

def _clean_heading(h: str) -> str:
    h = re.sub(r"\s+", " ", (h or "")).strip()
    h = re.sub(r"^[•\-\–\—\*]+\s*", "", h)
    return h

def _heading_ok(h: str) -> bool:
    hh = _clean_heading(h).lower()
    if not hh:
        return False
    if hh in STOP_HEADINGS:
        return False
    if len(hh) < 3:
        return False
    return True

def _mine_modules(headings: list[str], title: str) -> list[str]:
    cand = []
    for h in headings[:30]:
        h = _clean_heading(h)
        if _heading_ok(h):
            cand.append(h)
    # sometimes title itself is the module
    t = _clean_heading(title)
    if _heading_ok(t):
        cand.insert(0, t)
    # dedupe preserving order
    seen = set()
    out = []
    for x in cand:
        key = x.lower()
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out[:12]

def _mine_capabilities(snippets: list[dict[str, Any]]) -> list[str]:
    blob = " ".join((s.get("text") or "") for s in snippets[:15]).lower()
    found = []
    for hint in CAPABILITY_HINTS:
        if hint in blob:
            found.append(hint)
    # dedupe
    out = []
    seen = set()
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:12]

@dataclass
class EvidenceRef:
    url: str
    snippet_rank: int | None
    snippet_score: float | None
    snippet_text: str

@dataclass
class Capability:
    name: str
    evidence: list[EvidenceRef]

@dataclass
class Module:
    name: str
    description: str
    capabilities: list[Capability]
    evidence_urls: list[str]

@dataclass
class Pillar:
    name: str
    modules: list[Module]

@dataclass
class OfferingMap:
    vendor: str
    domain: str
    positioning: str
    pillars: list[Pillar]


def draft_offering_map(
    vendor: str,
    domain: str,
    evidence_packs_jsonl: str = "out/evidence_packs.jsonl",
    out_path: str = "out/offering_map.json",
) -> None:
    packs = _load_jsonl(evidence_packs_jsonl)

    # group pages by top path segment
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in packs:
        url = p["url"]
        groups[_segment(url)].append(p)

    # pick a simple positioning line from homepage-ish / best page
    best = sorted(
        packs,
        key=lambda x: (-(x.get("page_scores", {}).get("total") or 0), -len(x.get("snippets", []))),
    )[0] if packs else None
    positioning = ""
    if best:
        positioning = best.get("meta_description") or best.get("title") or ""
    positioning = positioning.strip()

    pillars: list[Pillar] = []

    # Convert each group into a pillar
    for seg, pages in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        seg_name = seg.strip("/") or "root"
        pillar_name = seg_name.replace("-", " ").title()

        modules: list[Module] = []
        for p in sorted(pages, key=lambda x: -(x.get("page_scores", {}).get("total") or 0))[:12]:
            url = p["url"]
            title = p.get("title") or ""
            headings = p.get("headings") or []
            snippets = p.get("snippets") or []

            mined_modules = _mine_modules(headings, title)
            module_name = mined_modules[0] if mined_modules else (title or _path(url))

            cap_names = _mine_capabilities(snippets)
            caps: list[Capability] = []
            for cn in cap_names:
                ev = []
                for s in snippets[:6]:
                    ev.append(EvidenceRef(
                        url=url,
                        snippet_rank=s.get("rank"),
                        snippet_score=s.get("score"),
                        snippet_text=(s.get("text") or "")[:500],
                    ))
                caps.append(Capability(name=cn, evidence=ev))

            desc = ""
            if snippets:
                desc = (snippets[0].get("text") or "")[:240]

            modules.append(Module(
                name=module_name,
                description=desc,
                capabilities=caps,
                evidence_urls=[url],
            ))

        if modules:
            pillars.append(Pillar(name=pillar_name, modules=modules))

    om = OfferingMap(
        vendor=vendor,
        domain=domain,
        positioning=positioning,
        pillars=pillars,
    )

    Path(out_path).write_text(json.dumps(asdict(om), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")

