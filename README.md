![SpyScraper logo](https://cdn.midjourney.com/5850ec40-edcd-4771-8ec8-4ff031a990fe/0_2.png)

# SpyScraper

Automated competitive intelligence pipeline that crawls competitor websites, extracts key content, and generates structured analysis using OpenAI.

## What It Does

Point it at a competitor's domain and get back:
- **XLSX** — Structured scrape of all web content with AI-generated summaries
- **DOCX** — Competitive offering map ready for sales enablement

## Pipeline

```
Domain → Crawl → Score/Trim → Evidence Packs → XLSX → Summarize → DOCX
```

| Step | Output |
|------|--------|
| 1. Crawl | `pages.jsonl` — raw page content |
| 2. Trim/Score | `pages_scored.jsonl`, `snippets.jsonl` — ranked paragraphs |
| 3. Evidence | `evidence_packs.jsonl` — grouped by topic |
| 4. Export | `core_web_content_scrape.xlsx` — structured data |
| 5. Summarize | AI summaries added to XLSX |
| 6. Offering Map | `competitive_offering_map.docx` — final deliverable |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/joegelman/spyscraper.git
cd spyscraper
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Set OpenAI key
export OPENAI_API_KEY="sk-..."

# Run the wizard
python -m ci.wizard
```

## Wizard Options

| Parameter | Options | Default |
|-----------|---------|---------|
| Scrape size | 50 / 100 / 300 pages | 50 |
| Model | gpt-4o / gpt-5-mini / gpt-5.2 | gpt-5-mini |
| Request delay | 0.3s / 0.6s / 1.2s | 0.6s |
| Top-k paragraphs | 5-100 | 20 |

## Individual Scripts

Run pipeline steps independently:

```bash
python run_crawl.py          # Just crawl
python run_trim.py           # Score and trim content
python run_synthesize.py     # Build evidence packs
python run_report.py         # Generate XLSX
python run_offering_map.py   # Generate DOCX
```

## Output Structure

```
data/
└── competitor-domain/
    ├── crawl/
    │   └── pages.jsonl
    ├── scored/
    │   ├── pages_scored.jsonl
    │   ├── snippets.jsonl
    │   └── keep_urls.txt
    ├── evidence/
    │   └── evidence_packs.jsonl
    └── export/
        ├── core_web_content_scrape.xlsx
        └── competitive_offering_map.docx
```

## Requirements

- Python 3.10+
- OpenAI API key
- Playwright (for JS-rendered pages)

## Configuration

The wizard handles configuration interactively. For automated/batch runs, see `ci_run.py`.

## License

MIT
