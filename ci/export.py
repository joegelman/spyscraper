# ci/export.py
import csv
import json
from pathlib import Path


def load_pages(pages_path: Path):
    with pages_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def is_product_page(url: str, title: str = "", text_md: str = "") -> bool:
    deny = (
        "/blog",
        "/press",
        "/news",
        "/events",
        "/careers",
        "/privacy",
        "/terms",
        "/legal",
    )
    if any(d in url.lower() for d in deny):
        return False

    allow = (
        "/product",
        "/products",
        "/solution",
        "/solutions",
        "/platform",
        "/use-case",
        "/use-cases",
        "/pricing",
        "/integration",
        "/integrations",
        "/partners",
        "/technology",
        "/how-it-works",
        "/features",
    )

    if any(a in url.lower() for a in allow):
        return True

    blob = (title + "\n" + text_md).lower()
    signal_terms = (
        "platform",
        "api",
        "integrat",
        "chargeback",
        "fraud",
        "risk",
        "guarantee",
        "policy",
        "dispute",
        "authorization",
        "decisioning",
        "account takeover",
        "ato",
        "identity",
        "aml",
        "kyc",
    )
    return any(t in blob for t in signal_terms)


def export_markdown(pages, out_path: Path):
    blocks = []
    for p in pages:
        md = (p.get("text_md") or "").strip()
        if not md:
            continue

        title = p.get("title") or p["url"]

        blocks.append(f"# {title}\n\n**URL:** {p['url']}\n\n{md}\n")

    out_path.write_text("\n\n---\n\n".join(blocks), encoding="utf-8")


def export_csv(pages, out_path: Path):
    rows = []
    for p in pages:
        rows.append(
            {
                "url": p["url"],
                "title": p.get("title", ""),
                "text_md": p.get("text_md", ""),
                "links_count": p.get("links_count", 0),
            }
        )

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["url", "title", "text_md", "links_count"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main(
    pages_path: str,
    out_dir: str,
    products_only: bool = True,
):
    pages_path = Path(pages_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = list(load_pages(pages_path))

    if products_only:
        pages = [
            p
            for p in pages
            if is_product_page(p["url"], p.get("title", ""), p.get("text_md", ""))
        ]

    export_markdown(pages, out_dir / "pages.md")
    export_csv(pages, out_dir / "pages.csv")

    print(f"✓ exported {len(pages)} pages")
    print(f"  - {out_dir / 'pages.md'}")
    print(f"  - {out_dir / 'pages.csv'}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--all", action="store_true", help="include non-product pages")
    args = ap.parse_args()

    main(
        pages_path=args.pages,
        out_dir=args.out,
        products_only=not args.all,
    )
