# run_synthesize.py
import argparse
from pathlib import Path

from ci.synthesize import build_synthesis_input
from ci.util import slugify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--base", default="data")
    ap.add_argument("--max-pages", type=int, default=35)
    ap.add_argument("--max-snips", type=int, default=10)
    args = ap.parse_args()

    slug = slugify(args.vendor)
    run_dir = Path(args.base) / slug / "synthesis"
    run_dir.mkdir(parents=True, exist_ok=True)

    build_synthesis_input(
        vendor=args.vendor,
        domain=args.domain,
        evidence_packs_jsonl=f"data/{slug}/evidence/evidence_packs.jsonl",
        out_input_json=str(run_dir / "synthesis_input.json"),
        out_prompt_txt=str(run_dir / "synthesis_prompt.txt"),
        max_pages=args.max_pages,
        max_snippets_per_page=args.max_snips,
    )


if __name__ == "__main__":
    main()

