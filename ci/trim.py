# ci/trim.py
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from ci.score import score_page, term_score, CAPABILITY_TERMS, ENGINEERING_SIGNALS, FLUFF_TERMS


def split_paragraphs(text: str) -> list[str]:
    """
    Split page text into paragraph-ish chunks.
    Keep only reasonably long chunks to avoid nav/footer noise.
    """
    raw = re.split(r"\n{2,}|\r\n\r\n+", text or "")
    paras: list[str] = []
    for p in raw:
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) >= 80:
            paras.append(p)
    return paras


def score_paragraph(p: str) -> float:
    """
    Simple relevance scoring: capability + engineering - fluff penalty.
    """
    cap = term_score(p, CAPABILITY_TERMS, 1.0)
    eng = term_score(p, ENGINEERING_SIGNALS, 1.2)
    fluff = term_score(p, FLUFF_TERMS, 1.0)
    return (cap + eng) - (1.4 * fluff)


def build_snippets(pages_jsonl: str, out_dir: str = "out", top_k: int = 25) -> None:
    """
    Reads out/pages.jsonl and writes:
      - out/snippets.jsonl       (top_k scored paragraphs per page)
      - out/pages_scored.jsonl   (page record + keep/score fields)
      - out/keep_urls.txt        (final_url list where keep==true)

    Files are created up-front so you always see output even if the run crashes.
    """
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    pages_path = Path(pages_jsonl)
    if not pages_path.exists():
        raise FileNotFoundError(f"Input pages.jsonl not found: {pages_jsonl}")

    snippets_path = outp / "snippets.jsonl"
    pages_scored_path = outp / "pages_scored.jsonl"
    keep_path = outp / "keep_urls.txt"

    # wipe old outputs
    for p in (snippets_path, pages_scored_path, keep_path):
        if p.exists():
            p.unlink()

    # create outputs immediately (so you can see progress / detect crashes)
    snippets_path.touch()
    pages_scored_path.touch()
    keep_path.write_text("", encoding="utf-8")

    keep_urls: list[str] = []

    with open(pages_jsonl, "r", encoding="utf-8") as f_in, \
         open(snippets_path, "a", encoding="utf-8") as f_snip, \
         open(pages_scored_path, "a", encoding="utf-8") as f_pg:

        for i, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue

            rec = json.loads(line)

            url = rec.get("final_url") or rec.get("url") or ""
            title = rec.get("title", "") or ""
            headings = rec.get("headings", []) or []
            text = rec.get("text", "") or ""

            ps = score_page(url, title, headings, text)
            rec_out = {**rec, **asdict(ps)}
            f_pg.write(json.dumps(rec_out, ensure_ascii=False) + "\n")

            # paragraph snippets
            paras = split_paragraphs(text)
            scored = [(score_paragraph(p), p) for p in paras]
            scored.sort(key=lambda x: x[0], reverse=True)

            for rank, (s, p) in enumerate(scored[:top_k], start=1):
                f_snip.write(json.dumps({
                    "url": url,
                    "title": title,
                    "rank": rank,
                    "score": s,
                    "text": p,
                }, ensure_ascii=False) + "\n")

            if ps.keep:
                keep_urls.append(url)

            # periodic flush so you see files grow during long runs
            if i % 25 == 0:
                f_pg.flush()
                f_snip.flush()

    # write keep list at end (may be empty; still write the file)
    with open(keep_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(set(keep_urls))) + ("\n" if keep_urls else ""))

    # optional: print a short summary for CLI usage
    print(f"Wrote: {snippets_path}")
    print(f"Wrote: {pages_scored_path}")
    print(f"Wrote: {keep_path}  ({len(set(keep_urls))} kept)")

