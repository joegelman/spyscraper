# run_offering_map.py
import argparse

from ci.evidence import build_evidence_packs
from ci.map_offering import draft_offering_map
from ci.diagram import render_marchitecture_svg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    build_evidence_packs(
        pages_scored_jsonl=f"{args.out}/pages_scored.jsonl",
        snippets_jsonl=f"{args.out}/snippets.jsonl",
        keep_urls_txt=f"{args.out}/keep_urls.txt",
        out_path=f"{args.out}/evidence_packs.jsonl",
        max_snippets_per_url=25,
    )

    draft_offering_map(
        vendor=args.vendor,
        domain=args.domain,
        evidence_packs_jsonl=f"{args.out}/evidence_packs.jsonl",
        out_path=f"{args.out}/offering_map.json",
    )

    render_marchitecture_svg(
        offering_map_json=f"{args.out}/offering_map.json",
        out_html=f"{args.out}/marchitecture.html",
    )


if __name__ == "__main__":
    main()

