#!/usr/bin/env python3
"""
one-shot competitive pipeline

Usage:
  python ci_run.py --domain sardine.ai
  python ci_run.py --domain seon.io --vendor "SEON"   # optional

What it does (end-to-end):
  1) crawl -> data/<slug>/crawl/{pages.jsonl,edges.csv,summary.json}
  2) trim/score -> data/<slug>/scored/{snippets.jsonl,pages_scored.jsonl,keep_urls.txt}
  3) evidence packs -> data/<slug>/evidence/evidence_packs.jsonl
  4) synthesis prompt+input -> data/<slug>/synthesis/{synthesis_input.json,synthesis_prompt.txt}
  5) report -> data/<slug>/report/offering_brief.md  (only if offering_semantics.json exists)

Decision logic baked in:
  - crawl allows everything (including blog) for recall
  - scoring/trimming decides what is "keep"
  - synthesis uses only keep_urls via evidence packs
  - no Playwright browser downloads (uses your existing Chrome via ci/browser.py)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Your existing modules
from ci.crawl import crawl_site
from ci.trim import build_snippets
from ci.evidence import build_evidence_packs
from ci.synthesize import build_synthesis_input
from ci.report import render_report_md


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"^https?://", "", s)
    s = s.strip("/").replace("www.", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def default_vendor_from_domain(domain: str) -> str:
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/").replace("www.", "")
    head = d.split(".")[0] if d else "Vendor"
    return head.capitalize()


def ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, help="e.g. sardine.ai (no protocol needed)")
    ap.add_argument("--vendor", default=None, help="e.g. Sardine (optional; inferred from domain)")
    ap.add_argument("--base", default="data", help="base output directory")
    ap.add_argument("--max-pages", type=int, default=450)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--top-k", type=int, default=20, help="top paragraphs per page for snippets")
    ap.add_argument("--max-synth-pages", type=int, default=35)
    ap.add_argument("--max-synth-snips", type=int, default=10)
    args = ap.parse_args()

    domain = args.domain.strip()
    vendor = args.vendor or default_vendor_from_domain(domain)
    slug = slugify(domain)

    base = Path(args.base) / slug
    crawl_dir = base / "crawl"
    scored_dir = base / "scored"
    evidence_dir = base / "evidence"
    synth_dir = base / "synthesis"
    report_dir = base / "report"

    for d in [crawl_dir, scored_dir, evidence_dir, synth_dir, report_dir]:
        d.mkdir(parents=True, exist_ok=True)

    start_url = f"https://www.{domain}/"

    print(f"\n=== CI RUN ===")
    print(f"Vendor : {vendor}")
    print(f"Domain : {domain}")
    print(f"Start  : {start_url}")
    print(f"Out    : {base}\n")

    # 1) CRAWL
    print("1) Crawling...")
    crawl_stats = crawl_site(
        start_url=start_url,
        out_dir=str(crawl_dir),
        max_pages=args.max_pages,
        delay=args.delay,
        allow_blog=True,  # recall; keep/drop decided later
    )
    print(f"   done: pages={crawl_stats.get('pages_fetched')} edges={crawl_stats.get('edges')}")

    pages_jsonl = crawl_dir / "pages.jsonl"
    if not pages_jsonl.exists():
        raise SystemExit(f"Missing crawl output: {pages_jsonl}")

    # 2) TRIM/SCORE
    print("2) Trimming/scoring...")
    build_snippets(
        pages_jsonl=str(pages_jsonl),
        out_dir=str(scored_dir),
        top_k=args.top_k,
    )

    keep_txt = scored_dir / "keep_urls.txt"
    if not keep_txt.exists():
        raise SystemExit(f"Missing keep list: {keep_txt}")

    kept = [ln.strip() for ln in keep_txt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"   kept urls: {len(kept)}")

    # 3) EVIDENCE PACKS
    print("3) Building evidence packs...")
    build_evidence_packs(
        pages_scored_jsonl=str(scored_dir / "pages_scored.jsonl"),
        snippets_jsonl=str(scored_dir / "snippets.jsonl"),
        keep_urls_txt=str(keep_txt),
        out_path=str(evidence_dir / "evidence_packs.jsonl"),
        max_snippets_per_url=25,
    )

    # 4) SYNTHESIS PROMPT + INPUT
    print("4) Preparing synthesis prompt+input...")
    build_synthesis_input(
        vendor=vendor,
        domain=domain,
        evidence_packs_jsonl=str(evidence_dir / "evidence_packs.jsonl"),
        out_input_json=str(synth_dir / "synthesis_input.json"),
        out_prompt_txt=str(synth_dir / "synthesis_prompt.txt"),
        max_pages=args.max_synth_pages,
        max_snippets_per_page=args.max_synth_snips,
    )

    # 5) REPORT (only if semantics already exists)
    semantics_json = synth_dir / "offering_semantics.json"
    if semantics_json.exists():
        print("5) Rendering report...")
        render_report_md(
            offering_semantics_json=str(semantics_json),
            out_md=str(report_dir / "offering_brief.md"),
        )
        print(f"   report: {report_dir / 'offering_brief.md'}")
    else:
        print("5) Report skipped (missing offering_semantics.json).")
        print(f"   Next step:")
        print(f"   - Open: {synth_dir / 'synthesis_prompt.txt'}")
        print(f"   - Paste into your LLM, save output JSON to:")
        print(f"     {semantics_json}")
        print(f"   - Then run:")
        print(f"     python ci_run.py --domain {domain} --vendor \"{vendor}\"")

    print("\nDONE.")
    print(f"Artifacts under: {base}\n")


if __name__ == "__main__":
    main()

