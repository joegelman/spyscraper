# ci/wizard.py
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from ci.crawl import crawl_site
from ci.evidence import build_evidence_packs
from ci.make_scrape_xlsx import write_scrape_xlsx
from ci.trim import build_snippets


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"^https?://", "", s).strip("/").replace("www.", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalize_domain(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^https?://", "", s).strip("/")
    s = s.replace("www.", "")
    return s


def ask(prompt: str) -> str:
    return input(prompt).strip()


def ask_yes_no(prompt: str, default_no: bool = True) -> bool:
    v = input(prompt).strip().lower()
    if v in ("y", "yes"):
        return True
    if v in ("n", "no"):
        return False
    return False if default_no else True


def pick_menu(
    title: str, options: list[tuple[str, str]], default_idx: int | None = None
) -> int:
    print(title)
    for i, (label, desc) in enumerate(options, start=1):
        if desc:
            print(f"({i}) {label:<10} - {desc}")
        else:
            print(f"({i}) {label}")
    if default_idx is not None:
        v = input(f"Select (default {default_idx}): ").strip()
        if not v:
            return default_idx
    else:
        v = input("Select: ").strip()

    while True:
        if v.isdigit():
            n = int(v)
            if 1 <= n <= len(options):
                return n
        v = input(f"Select 1-{len(options)}: ").strip()


def ask_int(prompt: str, min_v: int, max_v: int, default: int) -> int:
    v = input(f"{prompt} [{default}]: ").strip()
    if not v:
        return default
    while True:
        if v.isdigit():
            n = int(v)
            if min_v <= n <= max_v:
                return n
        v = input(f"Enter an integer {min_v}-{max_v} [{default}]: ").strip()
        if not v:
            return default


def is_insecure_enabled() -> bool:
    return os.environ.get("OPENAI_INSECURE", "").lower() in ("1", "true", "yes")


def pick_network_mode() -> None:
    """
    Sets OPENAI_INSECURE=1 for this process only if user selects Basic.
    """
    print("Network config:")
    print("(1) Basic (recommended for managed Macs)")
    print("(2) Expert")
    choice = input("Select [1]: ").strip() or "1"
    if choice == "1":
        os.environ["OPENAI_INSECURE"] = "1"


def run_cmd(cmd: list[str]) -> None:
    """
    Run a subprocess with inherited env/stdout/stderr. Raise on failure.
    """
    print("\n$ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=os.environ.copy())


def main():
    # 1) Competitor name
    vendor = ask("Competitor name: ")
    while not vendor:
        vendor = ask("Competitor name: ")

    # 2) Domain
    domain = normalize_domain(ask("Competitor website/domain (e.g. competitor.com): "))
    while not domain or "." not in domain:
        domain = normalize_domain(
            ask("Competitor website/domain (e.g. competitor.com): ")
        )

    # 3) Scrape size
    size_choice = pick_menu(
        "Scrape size:",
        [("Small", "50 pages"), ("Medium", "100 pages"), ("Large", "300 pages")],
        default_idx=1,
    )
    max_pages = {1: 50, 2: 100, 3: 300}[size_choice]

    # Defaults
    model = "gpt-5-mini"
    delay = 0.6
    top_k = 20

    # 4) Runtime settings
    run_choice = pick_menu(
        "Runtime settings:",
        [("Use defaults", ""), ("Customize first", "")],
        default_idx=1,
    )

    if run_choice == 2:
        model_choice = pick_menu(
            "OpenAI model:",
            [("Budget", "gpt-4o"), ("Solid", "gpt-5-mini"), ("Fancy", "gpt-5.2")],
            default_idx=2,
        )
        model = {1: "gpt-4o", 2: "gpt-5-mini", 3: "gpt-5.2"}[model_choice]

        delay_choice = pick_menu(
            "Delays between requests:",
            [("Fast", "0.3s"), ("Normal", "0.6s"), ("Slow", "1.2s")],
            default_idx=2,
        )
        delay = {1: 0.3, 2: 0.6, 3: 1.2}[delay_choice]

        top_k = ask_int("Top paragraphs per page (5-100):", 5, 100, 20)

    if not is_insecure_enabled():
        print(
            "\nNote: OPENAI_INSECURE is not set.\n"
            "If you see SSL errors on a managed Mac, choose 'Basic' below.\n"
        )

    pick_network_mode()

    # Summary + confirm
    print("\n--- Run plan ---")
    print(f"Vendor: {vendor}")
    print(f"Domain: {domain}")
    print(f"Pages:  {max_pages}")
    print(f"Model:  {model}")
    print(f"Delay:  {delay}s")
    print(f"Top-k:  {top_k}")
    print("----------------\n")

    if not ask_yes_no("Ready to run? (y/N): "):
        print("Aborted.")
        return

    # Output dirs
    base = Path("data") / slugify(domain)
    crawl_dir = base / "crawl"
    scored_dir = base / "scored"
    evidence_dir = base / "evidence"
    export_dir = base / "export"

    for d in (crawl_dir, scored_dir, evidence_dir, export_dir):
        d.mkdir(parents=True, exist_ok=True)

    start_url = f"https://www.{domain}/"
    pages_jsonl = crawl_dir / "pages.jsonl"

    print("\n1) Crawling...")
    crawl_site(
        start_url=start_url,
        out_dir=str(crawl_dir),
        max_pages=max_pages,
        delay=delay,
        include_subdomains=True,
    )

    print("\n2) Trimming/scoring...")
    build_snippets(
        pages_jsonl=str(pages_jsonl),
        out_dir=str(scored_dir),
        top_k=top_k,
    )

    print("\n3) Evidence packs...")
    build_evidence_packs(
        pages_scored_jsonl=str(scored_dir / "pages_scored.jsonl"),
        snippets_jsonl=str(scored_dir / "snippets.jsonl"),
        keep_urls_txt=str(scored_dir / "keep_urls.txt"),
        out_path=str(evidence_dir / "evidence_packs.jsonl"),
        max_snippets_per_url=25,
        max_full_text_chars=40000,
    )

    print("\n4) Build scrape XLSX...")
    xlsx_path = export_dir / "core_web_content_scrape.xlsx"
    write_scrape_xlsx(
        pages_jsonl=str(pages_jsonl),
        out_xlsx=str(xlsx_path),
        title=f"{vendor} Core Web Content Scrape",
        include_all=True,
    )

    print("\n5) Summarize XLSX via OpenAI (subprocess)...")
    run_cmd(
        [
            sys.executable,
            "ci/summarize_xlsx_openai.py",
            "--xlsx",
            str(xlsx_path),
            "--model",
            model,
        ]
    )

    print("\n6) Generate Competitive Offering Map DOCX via OpenAI (subprocess)...")
    docx_path = export_dir / "competitive_offering_map.docx"
    run_cmd(
        [
            sys.executable,
            "ci/make_offering_docx_openai.py",
            "--vendor",
            vendor,
            "--domain",
            domain,
            "--xlsx",
            str(xlsx_path),
            "--out",
            str(docx_path),
            "--model",
            model,
            "--max-rows",
            "10",
        ]
    )

    print("\nDONE.")
    print(f"Folder: {base}")
    print(f"- XLSX: {xlsx_path}")
    print(f"- DOCX: {docx_path}")


if __name__ == "__main__":
    main()
