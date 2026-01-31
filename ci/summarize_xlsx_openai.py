# ci/summarize_xlsx_openai.py
from __future__ import annotations

import json
import os
import ssl
import urllib.request

import openpyxl

OPENAI_API_URL = "https://api.openai.com/v1/responses"


def call_openai(prompt: str, model: str = "gpt-5-mini") -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY env var")

    body = {
        "model": model,
        "input": prompt,
    }

    req = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # Extract first text output
    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                return c.get("text") or ""
    return ""


def summarize_row(full_text: str) -> str:
    # keep prompt tight; the sheet cell can be long but avoid runaway
    full_text = (full_text or "")[:12000]

    return call_openai(
        prompt=(
            "Summarize this page for competitive intel.\n"
            "Return:\n"
            "- a short TITLE CASE headline\n"
            "- 5–10 unicode bullets (•) with concrete capabilities / positioning / proof\n"
            "Avoid fluff.\n\n"
            f"PAGE TEXT (markdown):\n{full_text}\n"
        )
    ).strip()


def summarize_xlsx(xlsx_path: str, model: str = "gpt-5-mini") -> None:
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active  # single-sheet file

    # headers are on row 2; data starts row 3
    for r in range(3, ws.max_row + 1):
        full_text = ws.cell(r, 4).value or ""
        existing = ws.cell(r, 5).value or ""
        if existing.strip():
            continue
        if not str(full_text).strip():
            continue

        summary = summarize_row(str(full_text))
        ws.cell(r, 5, summary)
        print(f"row {r}: summarized")

    wb.save(xlsx_path)
    print(f"Updated {xlsx_path}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--model", default="gpt-5.2")
    args = ap.parse_args()
    summarize_xlsx(args.xlsx, model=args.model)
