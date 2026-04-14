#!/usr/bin/env python3
"""
DataForSEO SEO Audit CLI
========================
Runs a full SEO audit for a domain and outputs JSON, Markdown, and/or PDF.

Usage:
    python tools/seo_audit_cli.py enricoviola.com
    python tools/seo_audit_cli.py enricoviola.com --format pdf
    python tools/seo_audit_cli.py enricoviola.com --format all
    python tools/seo_audit_cli.py enricoviola.com --format json md
    python tools/seo_audit_cli.py enricoviola.com --mock
    python tools/seo_audit_cli.py enricoviola.com --location uk
    python tools/seo_audit_cli.py enricoviola.com --output-dir /tmp/audits
    python tools/seo_audit_cli.py enricoviola.com --deep            # per-page gap analysis (paid)
    python tools/seo_audit_cli.py enricoviola.com --mock --deep     # deep mode with mock data

Available location shortcuts:
    uk  → 2826  (United Kingdom, default)
    us  → 2840  (United States)
    au  → 2036  (Australia)
    ca  → 2124  (Canada)
    de  → 2276  (Germany)
    fr  → 2250  (France)
    it  → 2380  (Italy)
    es  → 2724  (Spain)
    nl  → 2528  (Netherlands)
    (or pass a numeric DataForSEO location_code directly)
"""
import argparse
import asyncio
import sys
from pathlib import Path

# ── Bootstrap: ensure project root is on sys.path ─────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Load .env and fix Python 3.14 pydantic.v1 compat ─────────────────────────
# Must happen before any project imports that touch langfuse/pydantic
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import app._compat  # noqa: F401  — pydantic.v1 patch for Python 3.14

from app.services.dataforseo_audit import DataForSEOAuditService


LOCATION_MAP = {
    "us": 2840,
    "uk": 2826,
    "au": 2036,
    "ca": 2124,
    "de": 2276,
    "fr": 2250,
    "it": 2380,
    "es": 2724,
    "nl": 2528,
}


def parse_location(value: str) -> int:
    """Accept a location shortcode (us/uk/au…) or a raw integer."""
    if value.lower() in LOCATION_MAP:
        return LOCATION_MAP[value.lower()]
    try:
        return int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Unknown location '{value}'. "
            f"Use one of {list(LOCATION_MAP)} or a numeric DataForSEO location_code."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seo_audit_cli",
        description="Run a full DataForSEO SEO audit for a domain.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "domain",
        help="Domain to audit (e.g. enricoviola.com). Protocol and www are stripped automatically.",
    )
    parser.add_argument(
        "--format", "-f",
        nargs="+",
        choices=["json", "md", "pdf", "all"],
        default=["json", "md"],
        metavar="FORMAT",
        help=(
            "Output format(s): json, md, pdf, or all. "
            "Defaults to json and md. "
            "Example: --format json md pdf"
        ),
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="reports",
        help="Directory to write output files into (created if missing). Default: reports/",
    )
    parser.add_argument(
        "--location", "-l",
        default="uk",
        type=parse_location,
        metavar="LOCATION",
        help=(
            "Target location for keyword/SERP data. "
            "Shortcuts: uk (default), us, au, ca, de, fr, it, es, nl. "
            "Or pass a numeric DataForSEO location_code."
        ),
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use synthetic mock data instead of live API calls (no quota consumed).",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help=(
            "Run per-page SERP content gap analysis for keywords at positions 4–30. "
            "Adds a Per-Page Content Gaps section to the PDF. "
            "Expensive: consumes ~1 SERP + 3 content_parsing API calls per keyword."
        ),
    )
    parser.add_argument(
        "--standard",
        action="store_true",
        help=(
            "Use the DataForSEO Standard (task-based) method instead of Live. "
            "Cheaper per call but slower: each endpoint submits a task, polls "
            "tasks_ready, then fetches results. Adds ~10–60 s per endpoint. "
            "Live-only endpoints (Lighthouse, instant_pages, GBP) are unaffected."
        ),
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Use DataForSEO sandbox API (test data, no credits spent).",
    )
    parser.add_argument(
        "--business-context",
        type=str,
        default=None,
        metavar="CONTEXT",
        help=(
            'Business context for the executive summary LLM prompt. '
            'Example: "dental practice in Manchester"'
        ),
    )
    parser.add_argument(
        "--ai-visibility",
        action="store_true",
        help=(
            "Enable Tier 4: AI Visibility analysis (LLM mentions, brand SERP features). "
            "Adds ~3-7 extra API calls."
        ),
    )
    return parser


async def main():
    parser = build_parser()
    args = parser.parse_args()

    formats = args.format
    if "all" in formats:
        formats = ["json", "md", "pdf"]

    if args.mock:
        mode = "MOCK (no API calls)"
    elif args.sandbox:
        mode = "SANDBOX (test data)"
    elif args.standard:
        mode = "STANDARD (task-based, cheaper)"
    else:
        mode = "LIVE"

    print(f"\n{'='*60}")
    print(f"  DataForSEO SEO Audit")
    print(f"  Domain   : {args.domain}")
    print(f"  Formats  : {', '.join(formats)}")
    print(f"  Location : {args.location}")
    print(f"  Output   : {args.output_dir}/")
    print(f"  Mode     : {mode}")
    if args.deep:
        print(f"  Deep     : ON (per-page gap analysis)")
    if args.ai_visibility:
        print(f"  AI Vis.  : ON (LLM mentions + brand SERP)")
    if args.business_context:
        print(f"  Business : {args.business_context}")
    print(f"{'='*60}\n")

    service = DataForSEOAuditService(
        sandbox=args.sandbox,
        use_standard=args.standard,
        business_context=args.business_context,
        ai_visibility=args.ai_visibility,
    )

    try:
        result = await service.run_audit(
            domain=args.domain,
            output_dir=args.output_dir,
            formats=formats,
            location_code=args.location,
            mock=args.mock,
            deep=args.deep,
            ai_visibility=args.ai_visibility,
            business_context=args.business_context,
        )
    except ValueError as exc:
        msg = str(exc)
        if "DATAFORSEO_API_KEY" in msg or "api key" in msg.lower():
            print(f"\n✗  Configuration error: {exc}", file=sys.stderr)
            print("   Ensure DATAFORSEO_API_KEY is set in your .env file.", file=sys.stderr)
        else:
            print(f"\n✗  Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n✗  Audit failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print("  Audit complete. Files written:")
    for key in ("json_path", "md_path", "pdf_path"):
        if key in result:
            print(f"    {result[key]}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
