# ci/synthesize.py
from __future__ import annotations

import json
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


def build_synthesis_input(
    vendor: str,
    domain: str,
    evidence_packs_jsonl: str = "out/evidence_packs.jsonl",
    out_input_json: str = "out/synthesis_input.json",
    out_prompt_txt: str = "out/synthesis_prompt.txt",
    max_pages: int = 35,
    max_snippets_per_page: int = 10,
    max_chars_per_snippet: int = 520,
) -> None:
    """
    Produces two files:
      - synthesis_input.json: compact evidence bundle
      - synthesis_prompt.txt: strict prompt that outputs offering_semantics.json (schema)
    """
    packs = _load_jsonl(evidence_packs_jsonl)

    # sort by page score signal, then keep top N pages
    def page_signal(p: dict[str, Any]) -> float:
        ps = p.get("page_scores") or {}
        return float(ps.get("total") or 0)

    packs_sorted = sorted(packs, key=page_signal, reverse=True)[:max_pages]

    pages = []
    urls_used = []

    for p in packs_sorted:
        url = p.get("url", "")
        urls_used.append(url)

        # shrink headings/snippets to keep the prompt tight
        headings = (p.get("headings") or [])[:20]
        title = p.get("title") or ""
        meta = p.get("meta_description") or ""
        snips = (p.get("snippets") or [])[:max_snippets_per_page]
        snips_compact = []
        for s in snips:
            snips_compact.append({
                "rank": s.get("rank"),
                "score": s.get("score"),
                "text": (s.get("text") or "")[:max_chars_per_snippet],
            })

        pages.append({
            "url": url,
            "title": title,
            "meta_description": meta,
            "h1": (p.get("h1") or [])[:2],
            "headings": headings,
            "snippets": snips_compact,
            "page_scores": p.get("page_scores") or {},
        })

    payload = {
        "vendor": vendor,
        "domain": domain,
        "instruction": "Produce offering_semantics.json using only the evidence below. Cite sources by URL in evidence arrays.",
        "pages": pages,
        "urls_used": sorted(set(urls_used)),
    }

    Path(out_input_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    prompt = f"""You are a competitive intelligence analyst.

Task:
Given the JSON evidence bundle, output ONE JSON object named offering_semantics.json that conforms to this schema:

Top-level fields (required):
- vendor (string)
- domain (string)
- positioning_one_liner (string)
- modules (array of Module)

Recommended top-level fields:
- category (array of strings)
- target_segments (array of strings)
- differentiators (array of strings)
- notable_claims (array of ProofPoint)
- deemphasized_or_missing (array of strings)
- risks_or_ambiguities (array of strings)
- evidence_urls_used (array of strings)

Module schema (required fields):
- name (string)
- one_liner (string)
- description (string)

Module optional fields:
- key_capabilities: array of Capability
- proof_points: array of ProofPoint
- target_buyers: array of strings
- integrations: array of strings
- keywords: array of strings
- source_urls: array of strings

Capability schema:
- name (string)
- description (string, optional)
- evidence: array of EvidenceItem

ProofPoint schema:
- claim (string)
- evidence: array of EvidenceItem

EvidenceItem schema:
- url (string)
- quote (string)  # short, directly supported excerpt
- score (number, optional)

Rules:
- Use ONLY the provided evidence. No outside knowledge.
- Prefer product/platform pages; ignore fluffy marketing where possible.
- Keep it concrete: modules, capabilities, technical signals, integration points, buyer outcomes.
- Every major capability and proof point MUST have at least one EvidenceItem with a URL and quote.
- Output MUST be valid JSON only (no markdown, no commentary).

Now read this evidence bundle and output offering_semantics.json:

{Path(out_input_json).read_text(encoding="utf-8")}
"""
    Path(out_prompt_txt).write_text(prompt, encoding="utf-8")

    print(f"Wrote {out_input_json}")
    print(f"Wrote {out_prompt_txt}")
    print("Next: paste the prompt into your LLM and save the JSON output to out/offering_semantics.json")

