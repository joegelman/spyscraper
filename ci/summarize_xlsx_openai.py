# ci/summarize_xlsx_openai.py
from __future__ import annotations

import argparse
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

import openpyxl

OPENAI_API_URL = "https://api.openai.com/v1/responses"


def _log(msg: str) -> None:
    print(msg, flush=True)


def call_openai(
    prompt: str,
    model: str,
    timeout_s: int = 45,
    max_output_tokens: int = 240,
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY env var")

    body: Dict[str, object] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": max_output_tokens,
        # NOTE: do NOT send temperature; some models reject it (as you saw).
        # Optional: prevent hard failures on slightly-too-long inputs.
        "truncation": "auto",
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
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    for item in data.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                return (c.get("text") or "").strip()
    return ""


def call_openai_with_retries(
    prompt: str,
    model: str,
    timeout_s: int = 45,
    max_output_tokens: int = 240,
    retries: int = 6,
) -> str:
    backoff = 1.0
    last_body = ""

    for attempt in range(1, retries + 1):
        try:
            return call_openai(
                prompt=prompt,
                model=model,
                timeout_s=timeout_s,
                max_output_tokens=max_output_tokens,
            )

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<could not read error body>"
            last_body = body

            # Non-retryable client errors: stop immediately.
            if e.code in (400, 401, 403, 404, 422):
                _log(f"HTTP {e.code} (non-retryable). Body:\n{body}")
                raise

            # Retryable
            if e.code in (429, 500, 502, 503, 504):
                sleep_s = backoff + random.uniform(0, 0.25)
                _log(
                    f"HTTP {e.code} retry (attempt {attempt}/{retries}) sleeping {sleep_s:.2f}s"
                )
                if body:
                    _log(body)
                time.sleep(sleep_s)
                backoff = min(backoff * 1.8, 20)
                continue

            _log(f"HTTP {e.code} unexpected. Body:\n{body}")
            raise

        except (urllib.error.URLError, TimeoutError) as e:
            sleep_s = backoff + random.uniform(0, 0.25)
            _log(
                f"network/timeout (attempt {attempt}/{retries}) sleeping {sleep_s:.2f}s: {e!r}"
            )
            time.sleep(sleep_s)
            backoff = min(backoff * 1.8, 20)

    raise RuntimeError(
        f"OpenAI request failed after retries. Last error body:\n{last_body}"
    )


def _trim_text(full_text: str, max_chars: int = 12000) -> str:
    t = (full_text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[:8000] + "\n\n[...]\n\n" + t[-2000:]


def summarize_row(
    full_text: str, model: str, timeout_s: int, max_output_tokens: int
) -> str:
    full_text = _trim_text(full_text)

    prompt = (
        "Summarize this page for competitive intel.\n"
        "FORMAT (exact):\n"
        "HEADLINE: <Title Case, <= 10 words>\n"
        "BULLETS:\n"
        "• ...\n"
        "Rules:\n"
        "- 5–8 bullets\n"
        "- concrete capabilities / positioning / proof only\n"
        "- no fluff, no intro, no conclusion\n\n"
        f"PAGE TEXT (markdown):\n{full_text}\n"
    )

    return call_openai_with_retries(
        prompt=prompt,
        model=model,
        timeout_s=timeout_s,
        max_output_tokens=max_output_tokens,
        retries=6,
    ).strip()


def build_jobs(
    ws, start_row: int, text_col: int, out_col: int, heartbeat_every: int = 200
) -> List[Tuple[int, str]]:
    jobs: List[Tuple[int, str]] = []
    max_row = ws.max_row
    _log(
        f"Sheet scan: rows {start_row}..{max_row} | text_col={text_col} out_col={out_col}"
    )

    for r in range(start_row, max_row + 1):
        if heartbeat_every and (r % heartbeat_every == 0):
            _log(f"scanned up to row {r}/{max_row}")

        full_text = ws.cell(r, text_col).value
        existing = ws.cell(r, out_col).value

        if existing is not None and str(existing).strip():
            continue
        if full_text is None or not str(full_text).strip():
            continue

        jobs.append((r, str(full_text)))

    return jobs


def summarize_xlsx(
    xlsx_path: str,
    model: str,
    workers: int = 8,
    start_row: int = 3,
    text_col: int = 4,
    out_col: int = 5,
    timeout_s: int = 45,
    max_output_tokens: int = 240,
    save_every: int = 10,
) -> None:
    _log(f"Loading workbook: {xlsx_path}")
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    jobs = build_jobs(ws, start_row=start_row, text_col=text_col, out_col=out_col)
    _log(f"jobs: {len(jobs)}")
    if not jobs:
        _log(
            "No rows to summarize (either output col already filled or text col empty)."
        )
        return

    first_r, first_txt = jobs[0]
    _log(f"first job row: {first_r} text_len: {len(first_txt)}")
    _log(
        f"Running model={model} workers={workers} timeout_s={timeout_s} max_output_tokens={max_output_tokens}"
    )

    completed = 0

    # Sequential path (clean + easiest to debug)
    if workers <= 1:
        for r, txt in jobs:
            _log(f"row {r}: start")
            summary = summarize_row(
                txt,
                model=model,
                timeout_s=timeout_s,
                max_output_tokens=max_output_tokens,
            )
            ws.cell(r, out_col, summary)
            completed += 1
            _log(f"row {r}: summarized ({completed}/{len(jobs)})")
            if save_every and (completed % save_every == 0):
                wb.save(xlsx_path)
                _log(f"checkpoint saved ({completed}/{len(jobs)})")

        wb.save(xlsx_path)
        _log(f"Updated {xlsx_path} | completed={completed}")
        return

    # Concurrent path with bounded in-flight futures (so you don't enqueue everything at once)
    max_inflight = max(2, workers * 2)
    idx = 0

    def submit(ex, job):
        r, txt = job
        return ex.submit(summarize_row, txt, model, timeout_s, max_output_tokens), r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        inflight: List[Tuple[object, int]] = []

        while idx < len(jobs) and len(inflight) < max_inflight:
            fut, r = submit(ex, jobs[idx])
            _log(f"row {r}: start")
            inflight.append((fut, r))
            idx += 1

        while inflight:
            for fut in as_completed([f for f, _ in inflight], timeout=None):
                # find row for this future
                r = next(rr for ff, rr in inflight if ff is fut)
                inflight = [(ff, rr) for ff, rr in inflight if ff is not fut]

                try:
                    summary = fut.result()
                except Exception as e:
                    _log(f"FAILED row {r}: {e!r}")
                    raise

                ws.cell(r, out_col, summary)
                completed += 1
                _log(f"row {r}: summarized ({completed}/{len(jobs)})")

                if save_every and (completed % save_every == 0):
                    wb.save(xlsx_path)
                    _log(f"checkpoint saved ({completed}/{len(jobs)})")

                # keep pipeline full
                if idx < len(jobs):
                    fut2, r2 = submit(ex, jobs[idx])
                    _log(f"row {r2}: start")
                    inflight.append((fut2, r2))
                    idx += 1

                break  # process futures one at a time to keep logs sane

    wb.save(xlsx_path)
    _log(f"Updated {xlsx_path} | completed={completed}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--start-row", type=int, default=3)
    ap.add_argument("--text-col", type=int, default=4)
    ap.add_argument("--out-col", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--max-output-tokens", type=int, default=240)
    ap.add_argument("--save-every", type=int, default=10)
    args = ap.parse_args()

    summarize_xlsx(
        xlsx_path=args.xlsx,
        model=args.model,
        workers=args.workers,
        start_row=args.start_row,
        text_col=args.text_col,
        out_col=args.out_col,
        timeout_s=args.timeout,
        max_output_tokens=args.max_output_tokens,
        save_every=args.save_every,
    )
