"""
DataForSEO PDF report builder — three-tier edition.

Produces a branded A4 PDF audit report using ReportLab.
Sections:
  1. Executive Summary (LLM-generated when available)
  2. Domain Overview & Authority
  3. Organic Keyword Rankings
  4. Competitive Landscape
  5. Backlink Profile
  6. On-Page & Technical SEO
  7. Page Speed & Core Web Vitals
  8. Local SEO (Google Business Profile)
  9. AEO & AI Overview Readiness
 10. Per-Page Content Gaps (if --deep data present)
 11. Priority Recommendations
 12. Cost Appendix

Requires: pip install reportlab
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.services.dataforseo_client import first_result, safe_get

# ── Brand colours ──────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#0D1B2A")
BRAND_BLUE   = colors.HexColor("#1565C0")
BRAND_LIGHT  = colors.HexColor("#E3F2FD")
BRAND_ACCENT = colors.HexColor("#FF6F00")
BRAND_GREEN  = colors.HexColor("#2E7D32")
BRAND_RED    = colors.HexColor("#C62828")
BRAND_GREY   = colors.HexColor("#607D8B")
BRAND_TEAL   = colors.HexColor("#00695C")
WHITE        = colors.white
PAGE_W, PAGE_H = A4


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_int(v: Any) -> str:
    """Format a numeric API value as a comma-separated integer (no decimals)."""
    if v is None or v == "N/A":
        return "N/A"
    try:
        return f"{int(float(v)):,}"
    except (TypeError, ValueError):
        return str(v)


def _score_color(score: Any) -> Any:
    if score == "N/A":
        return BRAND_GREY
    try:
        v = int(float(score))
        if v < 50:   return BRAND_RED
        if v < 80:   return BRAND_ACCENT
        return BRAND_GREEN
    except (ValueError, TypeError):
        return BRAND_GREY


# ── Style helpers ──────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base   = getSampleStyleSheet()
    extras = {
        "Cover_Title": ParagraphStyle(
            "Cover_Title", fontName="Helvetica-Bold",
            fontSize=32, textColor=WHITE, leading=40),
        "Cover_Sub": ParagraphStyle(
            "Cover_Sub", fontName="Helvetica",
            fontSize=15, textColor=colors.HexColor("#BBDEFB"), leading=22),
        "Cover_Meta": ParagraphStyle(
            "Cover_Meta", fontName="Helvetica",
            fontSize=11, textColor=WHITE, leading=18),
        "Section_Title": ParagraphStyle(
            "Section_Title", fontName="Helvetica-Bold",
            fontSize=18, textColor=BRAND_BLUE, spaceBefore=16, spaceAfter=6),
        "Sub_Title": ParagraphStyle(
            "Sub_Title", fontName="Helvetica-Bold",
            fontSize=12, textColor=BRAND_DARK, spaceBefore=10, spaceAfter=4),
        "Body": ParagraphStyle(
            "Body", fontName="Helvetica",
            fontSize=10, textColor=BRAND_DARK, leading=15, spaceAfter=5),
        "Body_Italic": ParagraphStyle(
            "Body_Italic", fontName="Helvetica-Oblique",
            fontSize=10, textColor=BRAND_GREY, leading=15, spaceAfter=5),
        "Small": ParagraphStyle(
            "Small", fontName="Helvetica",
            fontSize=8, textColor=BRAND_GREY, leading=11),
        "TOC_Item": ParagraphStyle(
            "TOC_Item", fontName="Helvetica",
            fontSize=11, textColor=BRAND_DARK, leading=20, leftIndent=10),
        "Callout": ParagraphStyle(
            "Callout", fontName="Helvetica-Bold",
            fontSize=11, textColor=BRAND_TEAL, leading=16, spaceAfter=6),
    }
    return {**{k: base[k] for k in base.byName}, **extras}


def _divider(color=BRAND_BLUE) -> HRFlowable:
    return HRFlowable(width="100%", thickness=1, color=color,
                      spaceAfter=8, spaceBefore=4)


def _metric_cards(metrics: list) -> Table:
    """Row of KPI cards. Each metric: {label, value, color}"""
    n  = len(metrics)
    cw = (PAGE_W - 40 * mm) / n
    vals = [
        Paragraph(
            f'<font color="{m["color"].hexval()}"><b>{html.escape(str(m["value"]))}</b></font>',
            ParagraphStyle("mv", fontName="Helvetica-Bold", fontSize=20,
                           textColor=m["color"], alignment=TA_CENTER),
        )
        for m in metrics
    ]
    labs = [
        Paragraph(
            html.escape(m["label"]),
            ParagraphStyle("ml", fontName="Helvetica", fontSize=8,
                           textColor=BRAND_GREY, alignment=TA_CENTER),
        )
        for m in metrics
    ]
    t = Table([vals, labs], colWidths=[cw] * n, rowHeights=[30, 16])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
        ("INNERGRID",     (0, 0), (-1, -1), 0,   WHITE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _data_table(headers: list, rows: list, col_widths=None) -> Table:
    hdr_s = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9,
                            textColor=WHITE, alignment=TA_CENTER)
    cel_s = ParagraphStyle("td", fontName="Helvetica", fontSize=8,
                            textColor=BRAND_DARK, leading=12)
    hdr_row   = [Paragraph(html.escape(h), hdr_s) for h in headers]
    body_rows = [[Paragraph(html.escape(str(c)), cel_s) for c in row] for row in rows]
    t = Table([hdr_row] + body_rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), BRAND_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#E0E0E0")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t


def _signal_row(label: str, ok: bool, styles: dict) -> list:
    sym = "✓" if ok else "✗"
    col = BRAND_GREEN if ok else BRAND_RED
    p_s = ParagraphStyle("sig", fontName="Helvetica-Bold", fontSize=9,
                          textColor=col)
    p_l = ParagraphStyle("sigl", fontName="Helvetica", fontSize=9,
                          textColor=BRAND_DARK)
    return [Paragraph(sym, p_s), Paragraph(html.escape(label), p_l)]


def _header_footer(canvas, doc, domain: str):
    canvas.saveState()
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(0, PAGE_H - 28 * mm, PAGE_W, 28 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(WHITE)
    canvas.drawString(20 * mm, PAGE_H - 17 * mm, "SEO AUDIT REPORT")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(PAGE_W - 20 * mm, PAGE_H - 17 * mm, domain.upper())
    canvas.setFillColor(BRAND_LIGHT)
    canvas.rect(0, 0, PAGE_W, 14 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(BRAND_GREY)
    canvas.drawString(20 * mm, 5 * mm,
                      f"Confidential — {_now_utc().strftime('%B %Y')}")
    canvas.drawCentredString(PAGE_W / 2, 5 * mm, f"Page {doc.page}")
    canvas.drawRightString(PAGE_W - 20 * mm, 5 * mm, "Powered by DataForSEO")
    canvas.restoreState()


# ── Section builders ───────────────────────────────────────────────────────────

def _section_cover(story, domain, agency, styles):
    story += [
        Spacer(1, 42 * mm),
        Paragraph("SEO AUDIT REPORT", styles["Cover_Title"]),
        Spacer(1, 4 * mm),
        Paragraph(domain.upper(), ParagraphStyle(
            "dom", fontName="Helvetica-Bold", fontSize=24,
            textColor=BRAND_ACCENT, leading=30)),
        Spacer(1, 8 * mm),
        Paragraph(
            "A comprehensive three-tier analysis: organic performance, technical health, "
            "backlink authority, local SEO, and AI Overview readiness.",
            styles["Cover_Sub"]),
        Spacer(1, 28 * mm),
        Paragraph(f"Prepared by: <b>{html.escape(agency)}</b>",  styles["Cover_Meta"]),
        Paragraph(f"Date: <b>{_now_utc().strftime('%B %d, %Y')}</b>", styles["Cover_Meta"]),
        Paragraph("Data source: DataForSEO API v3", styles["Cover_Meta"]),
        PageBreak(),
    ]


def _section_toc(story, has_deep: bool, styles):
    story += [Paragraph("TABLE OF CONTENTS", styles["Section_Title"]), _divider()]
    toc = [
        ("1",  "Executive Summary"),
        ("2",  "Domain Overview &amp; Authority"),
        ("3",  "Organic Keyword Rankings"),
        ("4",  "Competitive Landscape"),
        ("5",  "Backlink Profile"),
        ("6",  "On-Page &amp; Technical SEO"),
        ("7",  "Page Speed &amp; Core Web Vitals"),
        ("8",  "Local SEO — Google Business Profile"),
        ("9",  "AEO &amp; AI Overview Readiness"),
    ]
    if has_deep:
        toc.append(("10", "Per-Page Content Gaps"))
        toc.append(("11", "Priority Recommendations"))
        toc.append(("—",  "Appendix A: Implementation Guides"))
        toc.append(("—",  "Appendix B: Rank Math WordPress SEO"))
        toc.append(("12", "Cost Appendix"))
    else:
        toc.append(("10", "Priority Recommendations"))
        toc.append(("—",  "Appendix A: Implementation Guides"))
        toc.append(("—",  "Appendix B: Rank Math WordPress SEO"))
        toc.append(("11", "Cost Appendix"))

    for num, title in toc:
        story.append(Paragraph(f"<b>{num}.</b>  {title}", styles["TOC_Item"]))
    story.append(PageBreak())


def _section_executive_summary(story, data, styles):
    exe = data.get("executive_summary") or {}
    ov_result = first_result(data.get("overview", {})) or {}
    ov_items  = safe_get(ov_result, "items", default=[]) or []
    ov  = ov_items[0] if ov_items else {}
    bl  = first_result(data.get("backlinks", {})) or {}

    story += [Paragraph("1. Executive Summary", styles["Section_Title"]), _divider()]

    # KPI cards
    story.append(_metric_cards([
        {"label": "Pos #1 Keywords",      "value": str(safe_get(ov, "metrics", "organic", "pos_1")),           "color": BRAND_BLUE},
        {"label": "Organic Keywords",     "value": str(safe_get(ov, "metrics", "organic", "count")),           "color": BRAND_BLUE},
        {"label": "Est. Monthly Traffic", "value": _fmt_int(safe_get(ov, "metrics", "organic", "etv")),        "color": BRAND_GREEN},
        {"label": "Total Backlinks",      "value": str(safe_get(bl, "backlinks")),                             "color": BRAND_BLUE},
        {"label": "Referring Domains",    "value": str(safe_get(bl, "referring_domains")),                     "color": BRAND_BLUE},
    ]))
    story.append(Spacer(1, 5 * mm))

    # LLM-generated state summary
    state = exe.get("state_summary", "")
    if state:
        story.append(Paragraph(html.escape(state), styles["Body"]))
    else:
        story.append(Paragraph(
            f"This report covers <b>{html.escape(data.get('domain', 'unknown'))}</b> "
            "across Tiers 0–3 using live DataForSEO data. "
            "Full findings are in Sections 2–9; recommendations in Section 10.",
            styles["Body"]))

    story.append(Spacer(1, 4 * mm))

    # AEO summary
    aeo_s = exe.get("aeo_summary", "")
    if aeo_s:
        story.append(Paragraph("AI Overview &amp; Local Search", styles["Sub_Title"]))
        story.append(Paragraph(html.escape(aeo_s), styles["Body"]))

    # Top 5 opportunities (if LLM generated them)
    opps = exe.get("opportunities", [])
    if opps:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Top 5 Opportunities", styles["Sub_Title"]))
        cw   = PAGE_W - 40 * mm
        rows = [
            [str(o.get("rank", "")), o.get("title", ""), o.get("description", ""),
             o.get("expected_impact", ""), o.get("effort", "")]
            for o in opps[:5]
        ]
        story.append(_data_table(
            ["#", "Opportunity", "Description", "Impact", "Effort"],
            rows,
            col_widths=[cw * 0.04, cw * 0.20, cw * 0.48, cw * 0.14, cw * 0.14]))

    # Workstreams
    ws = exe.get("workstreams", {})
    if ws:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Workstream Split", styles["Sub_Title"]))
        ws_rows = [
            ["Developer",    ", ".join(ws.get("developer",   []))],
            ["VA / Content", ", ".join(ws.get("va_content",  []))],
            ["Consultancy",  ", ".join(ws.get("consultancy", []))],
        ]
        story.append(_data_table(
            ["Workstream", "Tasks"],
            ws_rows,
            col_widths=[cw * 0.20, cw * 0.80]))

    # Dev time estimate
    dte = exe.get("dev_time_estimate", {})
    if dte.get("total_hours"):
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"<b>Estimated implementation time:</b> "
            f"{html.escape(str(dte['total_hours']))} hours "
            f"({html.escape(dte.get('notes', 'single developer'))})",
            styles["Body"]))

    story.append(PageBreak())


def _section_domain_overview(story, data, styles):
    # domain_rank_overview: data is at tasks[0].result[0].items[0].metrics
    ov_result = first_result(data.get("overview", {})) or {}
    ov_items  = safe_get(ov_result, "items", default=[]) or []
    ov = ov_items[0] if ov_items else {}
    # WHOIS: data is at tasks[0].result[0].items[0]
    wh_result = first_result(data.get("whois", {})) or {}
    wh_items  = safe_get(wh_result, "items", default=[]) or []
    wh = wh_items[0] if wh_items else {}
    story += [Paragraph("2. Domain Overview &amp; Authority", styles["Section_Title"]), _divider()]
    cw = PAGE_W - 40 * mm
    rows = [
        ["Organic Keywords (count)",   safe_get(ov, "metrics", "organic", "count")],
        ["Est. Organic Traffic (ETV)", _fmt_int(safe_get(ov, "metrics", "organic", "etv"))],
        ["Rank #1 Keywords",           safe_get(ov, "metrics", "organic", "pos_1")],
        ["Rank #2–3 Keywords",         safe_get(ov, "metrics", "organic", "pos_2_3")],
        ["Rank #4–10 Keywords",        safe_get(ov, "metrics", "organic", "pos_4_10")],
        ["Paid Keywords (count)",      safe_get(ov, "metrics", "paid",    "count")],
        ["Domain Registered",          safe_get(wh, "created_datetime",   default="N/A")],
        ["Domain Expiry",              safe_get(wh, "expiration_datetime", default="N/A")],
        ["Registrar",                  safe_get(wh, "registrar",          default="N/A")],
    ]
    story.append(_data_table(["Metric", "Value"], rows,
                              col_widths=[cw * 0.65, cw * 0.35]))

    # Visibility trend (historical rank overview)
    hr_items = safe_get(data.get("historical_rank", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(hr_items, list) and hr_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Visibility Trend", styles["Sub_Title"]))
        story.append(Paragraph(
            "Organic keyword count and estimated traffic over recent months.",
            styles["Body"]))
        hr_rows = []
        for h in hr_items:
            period = f"{safe_get(h, 'year', default='')}-{str(safe_get(h, 'month', default='')).zfill(2)}"
            kw_count = safe_get(h, "metrics", "organic", "count", default="—")
            etv_val  = safe_get(h, "metrics", "organic", "etv", default="—")
            pos1     = safe_get(h, "metrics", "organic", "pos_1", default="—")
            hr_rows.append([period, str(kw_count), _fmt_int(etv_val), str(pos1)])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Period", "Keywords", "Est. Traffic", "#1 Rankings"],
            hr_rows,
            col_widths=[cw * 0.25, cw * 0.25, cw * 0.25, cw * 0.25]))

    # Technology stack
    tech_items = safe_get(data.get("technologies", {}), "tasks", 0, "result", 0, "items", default=[])
    tech_item = tech_items[0] if isinstance(tech_items, list) and tech_items else {}
    techs = safe_get(tech_item, "technologies", default=[]) or []
    if isinstance(techs, list) and techs:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Technology Stack", styles["Sub_Title"]))
        story.append(Paragraph(
            "CMS, analytics, CDN, and frameworks detected on the domain.",
            styles["Body"]))
        # Group by category
        by_cat: dict = {}
        for t in techs:
            cat = safe_get(t, "category", default="Other")
            name = safe_get(t, "name", default="Unknown")
            by_cat.setdefault(str(cat), []).append(str(name))
        tech_rows = [[cat, ", ".join(names)] for cat, names in sorted(by_cat.items())]
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Category", "Technologies"],
            tech_rows,
            col_widths=[cw * 0.30, cw * 0.70]))

    story.append(PageBreak())


def _section_keywords(story, data, styles):
    story += [Paragraph("3. Organic Keyword Rankings", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Top organic keywords by estimated traffic volume (ETV). "
        "Keywords at positions 4–10 represent quick-win optimisation opportunities.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    # Position distribution summary
    ov_result = first_result(data.get("overview", {})) or {}
    ov_items  = safe_get(ov_result, "items", default=[]) or []
    ov = ov_items[0] if ov_items else {}
    org = safe_get(ov, "metrics", "organic", default={}) or {}
    pos_1    = safe_get(org, "pos_1",    default=0)
    pos_23   = safe_get(org, "pos_2_3",  default=0)
    pos_410  = safe_get(org, "pos_4_10", default=0)
    pos_1120 = safe_get(org, "pos_11_20", default=0)
    pos_21   = safe_get(org, "pos_21_30", default=0)
    total    = safe_get(org, "count",    default=0)
    if any(v and v != "N/A" for v in [pos_1, pos_23, pos_410]):
        story.append(Paragraph("Position Distribution", styles["Sub_Title"]))
        story.append(Paragraph(
            "Keywords grouped by SERP position. Positions 1–3 drive the majority of clicks; "
            "positions 4–10 are high-value optimisation targets.",
            styles["Body"]))
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Position Band", "Keywords", "Notes"],
            [
                ["#1",       str(pos_1),    "Top position — strong authority signals required"],
                ["#2–3",     str(pos_23),   "Near-top — title/meta and internal linking improvements can push to #1"],
                ["#4–10",    str(pos_410),  "Page 1 — quick-win optimisation targets"],
                ["#11–20",   str(pos_1120) if pos_1120 and pos_1120 != "N/A" else "—",
                             "Page 2 — content depth and E-E-A-T signals needed"],
                ["#21–30",   str(pos_21)   if pos_21   and pos_21   != "N/A" else "—",
                             "Early page 3 — competitive gap analysis recommended"],
                ["Total",    str(total),   "All tracked organic keywords"],
            ],
            col_widths=[cw * 0.14, cw * 0.14, cw * 0.72]))
        story.append(Spacer(1, 5 * mm))

    items = safe_get(data.get("keywords", {}), "tasks", 0, "result", 0, "items", default=[])
    if not isinstance(items, list): items = []

    # Keyword difficulty lookup
    kd_map: dict = {}
    kd_items = safe_get(data.get("keyword_difficulty", {}), "tasks", 0, "result", 0, "items", default=[])
    for kdi in (kd_items if isinstance(kd_items, list) else []):
        kd_map[safe_get(kdi, "keyword", default="")] = safe_get(kdi, "keyword_difficulty", default="—")

    # Search intent lookup
    intent_map: dict = {}
    si_items = safe_get(data.get("search_intent", {}), "tasks", 0, "result", 0, "items", default=[])
    for si in (si_items if isinstance(si_items, list) else []):
        intent_map[safe_get(si, "keyword", default="")] = safe_get(si, "search_intent", default="—")

    rows = []
    for item in items[:25]:
        kw  = safe_get(item, "keyword_data", "keyword", default="—")
        pos = safe_get(item, "ranked_serp_element", "serp_item", "rank_absolute", default="—")
        vol = safe_get(item, "keyword_data", "keyword_info", "search_volume", default="—")
        etv = safe_get(item, "ranked_serp_element", "serp_item", "etv", default="—")
        kd  = kd_map.get(str(kw), "—")
        intent = intent_map.get(str(kw), "—")
        rows.append([
            kw, str(pos),
            f"{vol:,}" if isinstance(vol, int) else str(vol),
            f"{etv:,.0f}" if isinstance(etv, (int, float)) else str(etv),
            str(kd), str(intent),
        ])

    if rows:
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Keyword", "Pos", "Volume", "Traffic", "KD", "Intent"],
            rows,
            col_widths=[cw * 0.28, cw * 0.06, cw * 0.10, cw * 0.10, cw * 0.08, cw * 0.38]))
    else:
        story.append(Paragraph("No keyword data available.", styles["Body"]))

    # Keyword gap
    gap_items = safe_get(data.get("keyword_gap", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(gap_items, list) and gap_items:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Keyword Gap (Competitor-only Keywords)", styles["Sub_Title"]))
        story.append(Paragraph(
            "Keywords that top competitors rank for but this domain does not — "
            "each represents an untapped content opportunity.",
            styles["Body"]))
        gap_rows = []
        for gi in gap_items[:15]:
            kw = safe_get(gi, "keyword_data", "keyword", default="—")
            sv = safe_get(gi, "keyword_data", "keyword_info", "search_volume", default="—")
            gap_rows.append([kw, _fmt_int(sv)])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Gap Keyword", "Search Volume"],
            gap_rows,
            col_widths=[cw * 0.70, cw * 0.30]))

    # Related keyword opportunities
    rk_items = safe_get(data.get("related_keywords", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(rk_items, list) and rk_items:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Related Keyword Opportunities", styles["Sub_Title"]))
        story.append(Paragraph(
            "Semantically related terms that could expand topical authority. "
            "Creating dedicated pages or sections for these terms builds the site's "
            "thematic relevance cluster.",
            styles["Body"]))
        rk_rows = []
        for rk in rk_items[:15]:
            kw  = safe_get(rk, "keyword_data", "keyword", default="—")
            sv  = safe_get(rk, "keyword_data", "keyword_info", "search_volume", default="—")
            kd  = safe_get(rk, "keyword_data", "keyword_info", "keyword_difficulty", default="—")
            rk_rows.append([
                str(kw),
                _fmt_int(sv),
                str(kd),
            ])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Related Keyword", "Search Volume", "Difficulty"],
            rk_rows,
            col_widths=[cw * 0.60, cw * 0.22, cw * 0.18]))

    story.append(PageBreak())


def _section_competitors(story, data, styles):
    story += [Paragraph("4. Competitive Landscape", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Domains competing for the same organic keywords, ranked by estimated traffic.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    items = safe_get(data.get("competitors", {}), "tasks", 0, "result", 0, "items", default=[])
    if not isinstance(items, list): items = []

    rows = [[
        safe_get(c, "domain"),
        safe_get(c, "domain_rank"),
        safe_get(c, "metrics", "organic", "count"),
        _fmt_int(safe_get(c, "metrics", "organic", "etv")),
        safe_get(c, "avg_position"),
    ] for c in items[:10]]

    if rows:
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Competitor", "Domain Rank", "Organic KWs", "Est. Traffic", "Avg. Pos"],
            rows,
            col_widths=[cw * 0.34, cw * 0.14, cw * 0.14, cw * 0.18, cw * 0.20]))
    else:
        story.append(Paragraph("No competitor data available.", styles["Body"]))

    story.append(PageBreak())


def _section_backlinks(story, data, styles):
    story += [Paragraph("5. Backlink Profile", styles["Section_Title"]), _divider()]
    bl = first_result(data.get("backlinks", {})) or {}

    story.append(_metric_cards([
        {"label": "Total Backlinks",   "value": str(safe_get(bl, "backlinks")),         "color": BRAND_BLUE},
        {"label": "Referring Domains", "value": str(safe_get(bl, "referring_domains")), "color": BRAND_BLUE},
        {"label": "Referring IPs",     "value": str(safe_get(bl, "referring_ips")),     "color": BRAND_BLUE},
        {"label": "Broken Backlinks",  "value": str(safe_get(bl, "broken_backlinks")),  "color": BRAND_RED},
    ]))
    story.append(Spacer(1, 5 * mm))

    # Top referring domains
    story.append(Paragraph("Top Referring Domains", styles["Sub_Title"]))
    rd_items = safe_get(data.get("referring_domains", {}), "tasks", 0, "result", 0, "items", default=[])
    if not isinstance(rd_items, list): rd_items = []
    rows = [[
        safe_get(r, "domain"),
        safe_get(r, "rank"),
        safe_get(r, "backlinks"),
        "Yes" if safe_get(r, "dofollow") is True else "No",
        str(safe_get(r, "first_seen", default="—")),
    ] for r in rd_items[:20]]

    if rows:
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Referring Domain", "Rank", "Links", "Dofollow", "First Seen"],
            rows,
            col_widths=[cw * 0.38, cw * 0.12, cw * 0.10, cw * 0.12, cw * 0.28]))

    # Anchor text
    at_items = safe_get(data.get("anchor_text", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(at_items, list) and at_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Top Anchor Texts", styles["Sub_Title"]))
        story.append(Paragraph(
            "Anchor text diversity is a healthy link profile signal. "
            "Over-reliance on exact-match commercial anchors can attract manual penalties.",
            styles["Body"]))
        at_rows = [[
            safe_get(a, "anchor"),
            safe_get(a, "backlinks"),
            safe_get(a, "referring_domains"),
        ] for a in at_items[:10]]
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Anchor Text", "Backlinks", "Ref. Domains"],
            at_rows,
            col_widths=[cw * 0.60, cw * 0.20, cw * 0.20]))

    # Backlink growth trend — line chart
    bh_items = safe_get(data.get("backlinks_history", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(bh_items, list) and bh_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Backlink Growth Trend", styles["Sub_Title"]))
        story.append(Paragraph(
            "Historical backlink and referring domain counts. "
            "Steady, consistent growth signals natural link acquisition to Google.",
            styles["Body"]))
        cw = PAGE_W - 40 * mm
        chart = _backlink_chart(bh_items, width=float(cw), height=140)
        if chart is not None:
            story.append(Spacer(1, 2 * mm))
            story.append(chart)
        else:
            # Fallback to table if not enough data points
            bh_rows = [[str(safe_get(e, "date", default="—")),
                        str(safe_get(e, "backlinks", default="—")),
                        str(safe_get(e, "referring_domains", default="—"))]
                       for e in bh_items]
            story.append(_data_table(
                ["Date", "Backlinks", "Referring Domains"],
                bh_rows,
                col_widths=[cw * 0.34, cw * 0.33, cw * 0.33]))

    story.append(PageBreak())


def _backlink_chart(bh_items: list, width: float, height: float):
    """
    Build a ReportLab Drawing with a two-line chart showing backlink history.
    Returns a Drawing or None if there is insufficient data.
    """
    dates: list = []
    bl_vals: list = []
    rd_vals: list = []
    for entry in bh_items:
        date_val = safe_get(entry, "date", default="")
        bl_count = safe_get(entry, "backlinks", default=None)
        rd_count = safe_get(entry, "referring_domains", default=None)
        try:
            bl_vals.append(float(bl_count))
            rd_vals.append(float(rd_count))
            dates.append(str(date_val)[:7])
        except (TypeError, ValueError):
            continue

    n = len(dates)
    if n < 2:
        return None

    drawing = Drawing(width, height)

    margin_left, margin_bottom = 55, 35
    chart_w = width - margin_left - 20
    chart_h = height - margin_bottom - 30

    lp             = LinePlot()
    lp.x           = margin_left
    lp.y           = margin_bottom
    lp.width       = chart_w
    lp.height      = chart_h

    lp.data = [
        [(i, bl_vals[i]) for i in range(n)],
        [(i, rd_vals[i]) for i in range(n)],
    ]

    lp.lines[0].strokeColor = BRAND_BLUE
    lp.lines[0].strokeWidth = 2
    lp.lines[1].strokeColor = BRAND_ACCENT
    lp.lines[1].strokeWidth = 2

    lp.xValueAxis.valueMin  = 0
    lp.xValueAxis.valueMax  = n - 1
    lp.xValueAxis.valueSteps = list(range(n))
    _dates_ref = dates

    def _x_label(v, _d=_dates_ref, _n=n):
        try:
            idx = int(round(float(v)))
            if 0 <= idx < _n:
                return _d[idx]
        except (ValueError, TypeError, IndexError):
            pass
        return ""

    lp.xValueAxis.labelTextFormat = _x_label
    lp.xValueAxis.labels.angle    = 30
    lp.xValueAxis.labels.fontName = "Helvetica"
    lp.xValueAxis.labels.fontSize = 7
    lp.xValueAxis.labels.dx       = -8

    all_y = bl_vals + rd_vals
    ymax  = max(all_y) * 1.2 if all_y else 100
    lp.yValueAxis.valueMin    = 0
    lp.yValueAxis.valueMax    = ymax
    lp.yValueAxis.labels.fontName = "Helvetica"
    lp.yValueAxis.labels.fontSize = 7
    lp.yValueAxis.labelTextFormat = "%.0f"

    drawing.add(lp)

    # Simple legend
    legend_items = [("Backlinks", BRAND_BLUE), ("Referring Domains", BRAND_ACCENT)]
    lx = margin_left
    ly = height - 14
    for label, col in legend_items:
        drawing.add(Line(lx, ly, lx + 18, ly, strokeColor=col, strokeWidth=2))
        drawing.add(String(lx + 22, ly - 4, label,
                           fontName="Helvetica", fontSize=8, fillColor=BRAND_DARK))
        lx += 120

    return drawing


# Actionable fix guidance per OnPage issue type
_ISSUE_ACTIONS: dict = {
    "no_description":              "Write a unique 120–160 character meta description per page targeting the primary keyword",
    "is_broken":                   "Repair content or 301-redirect all broken pages; update internal links pointing to them",
    "is_4xx_code":                 "Redirect 404 pages with 301 to the nearest relevant live page, or restore the content",
    "is_5xx_code":                 "Investigate server errors immediately — Google stops crawling 5xx pages",
    "broken_links":                "Audit outgoing links and update or remove any pointing to dead pages",
    "duplicate_title_tag":         "Rewrite each title to be unique, 50–60 characters, containing the page's primary keyword",
    "duplicate_meta_tags":         "Write a unique, relevant meta description for every page",
    "no_h1_tag":                   "Add one H1 per page matching the page's primary keyword intent",
    "no_title":                    "Add a descriptive title tag (50–60 chars) to every page",
    "no_image_alt":                "Add descriptive alt text to all images — improves accessibility and Google Image search",
    "no_image_title":              "Add title attributes to images for additional context",
    "low_content_rate":            "Expand thin pages to 400+ words covering the topic in depth to satisfy search intent",
    "no_favicon":                  "Add a favicon for brand trust and browser tab recognition",
    "is_redirect":                 "Update internal links to point directly to final destination URLs, bypassing redirects",
    "https_to_http_links":         "Update all internal links from http:// to https:// to eliminate mixed-content warnings",
    "has_render_blocking_resources": "Defer or async-load non-critical JS/CSS; identify files via Google PageSpeed Insights",
    "no_encoding_meta_tag":        "Add <meta charset='utf-8'> to every page's <head> section",
    "large_page_size":             "Compress images (WebP), minify CSS/JS, and remove unused scripts to reduce page weight",
    "title_too_long":              "Trim titles to 50–60 characters — Google truncates longer titles in search results",
    "title_too_short":             "Expand titles to 30+ characters and include the primary target keyword",
    "canonical_to_broken":         "Update canonical tags to point to live, indexable destination URLs",
    "canonical_to_redirect":       "Update canonical tags to point directly to the final URL, not via a redirect",
    "has_links_to_redirects":      "Update internal links to point directly to the final destination, skipping redirect hops",
    "irrelevant_description":      "Rewrite meta descriptions to be directly relevant to the specific page content",
}


def _section_onpage(story, data, styles):
    story += [Paragraph("6. On-Page &amp; Technical SEO", styles["Section_Title"]), _divider()]
    summary = first_result(data.get("onpage_summary", {})) or {}
    pm     = safe_get(summary, "page_metrics", default={}) or {}
    checks = safe_get(pm, "checks", default={}) or {}

    # Metric cards — read from the correct locations in the API response
    broken_pages     = int(checks.get("is_broken",    0) or 0)
    broken_resources = int(safe_get(pm, "broken_resources", default=0) or 0)
    dup_titles       = int(safe_get(pm, "duplicate_title", default=0) or checks.get("duplicate_title_tag", 0) or 0)
    missing_h1       = int(checks.get("no_h1_tag",     0) or 0)
    missing_desc     = int(checks.get("no_description", 0) or 0)
    pages_crawled    = int(safe_get(pm, "pages_crawled", default=0) or 0)
    op_score         = safe_get(pm, "onpage_score", default=None)

    op_score_str = "N/A"
    op_score_color = BRAND_GREY
    if op_score is not None:
        try:
            op_score_int = int(float(op_score))
            op_score_str = str(op_score_int)
            op_score_color = _score_color(op_score_int)
        except (TypeError, ValueError):
            pass

    story.append(_metric_cards([
        {"label": "OnPage Score",      "value": op_score_str,         "color": op_score_color},
        {"label": "Pages Crawled",     "value": str(pages_crawled),   "color": BRAND_BLUE},
        {"label": "Broken Pages",      "value": str(broken_pages),    "color": BRAND_RED   if broken_pages    > 0 else BRAND_GREEN},
        {"label": "Broken Resources",  "value": str(broken_resources),"color": BRAND_ACCENT if broken_resources > 0 else BRAND_GREEN},
        {"label": "Dup. Titles",       "value": str(dup_titles),      "color": BRAND_ACCENT if dup_titles     > 0 else BRAND_GREEN},
        {"label": "Missing Meta Desc", "value": str(missing_desc),    "color": BRAND_ACCENT if missing_desc   > 0 else BRAND_GREEN},
    ]))
    story.append(Spacer(1, 5 * mm))

    # Crawl overview table — richer stats from page_metrics
    links_int   = safe_get(pm, "links_internal",      default="—")
    links_ext   = safe_get(pm, "links_external",      default="—")
    non_idx     = safe_get(pm, "non_indexable",        default="—")
    dup_content = safe_get(pm, "duplicate_content",    default="—")
    dup_desc    = safe_get(pm, "duplicate_description",default="—")
    redir_loop  = safe_get(pm, "redirect_loop",        default="—")

    story.append(Paragraph("Crawl Overview", styles["Sub_Title"]))
    cw = PAGE_W - 40 * mm
    story.append(_data_table(
        ["Metric", "Value", "Metric", "Value"],
        [
            ["Internal Links",        str(links_int), "External Links",        str(links_ext)],
            ["Non-Indexable Pages",   str(non_idx),   "Duplicate Content",     str(dup_content)],
            ["Dup. Meta Descriptions",str(dup_desc),  "Redirect Loops",        str(redir_loop)],
            ["Missing H1 Tags",       str(missing_h1),"Missing Meta Desc",     str(missing_desc)],
        ],
        col_widths=[cw * 0.30, cw * 0.20, cw * 0.30, cw * 0.20]))
    story.append(Spacer(1, 5 * mm))

    # Issues by type — with actionable fix guidance
    story.append(Paragraph("Issues by Type", styles["Sub_Title"]))
    story.append(Paragraph(
        "All issues are ranked by page count. "
        "Fix 'High-impact' issues first — broken pages, missing meta descriptions, and render-blocking "
        "resources have the greatest effect on crawlability, CTR, and page speed.",
        styles["Body"]))
    issues = safe_get(data.get("onpage_issues", {}), "tasks", 0, "result", default=[])
    if not isinstance(issues, list):
        issues = []
    rows = []
    for i in issues[:20]:
        issue_key = safe_get(i, "issue_type", default="")
        desc      = safe_get(i, "issue_description", default="—")
        count     = safe_get(i, "pages_count", default="—")
        action    = _ISSUE_ACTIONS.get(str(issue_key), "Review and remediate per Google Search Central guidelines")
        rows.append([str(count), str(desc), action])
    if rows:
        story.append(_data_table(
            ["Pages", "Issue", "Recommended Action"],
            rows,
            col_widths=[cw * 0.08, cw * 0.30, cw * 0.62]))

    # Per-page audit table — uses onpage_pages (ordered by word count desc in collect_data)
    page_items = safe_get(data.get("onpage_pages", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(page_items, list) and page_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Crawled Pages — Audit Detail", styles["Sub_Title"]))
        story.append(Paragraph(
            "Per-page OnPage score, word count, and key issue flags. "
            "Pages scoring below 70 have multiple fixable issues. "
            "Low word counts on commercial/service pages indicate thin content.",
            styles["Body"]))
        page_rows = []
        for pg in page_items[:20]:
            url   = str(safe_get(pg, "url", default="—"))
            # Shorten URL to path only for readability
            try:
                from urllib.parse import urlparse
                path = urlparse(url).path or "/"
            except Exception:
                path = url
            if len(path) > 45:
                path = path[:42] + "…"

            pg_score = safe_get(pg, "onpage_score", default=None)
            pg_score_str = "—"
            if pg_score is not None:
                try:
                    pg_score_str = str(int(float(pg_score)))
                except (TypeError, ValueError):
                    pass

            wc = safe_get(pg, "meta", "content", "plain_text_word_count", default=None)
            wc_str = f"{int(wc):,}" if wc is not None else "—"

            pg_checks = safe_get(pg, "checks", default={}) or {}
            flags = []
            if pg_checks.get("no_description"):  flags.append("No desc")
            if pg_checks.get("no_h1_tag"):       flags.append("No H1")
            if pg_checks.get("no_image_alt"):    flags.append("No img alt")
            if pg_checks.get("low_content_rate"):flags.append("Thin content")
            if pg_checks.get("has_render_blocking_resources"): flags.append("Render-blocking")
            if pg_checks.get("is_broken"):       flags.append("Broken")
            if not pg_checks.get("has_micromarkup"): flags.append("No schema")
            res_errs = safe_get(pg, "resource_errors_count", default=0)
            if res_errs and int(res_errs) > 0:   flags.append(f"{res_errs} res.err")

            page_rows.append([path, pg_score_str, wc_str, ", ".join(flags) if flags else "✓ No issues"])

        story.append(_data_table(
            ["Page", "Score", "Words", "Issues"],
            page_rows,
            col_widths=[cw * 0.42, cw * 0.08, cw * 0.10, cw * 0.40]))

    # Non-indexable pages
    ni_items = safe_get(data.get("onpage_non_indexable", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(ni_items, list) and ni_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Non-Indexable Pages", styles["Sub_Title"]))
        ni_rows = [[safe_get(n, "url"), safe_get(n, "reason")] for n in ni_items[:10]]
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["URL", "Reason"],
            ni_rows,
            col_widths=[cw * 0.65, cw * 0.35]))

    # Duplicate title/meta tags
    dt_items = safe_get(data.get("duplicate_tags", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(dt_items, list) and dt_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Duplicate Title / Meta Tags", styles["Sub_Title"]))
        story.append(Paragraph(
            "Pages sharing identical title or meta description tags. "
            "Each group should have a unique, descriptive tag.",
            styles["Body"]))
        dt_rows = []
        for d in dt_items[:15]:
            url = safe_get(d, "url", default="—")
            tag_type = safe_get(d, "accumulator", default="—")
            tag_val = safe_get(d, "title", default=safe_get(d, "description", default="—"))
            dt_rows.append([str(url), str(tag_type), str(tag_val)])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["URL", "Tag Type", "Duplicate Value"],
            dt_rows,
            col_widths=[cw * 0.45, cw * 0.15, cw * 0.40]))

    # Duplicate content
    dc_items = safe_get(data.get("duplicate_content", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(dc_items, list) and dc_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Duplicate Content", styles["Sub_Title"]))
        story.append(Paragraph(
            "Near-duplicate page pairs. Consider adding canonical tags or merging content.",
            styles["Body"]))
        dc_rows = []
        for d in dc_items[:10]:
            url1 = safe_get(d, "url", default="—")
            url2 = safe_get(d, "page_from_url", default="—")
            sim = safe_get(d, "similarity", default="—")
            try:
                sim_str = f"{float(sim) * 100:.0f}%"
            except (TypeError, ValueError):
                sim_str = str(sim)
            dc_rows.append([str(url1), str(url2), sim_str])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Page A", "Page B", "Similarity"],
            dc_rows,
            col_widths=[cw * 0.40, cw * 0.40, cw * 0.20]))

    # Redirect chains
    rc_items = safe_get(data.get("redirect_chains", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(rc_items, list) and rc_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Redirect Chains", styles["Sub_Title"]))
        story.append(Paragraph(
            "Multi-hop redirects that waste crawl budget and dilute PageRank. "
            "Resolve to a single 301 redirect where possible.",
            styles["Body"]))
        rc_rows = []
        for r in rc_items[:10]:
            url_from = safe_get(r, "url", default="—")
            url_to = safe_get(r, "redirect_url", default="—")
            hops = safe_get(r, "chain_size", default="—")
            rc_rows.append([str(url_from), str(url_to), str(hops)])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Origin URL", "Redirect Target", "Hops"],
            rc_rows,
            col_widths=[cw * 0.40, cw * 0.40, cw * 0.20]))

    # Broken resources
    br_items = safe_get(data.get("broken_resources", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(br_items, list) and br_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Broken Resources (Images / CSS / JS)", styles["Sub_Title"]))
        story.append(Paragraph(
            "Resources returning 4xx/5xx status codes. Broken resources degrade user experience "
            "and waste server requests.",
            styles["Body"]))
        br_rows = []
        for b in br_items[:15]:
            res_url = safe_get(b, "url", default="—")
            res_type = safe_get(b, "resource_type", default="—")
            status = safe_get(b, "status_code", default="—")
            page = safe_get(b, "page_url", default="—")
            br_rows.append([str(res_url), str(res_type), str(status), str(page)])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Resource URL", "Type", "Status", "Found On"],
            br_rows,
            col_widths=[cw * 0.35, cw * 0.12, cw * 0.10, cw * 0.43]))

    story.append(PageBreak())


def _lh_score_int(raw: Any) -> int:
    """Convert a Lighthouse score (0.0–1.0 float or already 0–100 int) to 0–100 int."""
    if raw is None:
        return 0
    try:
        v = float(raw)
        return int(v * 100) if v <= 1.0 else int(v)
    except (TypeError, ValueError):
        return 0


def _section_page_speed(story, data, styles):
    story += [Paragraph("7. Page Speed &amp; Core Web Vitals", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Scores are from the Google Lighthouse audit run against the homepage. "
        "Performance, Accessibility, Best Practices, and SEO are each rated 0–100. "
        "Green ≥ 80 · Amber 50–79 · Red &lt; 50.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    # ── Lighthouse category scores ─────────────────────────────────────────────
    lh_result = first_result(data.get("lighthouse", {})) or {}
    lh_items  = safe_get(lh_result, "items", default=[]) or []
    lh_item   = lh_items[0] if lh_items else {}
    cats      = safe_get(lh_item, "categories", default={}) or {}
    audits    = safe_get(lh_item, "audits",     default={}) or {}

    perf = _lh_score_int(safe_get(cats, "performance",    "score", default=None))
    a11y = _lh_score_int(safe_get(cats, "accessibility",  "score", default=None))
    bp   = _lh_score_int(safe_get(cats, "best-practices", "score", default=None))
    seo  = _lh_score_int(safe_get(cats, "seo",            "score", default=None))

    if any([perf, a11y, bp, seo]):
        story.append(Paragraph("Lighthouse Category Scores", styles["Sub_Title"]))
        story.append(_metric_cards([
            {"label": "Performance",    "value": str(perf), "color": _score_color(perf)},
            {"label": "Accessibility",  "value": str(a11y), "color": _score_color(a11y)},
            {"label": "Best Practices", "value": str(bp),   "color": _score_color(bp)},
            {"label": "SEO",            "value": str(seo),  "color": _score_color(seo)},
        ]))
        story.append(Spacer(1, 5 * mm))

        # ── Core Web Vitals from Lighthouse audits ─────────────────────────────
        _CWV = [
            ("largest-contentful-paint", "Largest Contentful Paint (LCP)", "< 2.5 s"),
            ("total-blocking-time",       "Total Blocking Time (TBT)",       "< 200 ms"),
            ("cumulative-layout-shift",   "Cumulative Layout Shift (CLS)",   "< 0.1"),
            ("speed-index",               "Speed Index",                     "< 3.4 s"),
            ("first-contentful-paint",    "First Contentful Paint (FCP)",    "< 1.8 s"),
            ("interactive",               "Time to Interactive (TTI)",        "< 3.8 s"),
        ]
        cwv_rows = []
        for audit_id, label, threshold in _CWV:
            entry = audits.get(audit_id, {})
            display = safe_get(entry, "displayValue", default="—")
            raw_sc  = safe_get(entry, "score",        default=None)
            sc_int  = _lh_score_int(raw_sc) if raw_sc is not None else None
            if sc_int is not None:
                rating = "Good" if sc_int >= 90 else ("Needs improvement" if sc_int >= 50 else "Poor")
            else:
                rating = "—"
            cwv_rows.append([label, str(display), threshold, rating])

        cwv_rows_with_data = [r for r in cwv_rows if r[1] != "—"]
        if cwv_rows_with_data:
            story.append(Paragraph("Core Web Vitals", styles["Sub_Title"]))
            cw = PAGE_W - 40 * mm
            story.append(_data_table(
                ["Metric", "Measured", "Good Threshold", "Rating"],
                cwv_rows_with_data,
                col_widths=[cw * 0.44, cw * 0.18, cw * 0.20, cw * 0.18]))
            story.append(Spacer(1, 4 * mm))

    # ── Instant Pages timing (fallback / supplement) ───────────────────────────
    ps      = first_result(data.get("page_speed", {})) or {}
    ps_items = safe_get(ps, "items", default=[]) or []
    ps_item  = ps_items[0] if ps_items else {}
    timing   = safe_get(ps_item, "page_timing", default={}) or {}
    op_score = safe_get(ps_item, "onpage_score", default=None)

    def _fmt_ms(v):
        if v is None or v == 0:
            return "—"
        try:
            ms = int(v)
            return f"{ms / 1000:.1f} s" if ms >= 1000 else f"{ms} ms"
        except (TypeError, ValueError):
            return str(v)

    timing_rows = []
    if timing.get("largest_contentful_paint"):
        timing_rows.append(["LCP",  _fmt_ms(timing["largest_contentful_paint"]), "< 2.5 s"])
    if timing.get("time_to_interactive"):
        timing_rows.append(["TTI",  _fmt_ms(timing["time_to_interactive"]),      "< 3.8 s"])
    if timing.get("dom_complete"):
        timing_rows.append(["DOM Complete", _fmt_ms(timing["dom_complete"]),     "< 3.0 s"])
    if timing.get("waiting_time"):
        timing_rows.append(["TTFB", _fmt_ms(timing["waiting_time"]),             "< 600 ms"])

    if timing_rows or op_score is not None:
        story.append(Paragraph("Raw Page Timing (DataForSEO Instant Pages)", styles["Sub_Title"]))
        cards = []
        if op_score is not None:
            try:
                op_int = int(float(op_score))
                cards.append({"label": "OnPage Score", "value": str(op_int), "color": _score_color(op_int)})
            except (TypeError, ValueError):
                pass
        if cards:
            story.append(_metric_cards(cards))
            story.append(Spacer(1, 4 * mm))
        if timing_rows:
            cw = PAGE_W - 40 * mm
            story.append(_data_table(
                ["Metric", "Measured", "Good Threshold"],
                timing_rows,
                col_widths=[cw * 0.52, cw * 0.24, cw * 0.24]))

    if not any([perf, a11y, bp, seo]) and not timing_rows and op_score is None:
        story.append(Paragraph("No page speed data was collected for this domain.", styles["Body_Italic"]))

    story.append(PageBreak())


def _section_local_seo(story, data, styles):
    story += [Paragraph("8. Local SEO — Google Business Profile", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Google Business Profile is the most impactful lever for local search and Google Maps visibility. "
        "For an in-person therapy practice, appearing in the local pack is critical for bookings.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    aeo   = data.get("aeo_geo", {}) or {}
    local = aeo.get("local", {})

    gbp_found = local.get("gbp_found", False)
    if gbp_found:
        story.append(_metric_cards([
            {"label": "GBP Found",       "value": "Yes",
             "color": BRAND_GREEN},
            {"label": "Rating",          "value": str(local.get("gbp_rating", "N/A")),
             "color": BRAND_GREEN if (local.get("gbp_rating") or 0) >= 4.0 else BRAND_ACCENT},
            {"label": "Review Count",    "value": str(local.get("gbp_reviews", 0)),
             "color": BRAND_GREEN if int(local.get("gbp_reviews") or 0) >= 20 else BRAND_ACCENT},
            {"label": "In Local Pack",   "value": "Yes" if local.get("in_local_pack") else "No",
             "color": BRAND_GREEN if local.get("in_local_pack") else BRAND_RED},
        ]))
        story.append(Spacer(1, 4 * mm))
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Field", "Value"],
            [
                ["Business Name", str(local.get("gbp_name",    "N/A"))],
                ["Address",       str(local.get("gbp_address", "N/A"))],
                ["Rating",        str(local.get("gbp_rating",  "N/A"))],
                ["Reviews",       str(local.get("gbp_reviews", 0))],
                ["In Local Pack", "Yes" if local.get("in_local_pack") else "No"],
            ],
            col_widths=[cw * 0.30, cw * 0.70]))
    else:
        story.append(Paragraph(
            "⚠  No Google Business Profile was found for this domain. "
            "This is a critical gap for a local therapy practice. "
            "Creating and optimising a GBP listing should be the top priority action.",
            styles["Callout"]))

    # Recent reviews
    rev_items = safe_get(data.get("google_reviews", {}), "tasks", 0, "result", 0, "items", default=[])
    if isinstance(rev_items, list) and rev_items:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Recent Google Reviews", styles["Sub_Title"]))
        r_rows = []
        for r in rev_items[:5]:
            rating = safe_get(r, "rating", "value", default="")
            stars  = "★" * int(float(rating)) if rating else "—"
            text   = str(safe_get(r, "review_text", default="—"))[:120]
            r_rows.append([stars, text])
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Rating", "Review"],
            r_rows,
            col_widths=[cw * 0.12, cw * 0.88]))

    story.append(PageBreak())


def _section_aeo(story, data, styles):
    story += [Paragraph("9. AEO &amp; AI Overview Readiness", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Answer Engine Optimisation (AEO) and Generative Engine Optimisation (GEO) "
        "concern how a business appears in Google AI Overviews, ChatGPT responses, "
        "and other AI-generated answer systems. For a local therapy practice, "
        "strong E-E-A-T and structured data are the primary levers.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    aeo = data.get("aeo_geo", {}) or {}
    ai  = aeo.get("ai_overview", {})
    sc  = aeo.get("schema", {})
    ee  = aeo.get("eeat", {})
    recs = aeo.get("recommendations", [])

    score = ai.get("readiness_score", 0)
    label = ai.get("score_label", "")
    color = _score_color(score)

    story.append(_metric_cards([
        {"label": "AEO Readiness Score", "value": f"{score}/100", "color": color},
        {"label": "Schema Types",        "value": str(len(sc.get("types_detected", []))), "color": BRAND_BLUE},
        {"label": "E-E-A-T Signals",
         "value": str(sum(1 for k in ("has_about_page","has_contact_page","has_privacy_page") if ee.get(k))),
         "color": BRAND_BLUE},
        {"label": "Referring Domains",   "value": str(ee.get("referring_domains", 0)), "color": BRAND_BLUE},
    ]))
    story.append(Spacer(1, 5 * mm))

    # Signal checklist
    story.append(Paragraph("Signal Checklist", styles["Sub_Title"]))
    signals = [
        ("LocalBusiness / MedicalBusiness schema", sc.get("has_local_business", False)),
        ("FAQPage schema",                          sc.get("has_faq_page",       False)),
        ("Person / Practitioner schema",            sc.get("has_person",         False)),
        ("Review / AggregateRating schema",         sc.get("has_review_schema",  False)),
        ("About / Practitioner page",               ee.get("has_about_page",     False)),
        ("Contact page with NAP",                   ee.get("has_contact_page",   False)),
        ("Privacy policy page",                     ee.get("has_privacy_page",   False)),
        ("Google Business Profile",                 aeo.get("local", {}).get("gbp_found", False)),
        ("Appearing in local pack",                 aeo.get("local", {}).get("in_local_pack", False)),
    ]
    # Build as table
    hdr_s = ParagraphStyle("sigh", fontName="Helvetica-Bold", fontSize=9,
                            textColor=WHITE, alignment=TA_CENTER)
    body_rows_built = [[r[0], r[1]] for r in (_signal_row(lbl, ok, styles) for lbl, ok in signals)]
    cw = PAGE_W - 40 * mm
    t  = Table(body_rows_built, colWidths=[cw * 0.08, cw * 0.92])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#E0E0E0")),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    # AI Visibility (Tier 4 data)
    ai_vis = aeo.get("ai_visibility", {})
    llm_m = ai_vis.get("llm_mentions", {})
    serp_f = ai_vis.get("serp_features", {})
    if llm_m.get("mentions_found") or serp_f.get("keywords_checked"):
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("AI Visibility (Tier 4)", styles["Sub_Title"]))

        if llm_m.get("mentions_found"):
            story.append(Paragraph(
                f"Brand was mentioned <b>{llm_m.get('mention_count', 0)}</b> times "
                f"across LLM platforms: {', '.join(llm_m.get('platforms', ['none detected']))}. "
                f"Aggregated impressions: <b>{llm_m.get('aggregated_impressions', 0):,}</b>.",
                styles["Body"]))
        elif llm_m:
            story.append(Paragraph(
                "No brand mentions detected in LLM outputs (ChatGPT, Google AI, etc.). "
                "This represents an opportunity to improve AI visibility.",
                styles["Body"]))

        if serp_f.get("keywords_checked"):
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("SERP Feature Detection", styles["Sub_Title"]))
            serp_signals = [
                ("AI Overview present in SERPs",    serp_f.get("ai_overview_detected", False)),
                ("Featured Snippet present",         serp_f.get("featured_snippet_detected", False)),
                ("People Also Ask present",          serp_f.get("people_also_ask_detected", False)),
                ("Local Pack present",               serp_f.get("local_pack_detected", False)),
                ("Knowledge Panel present",          serp_f.get("knowledge_panel_detected", False)),
            ]
            serp_rows = [[r[0], r[1]] for r in (
                _signal_row(lbl, ok, styles) for lbl, ok in serp_signals
            )]
            cw = PAGE_W - 40 * mm
            t_serp = Table(serp_rows, colWidths=[cw * 0.08, cw * 0.92])
            t_serp.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, BRAND_LIGHT]),
                ("GRID",           (0, 0), (-1, -1), 0.3, colors.HexColor("#E0E0E0")),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",     (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
                ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ]))
            story.append(t_serp)

    # AEO Recommendations
    if recs:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("AEO Recommendations", styles["Sub_Title"]))
        rec_rows = [
            [r.get("priority", ""), r.get("area", ""), r.get("action", ""), r.get("workstream", "")]
            for r in recs[:8]
        ]
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Priority", "Area", "Action", "Workstream"],
            rec_rows,
            col_widths=[cw * 0.10, cw * 0.12, cw * 0.56, cw * 0.22]))

    story.append(PageBreak())


def _section_gap_analysis(story, data, styles):
    gaps = data.get("gap_analysis", [])
    if not (isinstance(gaps, list) and gaps):
        return

    story += [Paragraph("10. Per-Page Content Gaps", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "For keywords ranking at positions 4–30, the top competitor pages were analysed. "
        "Each entry below shows the content gap and recommended action for the target page.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    for gap in gaps:
        kw   = html.escape(str(gap.get("keyword", "—")))
        pos  = gap.get("position", "—")
        sv   = gap.get("search_volume", 0)
        url  = html.escape(str(gap.get("target_url", "—")))
        wc   = gap.get("avg_competitor_word_count", 0)
        h2   = gap.get("avg_competitor_h2_count", 0)
        acts = gap.get("gap_actions", [])

        story.append(Paragraph(
            f"<b>{kw}</b>  — Position {pos}  |  Vol: {sv:,}  |  Page: {url}",
            styles["Sub_Title"]))
        story.append(Paragraph(
            f"Competitors average: <b>{wc:,} words</b> / <b>{h2} H2 headings</b>",
            styles["Body"]))
        for act in acts:
            story.append(Paragraph(f"• {html.escape(act)}", styles["Body"]))
        story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())


def _section_recommendations(story, data, section_num: int, styles):
    title = f"{section_num}. Priority Recommendations"
    story += [Paragraph(title, styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Actions ranked by expected SEO impact. "
        "Workstream column indicates the most appropriate resource for each task.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    pm     = safe_get(first_result(data.get("onpage_summary", {})), "page_metrics") or {}
    if not isinstance(pm, dict):
        pm = {}
    checks = safe_get(pm, "checks", default={}) or {}
    if not isinstance(checks, dict):
        checks = {}
    aeo    = data.get("aeo_geo", {}) or {}
    local  = aeo.get("local", {})
    sc     = aeo.get("schema", {})
    ee     = aeo.get("eeat", {})

    # Page speed: prefer Lighthouse Performance, fall back to OnPage score
    lh_result    = first_result(data.get("lighthouse", {})) or {}
    lh_items     = safe_get(lh_result, "items", default=[]) or []
    lh_item      = lh_items[0] if lh_items else {}
    lh_cats      = safe_get(lh_item, "categories", default={}) or {}
    lh_perf_raw  = safe_get(lh_cats, "performance", "score", default=None)
    lh_perf      = _lh_score_int(lh_perf_raw) if lh_perf_raw is not None else None

    ps_result    = first_result(data.get("page_speed", {})) or {}
    ps_items     = safe_get(ps_result, "items", default=[]) or []
    onpage_score = safe_get(ps_items[0], "onpage_score", default=None) if ps_items else None

    recs = []

    # Technical fixes (use checks dict from onpage_summary)
    broken = checks.get("is_broken", 0) or checks.get("broken_links", 0) or pm.get("broken_links", 0) or 0
    if broken > 0:
        recs.append(("High", "Developer", "Fix broken internal links and 4xx/5xx pages",
                     "Restores crawlability and prevents PageRank leakage"))
    no_desc = checks.get("no_description", 0) or 0
    if no_desc > 0:
        recs.append(("High", "VA / Content", "Add unique meta descriptions to all pages missing them",
                     "Direct CTR impact in SERPs"))
    dup_title = checks.get("duplicate_title_tag", 0) or pm.get("duplicate_title", 0) or 0
    if dup_title > 0:
        recs.append(("High", "Developer", "Resolve duplicate title tags",
                     "Removes duplicate-content signals for Google"))
    # Use Lighthouse Performance score if available; otherwise fall back to OnPage score
    if lh_perf is not None and lh_perf < 80:
        recs.append(("High", "Developer",
                     f"Improve Lighthouse Performance score from {lh_perf} to above 80",
                     "Core Web Vitals are a confirmed Google ranking factor; low scores increase bounce rate"))
    elif lh_perf is None:
        try:
            if onpage_score is not None and float(onpage_score) < 80:
                recs.append(("High", "Developer",
                             f"Improve OnPage score from {int(float(onpage_score))} to above 80",
                             "Core Web Vitals are a confirmed Google ranking factor"))
        except (TypeError, ValueError):
            pass

    # AEO / local recs from analysis
    if not local.get("gbp_found"):
        recs.append(("High", "Consultancy / VA",
                     "Create and fully optimise a Google Business Profile",
                     "Essential for local pack visibility and in-person booking conversions"))
    if not sc.get("has_local_business"):
        recs.append(("High", "Developer",
                     "Implement LocalBusiness JSON-LD schema on the homepage",
                     "Required for AI Overviews and local knowledge panel"))
    if not sc.get("has_faq_page"):
        recs.append(("High", "VA / Content",
                     "Create a FAQ page with FAQPage JSON-LD schema",
                     "High eligibility for Google AI Overviews and People Also Ask"))
    if not ee.get("has_about_page"):
        recs.append(("High", "VA / Content",
                     "Create a detailed About/Practitioner page with credentials",
                     "Core E-E-A-T signal for YMYL (health) content"))

    # Lighthouse Accessibility check
    lh_result2  = first_result(data.get("lighthouse", {})) or {}
    lh_items2   = safe_get(lh_result2, "items", default=[]) or []
    lh_item2    = lh_items2[0] if lh_items2 else {}
    lh_cats2    = safe_get(lh_item2, "categories", default={}) or {}
    lh_a11y_raw = safe_get(lh_cats2, "accessibility", "score", default=None)
    lh_a11y     = _lh_score_int(lh_a11y_raw) if lh_a11y_raw is not None else None
    if lh_a11y is not None and lh_a11y < 90:
        recs.append(("Medium", "Developer",
                     f"Fix Lighthouse Accessibility issues (current score: {lh_a11y}/100)",
                     "Accessibility improvements also benefit SEO crawlability and inclusive UX"))

    # Universal
    recs += [
        ("Medium", "Consultancy / VA",
         "Acquire backlinks from UK therapy directories and local citations "
         "(e.g. Hypnotherapy Directory, Psychology Today UK, TherapyTribe, Yell.com)",
         "Builds domain authority and UK-relevant topical trust signals"),
        ("Medium", "VA / Content",
         "Optimise and expand content for keywords ranking at positions 4–20",
         "Quick wins: move page-2 rankings onto page 1 of UK Google results"),
        ("Medium", "Developer",
         "Implement Review / AggregateRating schema",
         "Rich snippet star ratings improve CTR from UK organic listings"),
        ("Low", "Developer",
         "Resolve any duplicate content via canonical tags or 301 redirects",
         "Consolidates authority across paginated or duplicate URLs"),
        ("Low", "Consultancy",
         "Register on Bing Places, Apple Maps, Yelp UK, and UK therapy directories",
         "Citation consistency is a local ranking factor and a trust signal for AI recommendation systems"),
    ]

    priority_colors = {"High": BRAND_RED, "Medium": BRAND_ACCENT, "Low": BRAND_GREEN}
    hdr_s   = ParagraphStyle("rh", fontName="Helvetica-Bold", fontSize=9,
                              textColor=WHITE, alignment=TA_CENTER)
    hdr_row = [Paragraph(h, hdr_s) for h in ["Priority", "Workstream", "Action", "Benefit"]]
    body_rows = []
    for p, ws, action, benefit in recs:
        pc = priority_colors.get(p, BRAND_GREY)
        body_rows.append([
            Paragraph(f"<b>{html.escape(p)}</b>",
                      ParagraphStyle("rpc", fontName="Helvetica-Bold",
                                     fontSize=9, textColor=pc)),
            Paragraph(html.escape(ws),
                      ParagraphStyle("rws", fontName="Helvetica",
                                     fontSize=8, textColor=BRAND_DARK, leading=13)),
            Paragraph(html.escape(action),
                      ParagraphStyle("ra", fontName="Helvetica",
                                     fontSize=8, textColor=BRAND_DARK, leading=13)),
            Paragraph(html.escape(benefit),
                      ParagraphStyle("rb", fontName="Helvetica",
                                     fontSize=8, textColor=BRAND_DARK, leading=13)),
        ])

    cw = PAGE_W - 40 * mm
    t  = Table([hdr_row] + body_rows,
               colWidths=[cw * 0.10, cw * 0.18, cw * 0.38, cw * 0.34])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1,-1), [WHITE, BRAND_LIGHT]),
        ("GRID",          (0, 0), (-1,-1), 0.3, colors.HexColor("#E0E0E0")),
        ("VALIGN",        (0, 0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1,-1), 5),
        ("BOTTOMPADDING", (0, 0), (-1,-1), 5),
        ("LEFTPADDING",   (0, 0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())


def _section_appendix(story, data, styles):  # noqa: C901
    """Appendix: step-by-step implementation guides for each priority recommendation."""
    story += [
        Paragraph("Appendix: Implementation Guides", styles["Section_Title"]),
        _divider(),
    ]
    story.append(Paragraph(
        "Each guide below corresponds to a priority recommendation in the previous section. "
        "Instructions are based on data collected during this audit. Code templates are "
        "ready-to-use — replace placeholder values (shown in UPPER_CASE) with the client's "
        "actual details before deployment.",
        styles["Body"]))
    story.append(Spacer(1, 6 * mm))

    # ── helpers ────────────────────────────────────────────────────────────────
    domain  = data.get("domain", "example.com")
    cw      = PAGE_W - 40 * mm
    card_n  = [0]
    priority_colors = {"High": BRAND_RED, "Medium": BRAND_ACCENT, "Low": BRAND_GREEN}

    def card_header(priority, workstream, title):
        card_n[0] += 1
        pc  = priority_colors.get(priority, BRAND_GREY)
        uid = card_n[0]
        row = [[
            Paragraph(f"<b>{html.escape(priority)}</b>",
                      ParagraphStyle(f"aph{uid}", fontName="Helvetica-Bold",
                                     fontSize=8, textColor=WHITE)),
            Paragraph(html.escape(workstream),
                      ParagraphStyle(f"apws{uid}", fontName="Helvetica",
                                     fontSize=8, textColor=colors.HexColor("#BBBBBB"))),
            Paragraph(f"<b>A{uid}.  {html.escape(title)}</b>",
                      ParagraphStyle(f"apt{uid}", fontName="Helvetica-Bold",
                                     fontSize=11, textColor=WHITE, leading=15)),
        ]]
        t = Table(row, colWidths=[cw * 0.10, cw * 0.22, cw * 0.68])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0,  0), pc),
            ("BACKGROUND",    (1, 0), (-1, 0), BRAND_DARK),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 3 * mm))

    def sub_heading(text):
        story.append(Paragraph(f"<b>{html.escape(text)}</b>",
                                ParagraphStyle("apsh", fontName="Helvetica-Bold",
                                               fontSize=9, textColor=BRAND_BLUE,
                                               spaceBefore=4, spaceAfter=2)))

    def body_text(text):
        story.append(Paragraph(html.escape(text), styles["Body"]))

    def code_block(code: str):
        lines  = code.strip().split("\n")
        joined = "<br/>".join(html.escape(ln) for ln in lines)
        t = Table(
            [[Paragraph(joined, ParagraphStyle("apcb", fontName="Courier",
                                               fontSize=7.5, textColor=BRAND_DARK,
                                               leading=11))]],
            colWidths=[cw])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F4F4F4")),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(t)
        story.append(Spacer(1, 3 * mm))

    def numbered_steps(steps: list):
        ns = ParagraphStyle("apns", fontName="Helvetica-Bold", fontSize=9,
                             textColor=BRAND_BLUE, leading=13)
        bs = ParagraphStyle("apbs", fontName="Helvetica", fontSize=9,
                             textColor=BRAND_DARK, leading=13)
        rows = [[Paragraph(f"<b>{i}</b>", ns),
                 Paragraph(html.escape(s), bs)]
                for i, s in enumerate(steps, 1)]
        t = Table(rows, colWidths=[cw * 0.05, cw * 0.95])
        t.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
        story.append(Spacer(1, 2 * mm))

    def verify(items: list):
        sub_heading("How to verify")
        vs = ParagraphStyle("apvs", fontName="Helvetica", fontSize=9,
                             textColor=BRAND_DARK, leading=14, leftIndent=8)
        for item in items:
            story.append(Paragraph(f"[ ]  {html.escape(item)}", vs))
        story.append(Spacer(1, 5 * mm))
        story.append(_divider(colors.HexColor("#E0E0E0")))
        story.append(Spacer(1, 4 * mm))

    # ── extract shared audit data ───────────────────────────────────────────────
    pm     = safe_get(first_result(data.get("onpage_summary", {})), "page_metrics") or {}
    pm     = pm if isinstance(pm, dict) else {}
    checks = safe_get(pm, "checks", default={}) or {}
    checks = checks if isinstance(checks, dict) else {}

    aeo   = data.get("aeo_geo", {}) or {}
    local = aeo.get("local", {}) or {}
    sc    = aeo.get("schema", {}) or {}
    ee    = aeo.get("eeat", {}) or {}

    lh_result   = first_result(data.get("lighthouse", {})) or {}
    lh_items    = safe_get(lh_result, "items", default=[]) or []
    lh_item     = lh_items[0] if lh_items else {}
    lh_cats     = safe_get(lh_item, "categories", default={}) or {}
    lh_audits   = safe_get(lh_item, "audits", default={}) or {}
    lh_perf_raw = safe_get(lh_cats, "performance", "score", default=None)
    lh_perf     = _lh_score_int(lh_perf_raw) if lh_perf_raw is not None else None
    lh_a11y_raw = safe_get(lh_cats, "accessibility", "score", default=None)
    lh_a11y     = _lh_score_int(lh_a11y_raw) if lh_a11y_raw is not None else None

    pages_result = first_result(data.get("onpage_pages", {})) or {}
    pages_items  = safe_get(pages_result, "items", default=[]) or []

    kw_result = first_result(data.get("keywords", {})) or {}
    kw_items  = safe_get(kw_result, "items", default=[]) or []

    tech_result = first_result(data.get("technologies", {})) or {}
    tech_items2 = safe_get(tech_result, "items", default=[]) or []
    tech_item2  = tech_items2[0] if tech_items2 else {}
    techs_list  = safe_get(tech_item2, "technologies", default=[]) or []
    cms_names   = {t.get("name", "").lower() for t in techs_list if isinstance(t, dict)}
    is_wp       = "wordpress" in cms_names

    broken   = checks.get("is_broken", 0) or pm.get("broken_links", 0) or 0
    no_desc  = checks.get("no_description", 0) or 0
    dup_title = checks.get("duplicate_title_tag", 0) or pm.get("duplicate_title", 0) or 0

    # ── A1: Fix Broken Pages ───────────────────────────────────────────────────
    if broken > 0:
        card_header("High", "Developer", "Fix Broken Pages & Broken Links")
        body_text(
            f"The audit found {broken} broken page(s) or links. Each 4xx/5xx error "
            "leaks PageRank, harms crawl budget, and damages user trust. Fix these "
            "before any other on-page work.")

        broken_pages = [p for p in pages_items
                        if safe_get(p, "checks", "is_broken")
                        or (p.get("resource_errors_count") or 0) > 0][:8]
        if broken_pages:
            sub_heading("Affected pages found in this audit")
            rows = [[p.get("url", "")[:80], str(p.get("onpage_score", "—")),
                     str(p.get("resource_errors_count", 0))]
                    for p in broken_pages]
            story.append(_data_table(["URL", "OnPage Score", "Resource Errors"],
                                     rows,
                                     col_widths=[cw * 0.72, cw * 0.15, cw * 0.13]))
            story.append(Spacer(1, 3 * mm))

        sub_heading("Steps")
        is_wp_step = ("Use a plugin such as Broken Link Checker or Screaming Frog to "
                      "confirm all 4xx URLs.") if is_wp else \
                     "Use Screaming Frog or the DataForSEO OnPage API to confirm all 4xx URLs."
        numbered_steps([
            is_wp_step,
            "For each broken URL, decide: (a) redirect to the nearest equivalent page "
            "with a 301, or (b) restore the content if it should still exist.",
            "Implement 301 redirects in your .htaccess (Apache), Nginx config, or via "
            "your hosting panel / Cloudflare Page Rules.",
            "Update any internal links pointing to the old URL to point directly to the "
            "new destination (avoids redirect chains).",
            "Submit the fixed URLs for re-indexing in Google Search Console → URL Inspection.",
        ])
        sub_heading("Example .htaccess 301 redirect")
        code_block("# Apache — add inside <IfModule mod_rewrite.c>\n"
                   "Redirect 301 /old-page-path/ https://" + domain + "/new-page-path/")
        verify([
            "Google Search Console → Coverage → Errors shows 0 new 4xx errors after re-crawl.",
            "Run Screaming Frog or DataForSEO OnPage again — no broken pages returned.",
            "Check Cloudflare Analytics / server logs for residual 404 traffic.",
        ])

    # ── A2: Add Meta Descriptions ──────────────────────────────────────────────
    if no_desc > 0:
        card_header("High", "VA / Content", "Add Unique Meta Descriptions")
        body_text(
            f"{no_desc} page(s) are missing a meta description. "
            "While not a direct ranking signal, meta descriptions are the primary "
            "copy users see in Google SERPs. A well-written description can lift "
            "click-through rate (CTR) by 5–30% on competitive UK searches.")

        missing_desc_pages = [p for p in pages_items
                               if safe_get(p, "checks", "no_description")][:10]
        if missing_desc_pages:
            sub_heading("Pages missing meta descriptions")
            rows = [[p.get("url", "")[:75],
                     str(p.get("meta", {}).get("content", {})
                            .get("plain_text_word_count", "—"))]
                    for p in missing_desc_pages]
            story.append(_data_table(["URL", "Word Count"],
                                     rows,
                                     col_widths=[cw * 0.80, cw * 0.20]))
            story.append(Spacer(1, 3 * mm))

        sub_heading("Best-practice meta description template")
        code_block('<meta name="description" content="[UNIQUE 120–155 CHAR DESCRIPTION. '
                   'Include primary keyword and a clear call-to-action for UK users.]">')

        numbered_steps([
            "Open each page listed above in your CMS (Yoast SEO → 'Edit Snippet' if WordPress).",
            "Write a unique description of 120–155 characters per page.",
            "Include the primary target keyword naturally — do not keyword-stuff.",
            "End with a UK-relevant CTA, e.g. 'Book a free consultation today' or "
            "'Based in London — call us on 020...'.",
            "Save and trigger a re-crawl via Google Search Console → URL Inspection → "
            "Request Indexing.",
        ])
        verify([
            "Run 'curl -s https://" + domain + "/page-path | grep -i description' — "
            "confirm tag is present.",
            "Google Search Console → Pages → Why pages aren't indexed → 'Missing meta description' "
            "should clear within 1–2 weeks.",
            "Monitor SERP CTR in GSC → Search Results → Clicks/Impressions for improved pages.",
        ])

    # ── A3: Resolve Duplicate Title Tags ──────────────────────────────────────
    if dup_title > 0:
        card_header("High", "Developer", "Resolve Duplicate Title Tags")
        body_text(
            f"{dup_title} page(s) share identical title tags. "
            "Duplicate titles confuse Google about which URL to rank, dilute "
            "keyword relevance, and can trigger a 'duplicate content' algorithmic "
            "penalty in competitive niches.")

        dup_result = first_result(data.get("duplicate_tags", {})) or {}
        dup_items  = safe_get(dup_result, "items", default=[]) or []
        if dup_items:
            sub_heading("Pages with duplicate title / description tags")
            rows = [[d.get("url", "")[:65],
                     d.get("accumulator", "title"),
                     (d.get("title") or d.get("description") or "")[:40]]
                    for d in dup_items[:8]]
            story.append(_data_table(["URL", "Tag Type", "Duplicate Value"],
                                     rows,
                                     col_widths=[cw * 0.52, cw * 0.13, cw * 0.35]))
            story.append(Spacer(1, 3 * mm))

        sub_heading("Steps")
        numbered_steps([
            "Identify which URL is the canonical version (typically the one with more "
            "backlinks or higher organic traffic).",
            "Edit the non-canonical page's title to be unique and specifically describe "
            "that page's content.",
            "Title tag formula: [Primary Keyword] — [Differentiator] | [Brand Name] "
            "(keep under 60 characters).",
            "If the pages are near-identical in content, consider consolidating them into "
            "one page and 301-redirecting the duplicate.",
            "Add a <link rel=\"canonical\"> tag on the non-canonical page pointing to "
            "the preferred URL as an additional signal.",
        ])
        sub_heading("Good title tag example")
        code_block("<title>Hypnotherapy for Anxiety in London | PRACTICE_NAME</title>")
        verify([
            "Screaming Frog → Page Titles filter → check 'Duplicate' — should return 0.",
            "Google Search Console → Pages → Duplicate without canonical should reduce.",
        ])

    # ── A4: Improve Page Speed ─────────────────────────────────────────────────
    if lh_perf is not None and lh_perf < 80:
        card_header("High", "Developer", f"Improve Page Speed (Lighthouse: {lh_perf}/100)")
        body_text(
            "Core Web Vitals (LCP, CLS, INP) are a confirmed Google ranking factor. "
            "A Lighthouse Performance score below 80 typically indicates issues that "
            "affect real user experience and search rankings, especially on mobile.")

        # Show relevant Lighthouse audits that are failing
        failing_audits = {k: v for k, v in lh_audits.items()
                          if isinstance(v, dict)
                          and v.get("score") is not None
                          and float(v.get("score", 1)) < 0.9
                          and v.get("displayValue")}
        if failing_audits:
            sub_heading("Failing Lighthouse audits (score < 90%)")
            rows = [[k.replace("-", " ").title(), v.get("displayValue", "")]
                    for k, v in list(failing_audits.items())[:8]]
            story.append(_data_table(["Audit", "Current Value"],
                                     rows,
                                     col_widths=[cw * 0.55, cw * 0.45]))
            story.append(Spacer(1, 3 * mm))

        sub_heading("Priority fixes")
        wp_steps = [
            "Install WP Rocket or LiteSpeed Cache — enable page caching, GZIP "
            "compression, and CSS/JS minification.",
            "Install Smush or ShortPixel — bulk-compress all uploaded images and "
            "enable WebP conversion.",
            "Enable lazy loading for images: add loading=\"lazy\" to all <img> tags "
            "(Yoast SEO does this automatically for body images).",
            "Remove or defer render-blocking scripts: in WP Rocket → File Optimisation "
            "→ enable 'Defer JS execution'.",
            "Use Cloudflare (already detected) — enable 'Auto Minify' (HTML/CSS/JS) "
            "and set browser cache TTL to 1 year for static assets.",
            "Serve images in next-gen formats: Cloudflare Polish → Lossy for automatic "
            "WebP delivery.",
        ]
        generic_steps = [
            "Compress and resize images to the displayed dimensions. Use WebP format.",
            "Enable server-side GZIP/Brotli compression for HTML, CSS, JS.",
            "Minify CSS and JavaScript files; combine where possible to reduce requests.",
            "Add a Cache-Control header with max-age=31536000 for all static assets.",
            "Remove render-blocking resources: defer non-critical JS with async/defer attributes.",
            "Implement lazy loading for below-fold images using loading=\"lazy\".",
        ]
        numbered_steps(wp_steps if is_wp else generic_steps)

        sub_heading("Core Web Vitals targets (Google's Good thresholds)")
        story.append(_data_table(
            ["Metric", "Good", "Needs Improvement", "Poor"],
            [
                ["LCP (Largest Contentful Paint)", "≤ 2.5 s", "2.5–4.0 s", "> 4.0 s"],
                ["INP (Interaction to Next Paint)", "≤ 200 ms", "200–500 ms", "> 500 ms"],
                ["CLS (Cumulative Layout Shift)",  "≤ 0.1",   "0.1–0.25",  "> 0.25"],
            ],
            col_widths=[cw * 0.40, cw * 0.20, cw * 0.20, cw * 0.20]))
        story.append(Spacer(1, 3 * mm))
        verify([
            "Re-run Google PageSpeed Insights (pagespeed.web.dev) — target 80+ on mobile.",
            "Google Search Console → Core Web Vitals — 'Good URLs' count should increase "
            "within 28-day data window.",
            "Chrome DevTools → Lighthouse tab → Performance — verify score improvement.",
        ])

    # ── A5: Google Business Profile ────────────────────────────────────────────
    if not local.get("gbp_found"):
        card_header("High", "Consultancy / VA", "Create & Optimise Google Business Profile")
        body_text(
            "A Google Business Profile (GBP) is the single most important local SEO "
            "asset for UK service businesses. Without it, the site cannot appear in "
            "the Google Local Pack (the map results shown above organic listings), "
            "which captures 30–40% of local search clicks.")

        sub_heading("Setup steps")
        numbered_steps([
            "Go to business.google.com and sign in with the client's Google account.",
            "Click 'Add your business' and enter the exact business name (must match "
            "website and all other directories exactly).",
            "Select the correct primary category (e.g. 'Hypnotherapist' or 'Therapist'). "
            "Add 2–3 secondary categories relevant to specific services offered.",
            "Enter the full UK address including postcode. For home-based practices, "
            "tick 'I deliver goods and services to my customers' and hide the address.",
            "Add the primary phone number (UK format: 020 XXXX XXXX or 07XXX XXXXXX).",
            "Add the website URL: https://" + domain,
            "Set opening hours accurately. Add special hours for bank holidays.",
            "Request verification by postcard (2–5 business days) or video call.",
        ])

        sub_heading("Optimisation checklist (post-verification)")
        checklist_style = ParagraphStyle("apcl", fontName="Helvetica", fontSize=9,
                                          textColor=BRAND_DARK, leading=14, leftIndent=8)
        optimisation_items = [
            "Write a 750-character keyword-rich business description — include primary "
            "service + location (e.g. 'London hypnotherapy for anxiety, phobias, and IBS').",
            "Upload at least 10 high-quality photos: exterior, interior, team, and "
            "before/after results (with consent).",
            "Add all services from the website with individual descriptions and prices.",
            "Enable messaging and set up a welcome message.",
            "Create a Google Post at least once per week (events, offers, news).",
            "Respond to ALL reviews — positive and negative — within 48 hours.",
        ]
        for item in optimisation_items:
            story.append(Paragraph(f"[ ]  {html.escape(item)}", checklist_style))
        story.append(Spacer(1, 3 * mm))
        verify([
            "Search '[business name] London' on Google — GBP panel appears on right.",
            "Search 'hypnotherapy near me' or '[service] [city]' — appear in Local Pack "
            "within 4–8 weeks of verification.",
            "GBP Insights → Views on Search and Maps should begin showing data.",
        ])

    # ── A6: LocalBusiness JSON-LD Schema ───────────────────────────────────────
    if not sc.get("has_local_business"):
        card_header("High", "Developer", "Implement LocalBusiness JSON-LD Schema")
        body_text(
            "LocalBusiness schema tells Google and AI systems (ChatGPT, Gemini, "
            "Perplexity) structured facts about the business. It's required for the "
            "knowledge panel, AI Overviews, and voice search answers. "
            "It takes under 30 minutes to implement.")

        gbp_name    = local.get("gbp_name",    "BUSINESS_NAME")
        gbp_address = local.get("gbp_address", "STREET_ADDRESS, CITY, POSTCODE")
        gbp_phone   = local.get("gbp_phone",   "+44 20 XXXX XXXX")

        sub_heading("JSON-LD schema — add inside <head> on the homepage")
        code_block(
            '<script type="application/ld+json">\n'
            '{\n'
            '  "@context": "https://schema.org",\n'
            '  "@type": "LocalBusiness",\n'
            f'  "name": "{gbp_name}",\n'
            f'  "url": "https://{domain}",\n'
            f'  "telephone": "{gbp_phone}",\n'
            '  "address": {\n'
            '    "@type": "PostalAddress",\n'
            f'    "streetAddress": "STREET_ADDRESS",\n'
            f'    "addressLocality": "CITY",\n'
            f'    "postalCode": "POSTCODE",\n'
            '    "addressCountry": "GB"\n'
            '  },\n'
            '  "openingHoursSpecification": [\n'
            '    {\n'
            '      "@type": "OpeningHoursSpecification",\n'
            '      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"],\n'
            '      "opens": "09:00",\n'
            '      "closes": "18:00"\n'
            '    }\n'
            '  ],\n'
            '  "geo": {\n'
            '    "@type": "GeoCoordinates",\n'
            '    "latitude": "LATITUDE",\n'
            '    "longitude": "LONGITUDE"\n'
            '  },\n'
            '  "sameAs": [\n'
            '    "GOOGLE_BUSINESS_PROFILE_URL",\n'
            '    "LINKEDIN_OR_THERAPY_DIRECTORY_URL"\n'
            '  ]\n'
            '}\n'
            '</script>'
        )

        wp_note = (" For WordPress: paste this snippet using the 'Insert Headers and Footers' "
                   "plugin, or add it to the theme's header.php inside the <head> block. "
                   "Yoast SEO Premium can also generate this automatically.") if is_wp else ""

        numbered_steps([
            "Copy the template above and fill in all UPPER_CASE placeholders.",
            "Find the latitude/longitude of the business address on Google Maps "
            "(right-click the pin → copy coordinates)." + wp_note,
            "Paste the completed script into the <head> section of the homepage.",
            "Validate with Google's Rich Results Test: "
            "search.google.com/test/rich-results",
            "Submit the homepage URL in Google Search Console → URL Inspection → "
            "Request Indexing.",
        ])
        verify([
            "Google Rich Results Test → paste homepage URL → 'Local Business' card appears.",
            "Search '[business name] site:" + domain + "' in Google — knowledge panel "
            "may appear within 2–4 weeks.",
        ])

    # ── A7: FAQPage Schema ─────────────────────────────────────────────────────
    if not sc.get("has_faq_page"):
        card_header("High", "VA / Content", "Create FAQ Page with FAQPage Schema")
        body_text(
            "FAQPage schema is one of the fastest routes to Google AI Overview inclusion. "
            "Google surfaces FAQ answers directly in search results (PAA — People Also Ask) "
            "and in AI-generated summaries. A well-structured FAQ page can "
            "also rank for long-tail queries with high buyer intent.")

        sub_heading("Recommended FAQ structure")
        body_text(
            "Create a page at https://" + domain + "/faq with 8–12 questions. "
            "Group them into: (1) About the service, (2) What to expect, "
            "(3) Conditions treated, (4) Pricing & booking. "
            "Aim for 80–150 words per answer — long enough to be informative, "
            "short enough to be featured in AI Overviews.")

        sub_heading("FAQPage JSON-LD template (add to /faq page <head>)")
        code_block(
            '<script type="application/ld+json">\n'
            '{\n'
            '  "@context": "https://schema.org",\n'
            '  "@type": "FAQPage",\n'
            '  "mainEntity": [\n'
            '    {\n'
            '      "@type": "Question",\n'
            '      "name": "What is hypnotherapy and how does it work?",\n'
            '      "acceptedAnswer": {\n'
            '        "@type": "Answer",\n'
            '        "text": "Hypnotherapy is a therapeutic technique that uses guided\n'
            '         relaxation and focused attention to help you access a heightened\n'
            '         state of awareness. During this state, the mind is more open to\n'
            '         positive suggestion, making it easier to address habits, phobias,\n'
            '         and emotional challenges. Sessions with PRACTITIONER_NAME'
            ' typically last 60 minutes."\n'
            '      }\n'
            '    },\n'
            '    {\n'
            '      "@type": "Question",\n'
            '      "name": "How many sessions will I need?",\n'
            '      "acceptedAnswer": {\n'
            '        "@type": "Answer",\n'
            '        "text": "Most clients see significant results in 3–6 sessions,\n'
            '         depending on the issue. We offer a free initial consultation\n'
            '         to discuss your goals and recommend a personalised plan."\n'
            '      }\n'
            '    },\n'
            '    {\n'
            '      "@type": "Question",\n'
            '      "name": "Is hypnotherapy available online?",\n'
            '      "acceptedAnswer": {\n'
            '        "@type": "Answer",\n'
            '        "text": "Yes — we offer secure online hypnotherapy sessions via\n'
            '         Zoom for clients across the UK. In-person sessions are available\n'
            '         at our CITY practice."\n'
            '      }\n'
            '    }\n'
            '  ]\n'
            '}\n'
            '</script>'
        )
        numbered_steps([
            "Create a new page '/faq' in your CMS with a clear H1: 'Frequently Asked "
            "Questions About Hypnotherapy'.",
            "Write 8–12 Q&A pairs using real questions from clients and the 'People Also "
            "Ask' boxes in Google for your top keywords.",
            "Add the FAQPage JSON-LD schema above — update answers to match your page "
            "content exactly.",
            "Link to the FAQ page from the homepage navigation and relevant service pages.",
            "Submit the new URL to Google Search Console → URL Inspection.",
        ])
        verify([
            "Google Rich Results Test → FAQPage schema validated.",
            "Search your primary keyword on Google — People Also Ask box may begin showing "
            "your questions within 4–8 weeks.",
            "Monitor Google Search Console → Search Appearance → Rich Results.",
        ])

    # ── A8: About / Practitioner Page ──────────────────────────────────────────
    if not ee.get("has_about_page"):
        card_header("High", "VA / Content", "Build an E-E-A-T Practitioner/About Page")
        body_text(
            "Google's Quality Rater Guidelines classify health and therapy sites as "
            "Your Money or Your Life (YMYL). For YMYL pages, Google heavily weights "
            "E-E-A-T: Experience, Expertise, Authoritativeness, and Trustworthiness. "
            "A detailed About page is the primary signal for all four dimensions.")

        sub_heading("Required content elements")
        checklist_style = ParagraphStyle("apcl2", fontName="Helvetica", fontSize=9,
                                          textColor=BRAND_DARK, leading=14, leftIndent=8)
        for item in [
            "Professional headshot photograph (not stock imagery).",
            "Full name, professional title, and years of experience.",
            "Qualifications: list each certification, awarding body, and year obtained "
            "(e.g. 'Diploma in Clinical Hypnotherapy, NCHP, 2018').",
            "Professional membership bodies: NCH, NCHP, CNHC, GHR, BSCH — with logos "
            "and links to member directory listings.",
            "Supervised client hours / practice history.",
            "Areas of specialism: anxiety, phobias, IBS, smoking cessation, weight "
            "management, etc.",
            "Personal statement: why you became a therapist (authentic voice — "
            "Google rewards genuine human experience).",
            "Published articles, podcast appearances, or media mentions (builds authority).",
            "Testimonials with first name, location, and date (with client consent).",
            "Contact information and booking CTA prominently visible.",
        ]:
            story.append(Paragraph(f"[ ]  {html.escape(item)}", checklist_style))
        story.append(Spacer(1, 3 * mm))

        sub_heading("Person schema (add to About page <head>)")
        code_block(
            '<script type="application/ld+json">\n'
            '{\n'
            '  "@context": "https://schema.org",\n'
            '  "@type": "Person",\n'
            '  "name": "PRACTITIONER_FULL_NAME",\n'
            '  "jobTitle": "Clinical Hypnotherapist",\n'
            f'  "worksFor": {{"@type": "LocalBusiness", "name": "PRACTICE_NAME"}},\n'
            '  "url": "https://' + domain + '/about",\n'
            '  "sameAs": [\n'
            '    "LINKEDIN_URL",\n'
            '    "NCH_MEMBER_DIRECTORY_URL"\n'
            '  ]\n'
            '}\n'
            '</script>'
        )
        verify([
            "Google Manual Actions (Search Console) — no thin content warnings after indexing.",
            "Search '[practitioner name]' on Google — Knowledge Panel or rich result appears.",
            "Check E-E-A-T signals with a quality rater tool or manual review against "
            "Google's Search Quality Evaluator Guidelines.",
        ])

    # ── A9: Lighthouse Accessibility ───────────────────────────────────────────
    if lh_a11y is not None and lh_a11y < 90:
        card_header("Medium", "Developer",
                    f"Fix Accessibility Issues (Lighthouse: {lh_a11y}/100)")
        body_text(
            "Accessibility improvements benefit both users and SEO. Accessible pages "
            "are more crawlable, load faster on assistive technologies, and signal "
            "quality to Google's algorithms. UK businesses also have obligations "
            "under the Equality Act 2010.")

        a11y_audits = {k: v for k, v in lh_audits.items()
                       if isinstance(v, dict)
                       and k not in ("performance-score",)
                       and str(k).startswith(("color", "image-alt", "label", "aria",
                                              "button", "link", "document", "frame",
                                              "heading", "html-lang", "landmark"))
                       and v.get("score") is not None
                       and float(v.get("score", 1)) < 0.9}
        if a11y_audits:
            sub_heading("Failing accessibility audits")
            rows = [[k.replace("-", " ").title(), v.get("displayValue", "Review required")]
                    for k, v in list(a11y_audits.items())[:8]]
            story.append(_data_table(["Audit", "Finding"],
                                     rows,
                                     col_widths=[cw * 0.50, cw * 0.50]))
            story.append(Spacer(1, 3 * mm))

        numbered_steps([
            "Add descriptive alt text to all images: <img src=\"...\" alt=\"Brief "
            "description of the image for screen readers\">.",
            "Ensure all form inputs have associated <label> elements (not just placeholder text).",
            "Check colour contrast: text must meet WCAG 2.1 AA ratio of 4.5:1 for normal "
            "text, 3:1 for large text. Use WebAIM Contrast Checker.",
            "Add lang=\"en\" attribute to the <html> element to identify page language.",
            "Ensure all interactive elements (buttons, links) have descriptive aria-label "
            "or visible text — avoid 'click here' or icon-only buttons.",
            "Use semantic HTML headings in order (H1 → H2 → H3) — do not skip levels.",
        ])
        verify([
            "Re-run Lighthouse in Chrome DevTools → Accessibility score ≥ 90.",
            "Test with NVDA (free) or VoiceOver (Mac/iOS) screen reader — all content "
            "should be navigable.",
            "axe DevTools browser extension — zero critical violations.",
        ])

    # ── A10: UK Citation Building ──────────────────────────────────────────────
    card_header("Medium", "Consultancy / VA", "Build UK Therapy Directory Citations")
    body_text(
        "Citations (consistent NAP: Name, Address, Phone listings) are a key local "
        "ranking factor. They also feed AI recommendation systems — when ChatGPT or "
        "Gemini recommends a local therapist, directory listings are a primary data "
        "source. Aim to be listed on all tier-1 UK therapy directories.")

    sub_heading("Priority UK directories for therapy practices")
    story.append(_data_table(
        ["Directory", "Type", "Action"],
        [
            ["Hypnotherapy Directory (hypnotherapy-directory.org.uk)", "Tier 1 — Therapy", "Create full profile"],
            ["Psychology Today UK (psychologytoday.com/gb)", "Tier 1 — Mental Health", "Create therapist profile"],
            ["Counselling Directory (counselling-directory.org.uk)", "Tier 1 — Therapy", "Create full profile"],
            ["TherapyTribe (therapytribe.com)", "Tier 2 — Therapy", "Claim/create listing"],
            ["Yell.com", "Tier 1 — General UK", "Claim/create listing"],
            ["Thomson Local (thomsonlocal.com)", "Tier 2 — General UK", "Claim listing"],
            ["Yelp UK (yelp.co.uk)", "Tier 2 — General", "Claim listing"],
            ["Bing Places (bingplaces.com)", "Search Engine", "Sync from Google Business Profile"],
            ["Apple Maps (mapsconnect.apple.com)", "Search Engine", "Claim listing"],
            ["CNHC Register (cnhc.org.uk)", "Professional Body", "Verify membership listing"],
        ],
        col_widths=[cw * 0.48, cw * 0.26, cw * 0.26]))
    story.append(Spacer(1, 3 * mm))

    sub_heading("NAP consistency rule")
    body_text(
        "Every listing MUST use identical Name, Address, and Phone format. "
        "Even minor variations (e.g. 'St.' vs 'Street', '020' vs '+44 20') "
        "reduce citation value. Decide on a canonical NAP format now and use it everywhere.")
    story.append(Spacer(1, 3 * mm))
    verify([
        "Moz Local or BrightLocal — run a citation audit, resolve all inconsistencies.",
        "Search '[business name] [city]' on Google — map pack appears within 6–12 weeks "
        "of consistent citation building.",
    ])

    # ── A11: Content Optimisation (Positions 4–20) ─────────────────────────────
    card_header("Medium", "VA / Content", "Content Optimisation — Move Position 4–20 to Page 1")
    body_text(
        "Keywords ranking at positions 4–20 are 'low-hanging fruit' — the site has "
        "already demonstrated topical relevance but needs stronger content signals "
        "to break into the top 3. Improving one position from #11 to #10 can "
        "double the click-through rate for that keyword.")

    mid_kws = [k for k in kw_items
               if 4 <= (safe_get(k, "keyword_data", "keyword_info", "search_volume") or
                        safe_get(k, "ranked_serp_element", "serp_item", "rank_absolute") or 0)
               <= 20]
    # Simpler: filter by rank_absolute position
    mid_kws = [k for k in kw_items
               if 4 <= int(safe_get(k, "ranked_serp_element", "serp_item",
                                    "rank_absolute", default=99) or 99) <= 20][:10]

    if mid_kws:
        sub_heading("Keywords at positions 4–20 (top opportunities)")
        rows = []
        for k in mid_kws:
            kw   = safe_get(k, "keyword_data", "keyword", default="") or ""
            pos  = safe_get(k, "ranked_serp_element", "serp_item", "rank_absolute", default="") or ""
            vol  = safe_get(k, "keyword_data", "keyword_info", "search_volume", default=0) or 0
            url  = safe_get(k, "ranked_serp_element", "serp_item", "url", default="") or ""
            rows.append([kw, str(pos), f"{vol:,}", url[:45]])
        story.append(_data_table(
            ["Keyword", "Pos", "Volume (UK)", "Ranking URL"],
            rows,
            col_widths=[cw * 0.32, cw * 0.07, cw * 0.14, cw * 0.47]))
        story.append(Spacer(1, 3 * mm))
    else:
        body_text("Re-run the audit in live mode to populate keyword position data.")

    numbered_steps([
        "For each keyword in the table above, open the ranking URL in your CMS.",
        "Check the current word count — compare against the top 3 competing pages "
        "(use a tool like SurferSEO or simply view source and estimate).",
        "Add a dedicated H2 or H3 section that directly addresses the keyword "
        "topic — do not keyword-stuff; write for users.",
        "Add 1–2 internal links from relevant pages to the target page using the "
        "keyword (or a close variant) as the anchor text.",
        "Add or update the page's meta title and description to include the keyword "
        "naturally.",
        "Embed a relevant video (YouTube) or add a FAQ block targeting the keyword's "
        "long-tail variants — both can increase time-on-page.",
        "Request re-indexing via Google Search Console after edits.",
    ])
    verify([
        "Monitor keyword positions weekly using DataForSEO Labs or Google Search Console.",
        "Target: move each keyword up by at least 3 positions within 60 days.",
    ])

    # ── A12: Review / AggregateRating Schema ──────────────────────────────────
    card_header("Medium", "Developer", "Add Review & AggregateRating Schema")
    body_text(
        "AggregateRating schema enables Google to display star ratings directly in "
        "organic search results (rich snippets). This can increase CTR by 10–30% "
        "without any ranking change. Particularly effective for therapy and wellness "
        "businesses where social proof drives conversions.")

    sub_heading("JSON-LD template (add to homepage or service pages)")
    code_block(
        '<script type="application/ld+json">\n'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "LocalBusiness",\n'
        f'  "name": "BUSINESS_NAME",\n'
        f'  "url": "https://{domain}",\n'
        '  "aggregateRating": {\n'
        '    "@type": "AggregateRating",\n'
        '    "ratingValue": "4.9",\n'
        '    "reviewCount": "47",\n'
        '    "bestRating": "5",\n'
        '    "worstRating": "1"\n'
        '  },\n'
        '  "review": [\n'
        '    {\n'
        '      "@type": "Review",\n'
        '      "author": {"@type": "Person", "name": "CLIENT_FIRST_NAME"},\n'
        '      "reviewRating": {"@type": "Rating", "ratingValue": "5"},\n'
        '      "reviewBody": "GENUINE_REVIEW_TEXT_HERE",\n'
        '      "datePublished": "2025-10-01"\n'
        '    }\n'
        '  ]\n'
        '}\n'
        '</script>'
    )

    numbered_steps([
        "Collect client reviews with explicit written permission to publish on the website.",
        "Update ratingValue and reviewCount to reflect actual numbers — "
        "Google may demote inaccurate or inflated ratings.",
        "Include at least 3 individual Review objects with real client names and dates.",
        "Embed the JSON-LD on each service page and the homepage.",
        "Validate with Google's Rich Results Test.",
    ])
    body_text(
        "Note: Do NOT use reviews sourced exclusively from Google or Trustpilot "
        "in this schema — use only reviews you hold first-party rights to. "
        "Link to your Google/Trustpilot page separately.")
    story.append(Spacer(1, 3 * mm))
    verify([
        "Google Rich Results Test → AggregateRating result validated.",
        "Search '[business name] reviews' — star rating rich snippet appears in SERPs.",
        "Monitor CTR uplift in GSC → Search Results for pages with schema added.",
    ])

    # ── Rank Math: WordPress SEO plugin guide ──────────────────────────────────
    card_header("Medium", "Developer", "Rank Math SEO Plugin — WordPress Optimisation")
    body_text(
        "Rank Math is the recommended SEO plugin for WordPress sites. "
        "It centralises on-page optimisation, sitemap management, schema markup, "
        "redirections, and 404 monitoring in a single interface. "
        "The target for every page is an 80+ Rank Math SEO score (green indicator). "
        "Follow the workflow below after installing: Rank Math → Dashboard → Setup Wizard."
    )

    sub_heading("1. Initial Setup Wizard")
    numbered_steps([
        "Install Rank Math from WordPress Admin → Plugins → Add New → search 'Rank Math SEO'.",
        "Run the Setup Wizard (Rank Math → Dashboard → Setup Wizard). "
        "Connect Google Search Console when prompted — this imports real impression/click "
        "data directly into the WordPress dashboard.",
        "Set the Site Type (Local Business, Personal, etc.) and fill in the business "
        "details (name, logo, contact info). This auto-generates basic JSON-LD schema.",
        "Enable all modules you need: Sitemap, Schema, Redirections, 404 Monitor, "
        "Image SEO, and Local SEO.",
        "Set the 'Separator character' for titles and confirm the default title/description "
        "format patterns for posts, pages, and taxonomies.",
    ])

    sub_heading("2. On-Page SEO — Targeting 80+ Score")
    body_text(
        "Open any page/post in the WordPress editor. The Rank Math panel appears on the "
        "right. Set a Focus Keyword and work through the checklist until the score turns green."
    )
    numbered_steps([
        "Focus Keyword: enter the primary keyword for the page. Rank Math checks it against "
        "the title, URL slug, meta description, first paragraph, and H2/H3 headings.",
        "SEO Title: include the focus keyword near the start. Keep to 50–60 characters. "
        "Example: 'Counselling West Oxfordshire | BUSINESS_NAME'.",
        "Meta Description: write a unique 120–155 character description that includes the "
        "keyword and a clear call to action (e.g. 'Book a free 20-min consultation today').",
        "URL Slug: use a short, keyword-rich slug with hyphens, no stop words. "
        "Example: /counselling-west-oxfordshire/ not /services-page-1/.",
        "Content: include the focus keyword in the first paragraph and at least one H2 "
        "subheading. Aim for 1–1.5% keyword density — Rank Math flags over-stuffing.",
        "Content Length: for service and location pages, target 1,200+ words. Rank Math's "
        "Content AI (Pro) suggests optimal length based on SERP competitors.",
        "Internal Links: add at least 2 internal links per page using relevant anchor text. "
        "Rank Math counts these and reports shortfall in the score panel.",
        "External Links: include 1–2 links to reputable authority sources "
        "(NHS, BACP, UKCP etc.) where relevant — signals E-E-A-T for YMYL content.",
    ])

    sub_heading("3. XML Sitemaps")
    numbered_steps([
        "Rank Math → Sitemap Settings. Ensure sitemaps are ON for: Posts, Pages, "
        "and any custom post types. Disable sitemaps for tags, authors, and archives "
        "unless they have unique content.",
        "Set 'Links Per Sitemap' to 100 (better for shared hosting / large sites).",
        "Enable 'Include Images in Sitemap' — this helps Google Image Search indexing "
        "and is a ranking signal for image-heavy pages.",
        "Submit the sitemap URL (usually /sitemap_index.xml) to Google Search Console → "
        "Sitemaps. Also submit to Bing Webmaster Tools.",
        "Ping sitemaps automatically: Rank Math does this on publish — confirm 'Ping "
        "Search Engines' is ON in Sitemap Settings.",
    ])

    sub_heading("4. Schema Markup")
    numbered_steps([
        "Rank Math → Titles & Meta → Global Meta: set the global schema type for the "
        "site (LocalBusiness recommended for service businesses).",
        "Per-page: in the Rank Math editor panel → Schema tab → Add Schema. "
        "Select the appropriate type: LocalBusiness, Service, FAQPage, "
        "Person, Article, etc.",
        "For the homepage: add LocalBusiness schema with address, phone, opening hours, "
        "and geo-coordinates. Fill in all fields — incomplete schema scores lower in "
        "Google's Rich Results Test.",
        "For service pages: add a Service schema with name, description, and areaServed.",
        "For any page with FAQs: add FAQPage schema — each Q&A pair is auto-formatted. "
        "This makes pages eligible for Google's People Also Ask and AI Overviews.",
        "Validate every schema addition at: https://search.google.com/test/rich-results",
    ])

    sub_heading("5. Breadcrumbs")
    numbered_steps([
        "Rank Math → General Settings → Breadcrumbs → Enable Breadcrumbs.",
        "Add the breadcrumb shortcode or Gutenberg block to your theme's page template "
        "or use the 'Rank Math Breadcrumbs' widget if using a page builder.",
        "Breadcrumbs add BreadcrumbList schema automatically, improving site structure "
        "signals for both users and Google.",
    ])

    sub_heading("6. Redirections & 404 Monitor")
    numbered_steps([
        "Rank Math → Redirections → Enable the Redirections module.",
        "Rank Math → 404 Monitor → Enable to log all 404 errors. Check weekly.",
        "For each logged 404, create a 301 redirect in Rank Math → Redirections → "
        "Add New. Set Source URL (the broken path) and Destination URL (the live page). "
        "This is faster than editing .htaccess directly and survives theme updates.",
        "Enable 'Auto-redirect attachments to their parent post' in Rank Math → "
        "General Settings to prevent WordPress attachment page 404s.",
        "Bulk-redirect old blog slugs or renamed pages: export the 404 log, filter "
        "by traffic, and bulk-import redirects via Rank Math → Redirections → Import.",
    ])

    sub_heading("7. Image SEO")
    numbered_steps([
        "Rank Math → General Settings → Image SEO → Auto-set ALT Tag: set the "
        "template to '%title%' or '%filename%' so all uploaded images get an ALT "
        "attribute automatically (fixes the 'no_image_alt' audit issue).",
        "For key images (hero, headshots, before/after), manually write descriptive "
        "ALT text that includes the focus keyword: e.g. 'Christabel Whiting MBACP "
        "counsellor in West Oxfordshire'.",
        "Compress images before upload: use WebP format or a plugin such as "
        "Smush / ShortPixel. Target < 200 KB per image.",
        "Ensure images are included in the sitemap (Rank Math → Sitemap Settings → "
        "Include Images).",
    ])

    sub_heading("8. Canonical Tags & Duplicate Content")
    numbered_steps([
        "Rank Math automatically sets self-referencing canonical tags on all pages — "
        "verify they are present by viewing page source: "
        "<link rel='canonical' href='https://DOMAIN/PAGE/' />.",
        "For paginated archives (?page=2 etc.), Rank Math adds rel='next'/'prev' "
        "automatically. Confirm under Rank Math → Titles & Meta → Posts → "
        "Pagination → 'Use rel=next/prev'.",
        "If two pages have highly similar content, set the canonical on the weaker "
        "page to point to the stronger one: Rank Math editor → Advanced tab → "
        "Canonical URL field.",
        "Use the 'No Index' toggle (Rank Math editor → Advanced → Robots Meta) for "
        "pages that should not appear in search: thank-you pages, internal search "
        "results, test pages.",
    ])

    sub_heading("9. Monitoring & SEO Analysis")
    numbered_steps([
        "Rank Math → SEO Analysis → Run a full site analysis. Rank Math checks "
        "50+ SEO factors including title tags, meta descriptions, schema, sitemaps, "
        "and Search Console connectivity.",
        "Rank Math → Analytics: review the Search Console integration weekly. "
        "Monitor position changes, click-through rate (CTR), and which queries "
        "generate impressions but few clicks (optimise meta descriptions for those).",
        "Rank Math → Schema → Schema Generator: periodically re-run to ensure new "
        "pages have schema assigned and existing schema hasn't drifted.",
        "If using Rank Math Pro: enable Content AI for AI-assisted keyword suggestions, "
        "readability scoring, and competitor content gap analysis per page.",
    ])

    verify([
        "WordPress Admin → Rank Math → SEO Analysis → Score is green (80+).",
        "Google Search Console → Sitemaps → Sitemap submitted and 0 errors.",
        "Google Rich Results Test → homepage and service pages pass schema validation.",
        "Rank Math → 404 Monitor → 0 new 404s after redirect cleanup.",
        "GSC → Coverage → Valid pages increasing week-on-week.",
        "All priority pages have Rank Math score ≥ 80 (check in page list view).",
    ])

    story.append(PageBreak())


def _section_cost(story, data, section_num: int, styles):
    story += [Paragraph(f"{section_num}. Cost Appendix", styles["Section_Title"]), _divider()]
    story.append(Paragraph(
        "Estimated costs for this audit. DataForSEO costs are estimates based on "
        "typical mid-tier API pricing; actual costs depend on your plan and data volume. "
        "LLM costs are based on Claude Haiku 4.5 pricing.",
        styles["Body"]))
    story.append(Spacer(1, 4 * mm))

    cost = data.get("cost", {}) or {}
    by_ep = cost.get("api_calls_by_endpoint", {})

    story.append(_metric_cards([
        {"label": "API Calls",         "value": str(cost.get("api_calls_total", 0)),              "color": BRAND_BLUE},
        {"label": "API Cost (est.)",   "value": f"${cost.get('api_cost_usd', 0):.4f}",           "color": BRAND_BLUE},
        {"label": "LLM Cost (est.)",   "value": f"${cost.get('llm_cost_usd', 0):.4f}",           "color": BRAND_BLUE},
        {"label": "Total Cost (est.)", "value": f"${cost.get('total_cost_usd', 0):.4f}",          "color": BRAND_ACCENT},
    ]))
    story.append(Spacer(1, 5 * mm))

    if by_ep:
        story.append(Paragraph("API Calls by Endpoint", styles["Sub_Title"]))
        rows = [
            [ep, str(v["calls"]), f"${v['cost_usd']:.4f}"]
            for ep, v in sorted(by_ep.items(), key=lambda x: -x[1]["cost_usd"])
        ]
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Endpoint", "Calls", "Est. Cost (USD)"],
            rows,
            col_widths=[cw * 0.65, cw * 0.15, cw * 0.20]))

    llm_in  = cost.get("llm_input_tokens",  0)
    llm_out = cost.get("llm_output_tokens", 0)
    llm_m   = cost.get("llm_model", "claude-sonnet-4-6")
    if llm_in or llm_out:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("LLM Usage", styles["Sub_Title"]))
        cw = PAGE_W - 40 * mm
        story.append(_data_table(
            ["Item", "Value"],
            [
                ["Model",         llm_m],
                ["Input tokens",  f"{llm_in:,}"],
                ["Output tokens", f"{llm_out:,}"],
                ["Est. LLM cost", f"${cost.get('llm_cost_usd', 0):.4f}"],
            ],
            col_widths=[cw * 0.40, cw * 0.60]))


# ── Public entry point ─────────────────────────────────────────────────────────

def build_pdf(data: dict, output_path: str, agency: str = "Theo Ruby SEO Agency") -> str:
    """
    Build a branded three-tier PDF SEO report.

    Args:
        data:        Collected audit data dict (from DataForSEOAuditService).
        output_path: Where to write the PDF file.
        agency:      Agency name shown on cover and header.

    Returns:
        The output_path written.
    """
    styles  = _build_styles()
    domain  = data.get("domain", "unknown")
    has_deep = bool(data.get("gap_analysis"))

    doc = BaseDocTemplate(
        output_path,
        pagesize    = A4,
        leftMargin  = 20 * mm, rightMargin = 20 * mm,
        topMargin   = 35 * mm, bottomMargin = 20 * mm,
        title       = f"SEO Audit — {domain}",
        author      = agency,
    )

    cover_frame    = Frame(0, 0, PAGE_W, PAGE_H,
                           leftPadding=25 * mm, rightPadding=20 * mm,
                           topPadding=0, bottomPadding=0, id="cover")
    interior_frame = Frame(20 * mm, 20 * mm, PAGE_W - 40 * mm, PAGE_H - 55 * mm,
                           id="interior")

    def cover_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(BRAND_BLUE)
        canvas.rect(0, 0, 8 * mm, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    def interior_page(canvas, doc):
        _header_footer(canvas, doc, domain)

    doc.addPageTemplates([
        PageTemplate(id="Cover",    frames=[cover_frame],    onPage=cover_bg),
        PageTemplate(id="Interior", frames=[interior_frame], onPage=interior_page),
    ])

    # Section numbers: 10 = recommendations, 11 = cost (no deep)
    #                  11 = recommendations, 12 = cost (with deep)
    rec_num  = 11 if has_deep else 10
    cost_num = 12 if has_deep else 11

    story = []
    story.append(NextPageTemplate("Interior"))
    _section_cover(story, domain, agency, styles)
    _section_toc(story, has_deep, styles)
    _section_executive_summary(story, data, styles)
    _section_domain_overview(story, data, styles)
    _section_keywords(story, data, styles)
    _section_competitors(story, data, styles)
    _section_backlinks(story, data, styles)
    _section_onpage(story, data, styles)
    _section_page_speed(story, data, styles)
    _section_local_seo(story, data, styles)
    _section_aeo(story, data, styles)
    if has_deep:
        _section_gap_analysis(story, data, styles)
    _section_recommendations(story, data, rec_num, styles)
    _section_appendix(story, data, styles)
    _section_cost(story, data, cost_num, styles)

    doc.build(story)
    return output_path
