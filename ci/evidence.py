# ci/evidence.py
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _load_keep_urls(path: str) -> set[str]:
    keep = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u:
                keep.add(u)
    return keep


def build_evidence_packs(
    pages_scored_jsonl: str = "out/pages_scored.jsonl",
    snippets_jsonl: str = "out/snippets.jsonl",
    keep_urls_txt: str = "out/keep_urls.txt",
    out_path: str = "out/evidence_packs.jsonl",
    max_snippets_per_url: int = 25,
    max_full_text_chars: int = 40000,
) -> None:
    """
    One JSON object per URL, used as LLM input.
    Includes:
      - full_text: markdown display text if available, else plain text
      - snippets: top scored paragraphs
    """
    keep = _load_keep_urls(keep_urls_txt)
    pages = _load_jsonl(pages_scored_jsonl)

    page_by_url: dict[str, dict[str, Any]] = {}
    for p in pages:
        url = p.get("final_url") or p.get("url")
        if not url or url not in keep:
            continue
        page_by_url[url] = p

    snips = _load_jsonl(snippets_jsonl)
    snips_by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in snips:
        url = s.get("url")
        if not url or url not in keep:
            continue
        snips_by_url[url].append(
            {
                "rank": s.get("rank"),
                "score": s.get("score"),
                "text": s.get("text"),
            }
        )

    for url, arr in snips_by_url.items():
        arr.sort(key=lambda x: (-(x.get("score") or 0), x.get("rank") or 9999))
        snips_by_url[url] = arr[:max_snippets_per_url]

    outp = Path(out_path)
    if outp.exists():
        outp.unlink()
    outp.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for url, p in page_by_url.items():
            # Prefer markdown display text; fall back to plain extracted text.
            full_text = p.get("text_md") or p.get("text") or ""
            if max_full_text_chars and len(full_text) > max_full_text_chars:
                full_text = full_text[:max_full_text_chars] + "\n\n[TRUNCATED]\n"

            rec = {
                "url": url,
                "title": p.get("title", ""),
                "meta_description": p.get("meta_description", ""),
                "h1": p.get("h1", []) or [],
                "headings": p.get("headings", []) or [],
                "jsonld_types": p.get("jsonld_types", []) or [],
                "page_scores": {
                    "capability": p.get("capability"),
                    "engineering": p.get("engineering"),
                    "fluff": p.get("fluff"),
                    "freshness": p.get("freshness"),
                    "total": p.get("total"),
                    "keep": p.get("keep"),
                },
                "full_text": full_text,
                "snippets": snips_by_url.get(url, []),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {out_path} ({n} evidence packs)")
