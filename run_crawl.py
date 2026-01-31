# run_crawl.py
import argparse

from ci.crawl import crawl_site


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, help="e.g. seon.io")
    ap.add_argument("--start", default=None, help="override start url")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--out", default="out")
    ap.add_argument(
        "--include-subdomains", action="store_true", help="include docs.*, etc."
    )
    args = ap.parse_args()

    start = args.start or f"https://www.{args.domain}/"

    stats = crawl_site(
        start_url=start,
        out_dir=args.out,
        max_pages=args.max_pages,
        delay=args.delay,
        include_subdomains=args.include_subdomains or True,  # default True
    )
    print(stats)


if __name__ == "__main__":
    main()
