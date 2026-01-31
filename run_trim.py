# run_trim.py
import argparse

from ci.trim import build_snippets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="out/pages.jsonl", help="Input pages.jsonl")
    ap.add_argument("--out", default="out", help="Output directory")
    ap.add_argument("--top-k", type=int, default=20, help="Top K paragraphs per page")
    args = ap.parse_args()

    print("RUN_TRIM:", args.pages, args.out, args.top_k)
    build_snippets(args.pages, out_dir=args.out, top_k=args.top_k)


if __name__ == "__main__":
    main()

