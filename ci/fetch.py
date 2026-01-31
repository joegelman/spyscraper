# ci/fetch.py
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup
from markdownify import markdownify as md

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120 Safari/537.36"
)

SKIP_PREFIXES = ("mailto:", "javascript:", "tel:", "#")


@dataclass
class FetchResult:
    url: str  # final URL (after redirects)
    status: int
    content_type: str
    html: str  # raw HTML (keep for debugging; you can drop later)
    text: str  # plain extracted text (trafilatura, text)
    text_md: str  # extracted markdown (trafilatura, markdown)
    links: list[str]  # absolute, defragged
    links_count: int


def _extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith(SKIP_PREFIXES):
            continue
        abs_url = urljoin(base_url, href)
        abs_url, _ = urldefrag(abs_url)
        out.append(abs_url)

    # dedupe preserving order
    seen = set()
    deduped = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def _extract_text_plain(html: str) -> str:
    txt = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        output_format="txt",
    )
    txt = (txt or "").strip()
    if len(txt) >= 800:
        return txt

    # fallback: broaden recall for marketing pages
    txt2 = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=False,
        output_format="txt",
    )
    return ((txt2 or txt) or "").strip()


def _extract_text_markdown(html: str) -> str:
    md_txt = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        output_format="markdown",
    )
    md_txt = (md_txt or "").strip()
    if len(md_txt) >= 800:
        return md_txt

    md_txt2 = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=False,
        output_format="markdown",
    )
    md_txt2 = (md_txt2 or "").strip()
    return md_txt2 or md_txt


def _main_html_only(html: str) -> str:
    """
    Fallback HTML (main-ish) for markdownify if trafilatura markdown is too short.
    Preference order: <main>, <article>, [role=main], then <body>.
    """
    soup = BeautifulSoup(html, "lxml")

    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
    )
    if main is None:
        return ""

    for t in main.find_all(["nav", "footer", "aside"]):
        t.decompose()

    return str(main)


def _markdownify_main_only(html: str) -> str:
    main_html = _main_html_only(html)
    if not main_html:
        return ""
    out = md(main_html, heading_style="ATX", bullets="*")
    out = (out or "").strip()
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out


def fetch_http(url: str, timeout: float = 20.0) -> FetchResult:
    with httpx.Client(
        headers={"User-Agent": UA},
        follow_redirects=True,
        timeout=timeout,
        verify=False,  # managed-mac pragmatic setting
        trust_env=False,
    ) as client:
        r = client.get(url)
        r.raise_for_status()

    html = r.text
    ct = (r.headers.get("Content-Type") or "").lower()

    is_html = ("text/html" in ct) or ("application/xhtml" in ct)

    text = _extract_text_plain(html) if is_html else ""
    text_md = _extract_text_markdown(html) if is_html else ""
    links = _extract_links(html, str(r.url)) if is_html else []

    # emergency fallback if trafilatura markdown is too short
    if is_html and len(text_md) < 300:
        fb = _markdownify_main_only(html)
        if len(fb) > len(text_md):
            text_md = fb

    return FetchResult(
        url=str(r.url),
        status=int(r.status_code),
        content_type=ct,
        html=html,
        text=text,
        text_md=text_md,
        links=links,
        links_count=len(links),
    )


def fetch_rendered(url: str, browser, timeout_ms: int = 30_000) -> FetchResult:
    page = browser.new_page(user_agent=UA)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        html = page.content()
        links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    finally:
        page.close()

    text = _extract_text_plain(html)
    text_md = _extract_text_markdown(html)

    # emergency fallback if trafilatura markdown is too short
    if len(text_md) < 300:
        fb = _markdownify_main_only(html)
        if len(fb) > len(text_md):
            text_md = fb

    # dedupe links
    seen = set()
    deduped = []
    for u in links:
        if not u:
            continue
        u, _ = urldefrag(u)
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    return FetchResult(
        url=url,
        status=200,
        content_type="text/html (rendered)",
        html=html,
        text=text,
        text_md=text_md,
        links=deduped,
        links_count=len(deduped),
    )


def needs_browser(
    r: FetchResult, min_links: int = 10, min_text_chars: int = 800
) -> bool:
    # Use markdown length as the “thin page” indicator
    if r.links_count < min_links:
        return True
    if len(r.text_md or "") < min_text_chars:
        return True
    return False
