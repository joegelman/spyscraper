from __future__ import annotations

import csv
import itertools
import json
import sys
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Set
from urllib.parse import urlparse

from ci.browser import with_browser
from ci.fetch import FetchResult, fetch_http, fetch_rendered, needs_browser

# -----------------------------
# URL + domain helpers
# -----------------------------


def canonicalize(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # strip fragment and trailing slash
    p = urlparse(url)
    url = f"{p.scheme}://{p.netloc}{p.path}"
    if url.endswith("/") and p.path != "/":
        url = url[:-1]
    return url


def base_domain(netloc: str) -> str:
    n = (netloc or "").lower()
    if n.startswith("www."):
        n = n[4:]
    return n


def allowed_netloc(netloc: str, allowed_base: str, include_subdomains: bool) -> bool:
    n = base_domain(netloc)
    if n == allowed_base:
        return True
    if include_subdomains and n.endswith("." + allowed_base):
        return True
    return False


def fetch_record(url: str, browser=None) -> dict:
    """
    Fetch via HTTP first; if thin, fall back to rendered fetch (if browser provided).
    Returns a dict suitable for JSONL writing.
    """
    r: FetchResult = fetch_http(url)

    if browser is not None and needs_browser(r):
        try:
            r = fetch_rendered(url, browser)
        except Exception:
            # keep HTTP result
            pass

    rec = asdict(r)
    # keep both raw and canonical final_url for later
    rec["url"] = url
    rec["final_url"] = canonicalize(r.url)
    rec["text_len"] = len((r.text or ""))
    rec["text"] = rec.get("text_md") or rec.get("text") or ""
    rec["text_len"] = len(rec["text"])

    # keep plain text separately if you want
    rec["text_plain"] = rec.get("text") or ""

    # drop raw html to prevent confusion and shrink file size
    rec.pop("html", None)
    return rec


class Spinner:
    def __init__(self):
        self._spin = itertools.cycle("|/-\\")
        self.last = ""

    def tick(self, msg: str):
        s = f"\r{next(self._spin)} {msg}"
        self.last = s
        sys.stdout.write(s)
        sys.stdout.flush()

    def done(self, msg: str = "done"):
        sys.stdout.write(f"\r✓ {msg}\n")
        sys.stdout.flush()


# -----------------------------
# Crawl
# -----------------------------


def crawl_site(
    start_url: str,
    max_pages: int,
    out_dir: str = "out",  # ← default
    delay: float = 0.6,
    include_subdomains: bool = True,
) -> Dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pages_path = out / "pages.jsonl"
    edges_path = out / "edges.csv"
    summary_path = out / "summary.json"

    # wipe old outputs
    for p in (pages_path, edges_path, summary_path):
        if p.exists():
            p.unlink()

    start_url = canonicalize(start_url)
    allowed_base = base_domain(urlparse(start_url).netloc)

    q = deque([start_url])
    seen: Set[str] = set()
    edges: Set[tuple[str, str]] = set()

    stats = {
        "pages_fetched": 0,
        "edges": 0,
        "skipped_external": 0,
        "skipped_seen": 0,
        "errors": 0,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    spinner = Spinner()

    def run(browser):
        nonlocal stats, spinner
        with open(pages_path, "a", encoding="utf-8") as f_pages:
            while q and stats["pages_fetched"] < max_pages:
                spinner.tick(
                    f"pages={stats['pages_fetched']} "
                    f"queue={len(q)} "
                    f"errors={stats['errors']} "
                    f"seen={len(seen)}"
                )

                url = canonicalize(q.popleft())

                if url in seen:
                    stats["skipped_seen"] += 1
                    continue

                if not allowed_netloc(
                    urlparse(url).netloc, allowed_base, include_subdomains
                ):
                    stats["skipped_external"] += 1
                    continue

                seen.add(url)

                try:
                    rec = fetch_record(url, browser=browser)
                except Exception:
                    stats["errors"] += 1
                    continue

                f_pages.write(json.dumps(rec, ensure_ascii=False) + "\n")
                stats["pages_fetched"] += 1

                src = rec["final_url"]
                for tgt in rec.get("links", []) or []:
                    tgt = canonicalize(tgt)
                    if not allowed_netloc(
                        urlparse(tgt).netloc, allowed_base, include_subdomains
                    ):
                        stats["skipped_external"] += 1
                        continue
                    edges.add((src, tgt))
                    if tgt not in seen:
                        q.append(tgt)

                f_pages.flush()
                time.sleep(delay)

    with_browser(run)

    # write edges
    with open(edges_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "target"])
        for s, t in sorted(edges):
            w.writerow([s, t])

    stats["edges"] = len(edges)
    stats["unique_seen"] = len(seen)
    stats["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    summary = {
        "start_url": start_url,
        "allowed_base": allowed_base,
        "include_subdomains": include_subdomains,
        "max_pages": max_pages,
        "delay": delay,
        "stats": stats,
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    spinner.done(
        f"pages={stats['pages_fetched']} edges={stats['edges']} errors={stats['errors']}"
    )
    return summary
