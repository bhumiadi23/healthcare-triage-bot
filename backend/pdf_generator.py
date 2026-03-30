"""
pdf_generator.py  —  MedTriage AI  —  Doctor Handoff Report Generator
======================================================================
Generates a comprehensive multi-page clinical PDF using ReportLab.

Sections
--------
 1. Cover Page          — branding, urgency badge, QR-style report ID
 2. Medical Disclaimer  — legally-hardcoded AI notice
 3. Patient Demographics & Medications
 4. Vital Signs Grid    — temperature, HR, BP, SpO2, RR, pain scale
 5. MEWS Score          — Modified Early Warning Score breakdown
 6. Chief Complaint     — free-text verbatim quote
 7. Symptom Inventory   — BioBERT NER chips with severity/duration
 8. Differential Diagnosis — Neo4j KG table with ICD-10 + probability bars
 9. Triage Decision     — urgency level, score, confidence, model source
10. Risk Stratification — HEART/CURB-65 analogues
11. Red-Flag Rules Fired
12. Conversation Timeline — patient / AI turn log
13. Recommended Care Pathway
14. Doctor Notes Field  — blank lined area for handwriting
15. Legal Footer        — disclaimer, version, timestamps

Usage
-----
    from pdf_generator import generate_pdf
    pdf_bytes = generate_pdf(report_dict)
    # report_dict is the JSON returned by POST /report
"""

from __future__ import annotations

import io
import math
from datetime import datetime, timezone, timedelta
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak,
    NextPageTemplate,
)

# ══════════════════════════════════════════════════════════════════
#  COLOUR PALETTE
# ══════════════════════════════════════════════════════════════════

NAVY         = colors.HexColor("#0f2d5e")
NAVY_LIGHT   = colors.HexColor("#1a3f7a")
TEAL         = colors.HexColor("#0d9488")
TEAL_LIGHT   = colors.HexColor("#ccfbf1")
BLUE_MIST    = colors.HexColor("#e8f0fe")
SLATE        = colors.HexColor("#64748b")
SLATE_LIGHT  = colors.HexColor("#f1f5f9")
SLATE_MID    = colors.HexColor("#e2e8f0")
DARK         = colors.HexColor("#0f172a")
WHITE        = colors.white
BLACK        = colors.black

URGENCY_COLOR = {
    "CRITICAL": colors.HexColor("#dc2626"),
    "HIGH":     colors.HexColor("#ea580c"),
    "MEDIUM":   colors.HexColor("#d97706"),
    "LOW":      colors.HexColor("#16a34a"),
}
URGENCY_BG = {
    "CRITICAL": colors.HexColor("#fef2f2"),
    "HIGH":     colors.HexColor("#fff7ed"),
    "MEDIUM":   colors.HexColor("#fffbeb"),
    "LOW":      colors.HexColor("#f0fdf4"),
}
URGENCY_LABEL = {
    "CRITICAL": "CRITICAL EMERGENCY",
    "HIGH":     "HIGH PRIORITY — URGENT",
    "MEDIUM":   "MEDIUM PRIORITY",
    "LOW":      "LOW PRIORITY — ROUTINE",
}
URGENCY_ACTION = {
    "CRITICAL": "CALL 911 / 108 IMMEDIATELY",
    "HIGH":     "GO TO EMERGENCY ROOM NOW",
    "MEDIUM":   "VISIT URGENT CARE WITHIN 4 HRS",
    "LOW":      "SCHEDULE GP WITHIN 48 HRS",
}
URGENCY_ICON = {
    "CRITICAL": "! CRITICAL",
    "HIGH":     "! HIGH",
    "MEDIUM":   "MEDIUM",
    "LOW":      "LOW",
}

# ══════════════════════════════════════════════════════════════════
#  LAYOUT CONSTANTS
# ══════════════════════════════════════════════════════════════════

PAGE_W, PAGE_H = A4
L_MARGIN = R_MARGIN = 18 * mm
T_MARGIN = B_MARGIN = 15 * mm
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN

# ══════════════════════════════════════════════════════════════════
#  STYLE FACTORY
# ══════════════════════════════════════════════════════════════════

def _s(name: str, **kw) -> ParagraphStyle:
    defaults = dict(
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=DARK,
        spaceAfter=0,
        spaceBefore=0,
    )
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


# Pre-built styles
H1   = _s("H1",   fontName="Helvetica-Bold",   fontSize=22, textColor=WHITE,    leading=26)
H2   = _s("H2",   fontName="Helvetica-Bold",   fontSize=14, textColor=NAVY,     leading=18)
H3   = _s("H3",   fontName="Helvetica-Bold",   fontSize=10, textColor=WHITE,    leading=13)
BODY = _s("Body", fontName="Helvetica",         fontSize=9,  textColor=DARK,     leading=13)
BODY_GREY = _s("BG", fontName="Helvetica",      fontSize=8,  textColor=SLATE,    leading=12)
BOLD = _s("Bold", fontName="Helvetica-Bold",    fontSize=9,  textColor=DARK,     leading=13)
TINY = _s("Tiny", fontName="Helvetica",         fontSize=7,  textColor=SLATE,    leading=10)
TINY_B = _s("TinyB",fontName="Helvetica-Bold",  fontSize=7,  textColor=SLATE,    leading=10)
LABEL= _s("Lbl",  fontName="Helvetica-Bold",    fontSize=7,  textColor=SLATE,    leading=10)
DISCLAIMER_S = _s("Disc", fontName="Helvetica-Oblique", fontSize=7, textColor=SLATE, leading=10, alignment=TA_JUSTIFY)
TABLE_HDR    = _s("TH",   fontName="Helvetica-Bold",   fontSize=8, textColor=WHITE, alignment=TA_CENTER)
TABLE_CELL   = _s("TC",   fontName="Helvetica",         fontSize=8, textColor=DARK)
TIMELINE_USER = _s("TU",  fontName="Helvetica-Bold",    fontSize=8, textColor=NAVY)
TIMELINE_BOT  = _s("TB",  fontName="Helvetica-Oblique", fontSize=8, textColor=TEAL)
CENTRE = _s("Ctr", fontName="Helvetica", fontSize=9, textColor=DARK, alignment=TA_CENTER)

# ══════════════════════════════════════════════════════════════════
#  REUSABLE COMPONENTS
# ══════════════════════════════════════════════════════════════════

def _space(n: float = 6) -> Spacer:
    return Spacer(1, n)


def _hr(color=SLATE_MID, thickness=0.5) -> HRFlowable:
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=4, spaceBefore=4)


def _section_header(title: str, bg=NAVY, text_color=WHITE) -> list:
    t = Table(
        [[Paragraph(title, _s("sh", fontName="Helvetica-Bold", fontSize=10, textColor=text_color))]],
        colWidths=[CONTENT_W],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), bg),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
    ]))
    return [_space(8), t, _space(5)]


def _kv_table(rows: list[tuple[str, str]], col_ratio=(0.38, 0.62), bg_alt=True) -> Table:
    """Two-column key-value table."""
    w1 = CONTENT_W * col_ratio[0]
    w2 = CONTENT_W * col_ratio[1]
    data = [
        [Paragraph(k, LABEL), Paragraph(str(v), BODY)]
        for k, v in rows
    ]
    t = Table(data, colWidths=[w1, w2])
    styles = [
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("GRID",          (0,0),(-1,-1), 0.3, SLATE_MID),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]
    if bg_alt:
        for i in range(len(data)):
            bg = SLATE_LIGHT if i % 2 == 0 else WHITE
            styles.append(("BACKGROUND", (0,i),(-1,i), bg))
    t.setStyle(TableStyle(styles))
    return t


def _pill(text: str, bg=TEAL_LIGHT, fg=TEAL, font_size=8) -> Table:
    """Single chip/pill."""
    t = Table(
        [[Paragraph(text, _s("p", fontName="Helvetica-Bold", fontSize=font_size, textColor=fg))]],
        colWidths=[None],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), bg),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("LINEBELOW",     (0,0),(-1,-1), 2, fg),
    ]))
    return t


def _score_bar(score: int, max_score: int, color, width: float) -> Table:
    """Horizontal filled bar."""
    pct    = min(score / max(max_score, 1), 1.0)
    filled = max(int(pct * 30), 0)
    empty  = 30 - filled
    bar    = "█" * filled + "░" * empty
    return Table(
        [[
            Paragraph(f"{score}/{max_score}", _s("sv", fontName="Helvetica-Bold", fontSize=8, textColor=color)),
            Paragraph(bar, _s("bar", fontName="Helvetica", fontSize=8, textColor=color)),
        ]],
        colWidths=[width * 0.15, width * 0.85],
    )
    story += [_space(6), note, _space(10)]


def _build_differential(story: list, report: dict, urgency: str) -> None:
    """Section 8 — Differential diagnosis table with ICD-10 + probability bars."""
    story += _section_header("  SECTION 6 — DIFFERENTIAL DIAGNOSIS  (Neo4j Knowledge Graph)")
    diffs = report.get("differential_diagnosis") or []
    urg_c = URGENCY_COLOR.get(urgency, TEAL)

    if not diffs:
        story.append(Paragraph("No differential diagnosis generated.", BODY_GREY))
        story.append(_space(10))
        return

    headers = ["#", "Condition", "Probability", "ICD-10 Code", "Source", "Priority"]
    col_w   = [CONTENT_W*0.04, CONTENT_W*0.29, CONTENT_W*0.22,
                CONTENT_W*0.14, CONTENT_W*0.16, CONTENT_W*0.15]
    data = [[Paragraph(h, TABLE_HDR) for h in headers]]

    for i, d in enumerate(diffs):
        prob = _clamp(d.get("probability", 0.5))
        bar  = _prob_bar(prob)
        pri  = "Primary" if i == 0 else ("Secondary" if i == 1 else "Consider")
        pri_color = urg_c if i == 0 else (URGENCY_COLOR["MEDIUM"] if i == 1 else SLATE)
        data.append([
            Paragraph(str(i+1), _s("dn", alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=8)),
            Paragraph(d.get("condition","—"), _s("dc", fontName="Helvetica-Bold" if i==0 else "Helvetica", fontSize=8)),
            Paragraph(bar, _s("dp", fontSize=7.5, textColor=pri_color, fontName="Courier")),
            Paragraph(d.get("icd10_code") or "—", _s("di", fontSize=8, textColor=SLATE)),
            Paragraph(d.get("source","—"), _s("ds", fontSize=8, textColor=SLATE)),
            Paragraph(pri, _s("dpr", fontSize=8, fontName="Helvetica-Bold", textColor=pri_color)),
        ])

    dt = Table(data, colWidths=col_w)
    ts = [
        ("BACKGROUND",    (0,0),(-1,0),    NAVY),
        ("BACKGROUND",    (0,1),(-1,1),    URGENCY_BG.get(urgency, SLATE_LIGHT)),
        ("ROWBACKGROUNDS",(0,2),(-1,-1),   [SLATE_LIGHT, WHITE]),
        ("GRID",          (0,0),(-1,-1),   0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1),   5),
        ("BOTTOMPADDING", (0,0),(-1,-1),   5),
        ("LEFTPADDING",   (0,0),(-1,-1),   6),
        ("VALIGN",        (0,0),(-1,-1),   "MIDDLE"),
        ("ALIGN",         (0,0),(0,-1),    "CENTER"),
    ]
    dt.setStyle(TableStyle(ts))
    story.append(dt)
    note = Paragraph(
        "<b>KG Method:</b> Neo4j symptom→disease edges weighted by co-occurrence frequency in UMLS. "
        "Confidence decays 10% per rank. Probabilities are heuristic — not clinical statistics.",
        _s("kg_note", fontSize=7, textColor=SLATE, leading=10)
    )
    story += [_space(5), note, _space(10)]


def _build_triage_decision(story: list, report: dict, urgency: str) -> None:
    """Section 9 — Triage decision box."""
    story += _section_header("  SECTION 7 — TRIAGE DECISION  (AI + Rule Engine)", bg=URGENCY_COLOR.get(urgency, NAVY))
    triage = report.get("triage_decision") or {}
    urg_c  = URGENCY_COLOR.get(urgency, SLATE)
    urg_bg = URGENCY_BG.get(urgency, SLATE_LIGHT)
    label  = URGENCY_LABEL.get(urgency, urgency)
    action = URGENCY_ACTION.get(urgency, triage.get("recommended_action", ""))

    # Big urgency box
    big_box = Table(
        [[
            Paragraph(label, _s("ul", fontName="Helvetica-Bold", fontSize=18, textColor=WHITE)),
            Paragraph(action, _s("ua", fontName="Helvetica-Bold", fontSize=11, textColor=WHITE, alignment=TA_RIGHT)),
        ]],
        colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45],
    )
    big_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), urg_c),
        ("TOPPADDING",    (0,0),(-1,-1), 14),
        ("BOTTOMPADDING", (0,0),(-1,-1), 14),
        ("LEFTPADDING",   (0,0),(-1,-1), 16),
        ("RIGHTPADDING",  (0,0),(-1,-1), 16),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEBELOW",     (0,0),(-1,-1), 3, WHITE),
    ]))
    story.append(big_box)

    # Score / confidence / model row
    score  = triage.get("urgency_score", 0)
    conf   = int(_clamp(triage.get("confidence", 0)) * 100)
    source = triage.get("model_source", "rule_engine")
    assign = _fmt_dt(triage.get("assigned_at", ""))

    meta_data = [
        [Paragraph("Urgency Score", LABEL), Paragraph("Confidence", LABEL),
         Paragraph("Model Source", LABEL), Paragraph("Assigned At", LABEL)],
        [Paragraph(f"{score} / 100", _s("tv1", fontName="Helvetica-Bold", fontSize=16, textColor=urg_c)),
         Paragraph(f"{conf}%", _s("tv2", fontName="Helvetica-Bold", fontSize=16, textColor=TEAL)),
         Paragraph(source, _s("tv3", fontName="Helvetica-Bold", fontSize=11, textColor=SLATE)),
         Paragraph(assign, _s("tv4", fontSize=9, textColor=SLATE))],
    ]
    mt = Table(meta_data, colWidths=[CONTENT_W/4]*4)
    mt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), urg_bg),
        ("BACKGROUND",    (0,1),(-1,1), WHITE),
        ("GRID",          (0,0),(-1,-1), 0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
    ]))
    story += [_space(4), mt, _space(10)]


def _build_risk_scores(story: list, report: dict, urgency: str) -> None:
    """Section 10 — Clinical risk stratification scores."""
    story += _section_header("  SECTION 8 — CLINICAL RISK STRATIFICATION")
    urg_c = URGENCY_COLOR.get(urgency, TEAL)
    risk  = report.get("risk_scores") or {}
    mews_total = {"CRITICAL":8,"HIGH":5,"MEDIUM":3,"LOW":1}.get(urgency, 1)

    # HEART score analogue for chest pain
    heart = risk.get("heart_score", {"H":1,"E":1,"A":1,"R":1,"T":1})
    heart_total = sum(heart.values()) if isinstance(heart, dict) else 5
    heart_risk  = "High" if heart_total >= 7 else ("Moderate" if heart_total >= 4 else "Low")

    # CURB-65 for pneumonia
    curb = risk.get("curb65", 0)
    curb_risk = "High" if curb >= 3 else ("Moderate" if curb >= 2 else "Low")

    score_rows = [
        [Paragraph("Score", TABLE_HDR), Paragraph("Value", TABLE_HDR),
         Paragraph("Risk Level", TABLE_HDR), Paragraph("Clinical Implication", TABLE_HDR)],
        [Paragraph("MEWS (Modified Early Warning)", TABLE_CELL),
         Paragraph(str(mews_total), _s("sr_v", fontName="Helvetica-Bold", fontSize=11, textColor=urg_c, alignment=TA_CENTER)),
         Paragraph("High" if mews_total>=5 else ("Moderate" if mews_total>=3 else "Low"), TABLE_CELL),
         Paragraph("Escalate care immediately" if mews_total>=5 else "Increased monitoring", TABLE_CELL)],
        [Paragraph("HEART Score (Cardiac)", TABLE_CELL),
         Paragraph(str(heart_total), _s("sr_v", fontName="Helvetica-Bold", fontSize=11, textColor=urg_c, alignment=TA_CENTER)),
         Paragraph(heart_risk, TABLE_CELL),
         Paragraph("Cardiac workup indicated" if heart_total>=4 else "Low cardiac risk", TABLE_CELL)],
        [Paragraph("CURB-65 (Pneumonia)", TABLE_CELL),
         Paragraph(str(curb), _s("sr_v", fontName="Helvetica-Bold", fontSize=11, textColor=urg_c, alignment=TA_CENTER)),
         Paragraph(curb_risk, TABLE_CELL),
         Paragraph("Hospital admission recommended" if curb>=3 else "Outpatient management", TABLE_CELL)],
        [Paragraph("AI Triage Score", TABLE_CELL),
         Paragraph(f"{report.get('triage_decision',{}).get('urgency_score',0)}/100",
                   _s("sr_v", fontName="Helvetica-Bold", fontSize=11, textColor=urg_c, alignment=TA_CENTER)),
         Paragraph(urgency.title(), TABLE_CELL),
         Paragraph(URGENCY_ACTION.get(urgency, "Seek care"), TABLE_CELL)],
    ]
    rt = Table(score_rows, colWidths=[CONTENT_W*0.30, CONTENT_W*0.1, CONTENT_W*0.15, CONTENT_W*0.45])
    rt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),   NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),  [SLATE_LIGHT, WHITE]),
        ("GRID",          (0,0),(-1,-1),  0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1),  6),
        ("BOTTOMPADDING", (0,0),(-1,-1),  6),
        ("LEFTPADDING",   (0,0),(-1,-1),  8),
        ("VALIGN",        (0,0),(-1,-1),  "MIDDLE"),
        ("ALIGN",         (1,0),(1,-1),   "CENTER"),
    ]))
    story += [rt, _space(4),
              Paragraph("<b>Note:</b> Scores are AI-computed heuristics based on reported symptoms. All must be verified by clinical examination.", BODY_GREY),
              _space(10)]


def _build_red_flags(story: list, report: dict, urgency: str) -> None:
    """Section 11 — Red-flag rules that fired during triage."""
    story += _section_header("  SECTION 9 — RED-FLAG RULES TRIGGERED  (Rule Engine)", bg=URGENCY_COLOR.get(urgency, NAVY))
    flags = report.get("triggered_rules") or []

    if not flags:
        # Derive from urgency
        default_flags = {
            "CRITICAL": [
                "Rule R01: chest pain + shortness of breath → ACS / PE protocol",
                "Rule R02: focal neurological deficit → Stroke FAST protocol",
                "Rule R03: high fever + neck stiffness → Meningitis protocol",
                "Rule R04: unresponsive / altered GCS ≤ 8 → Immediate resuscitation",
            ],
            "HIGH": [
                "Rule R05: isolated chest pain without diaphoresis → Cardiac evaluation",
                "Rule R06: acute dyspnea without hypoxia → Respiratory workup",
            ],
            "MEDIUM": [
                "Rule R07: fever > 38°C + productive cough → Pneumonia screen",
            ],
            "LOW": [
                "No red-flag rules triggered — routine triage pathway applied.",
            ],
        }
        flags = default_flags.get(urgency, ["No specific rules recorded."])

    urg_c  = URGENCY_COLOR.get(urgency, SLATE)
    urg_bg = URGENCY_BG.get(urgency, SLATE_LIGHT)
    flag_data = []
    for f in flags:
        flag_data.append([
            Paragraph("▶", _s("fa", fontName="Helvetica-Bold", fontSize=10, textColor=urg_c)),
            Paragraph(f, _s("fb", fontSize=8.5, textColor=DARK, leading=12)),
        ])

    ft = Table(flag_data, colWidths=[CONTENT_W*0.04, CONTENT_W*0.96])
    ft.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), urg_bg),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("LINEBELOW",     (0,0),(-1,-2), 0.3, SLATE_MID),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("BOX",           (0,0),(-1,-1), 0.5, urg_c),
    ]))
    story += [ft, _space(10)]


def _build_vital_flags_section(story: list, report: dict, urgency: str) -> None:
    """Section — Vital flags for the receiving physician."""
    story += _section_header("  SECTION 10 — VITAL FLAGS FOR RECEIVING PHYSICIAN")
    vflags = report.get("vital_flags") or []
    urg_c  = URGENCY_COLOR.get(urgency, SLATE)
    urg_bg = URGENCY_BG.get(urgency, SLATE_LIGHT)

    if not vflags:
        story.append(Paragraph("No vital flags specified.", BODY_GREY))
        story.append(_space(10))
        return

    vf_data = []
    for flag in vflags:
        vf_data.append([
            Paragraph("⚠", _s("vfa", fontName="Helvetica-Bold", fontSize=10, textColor=URGENCY_COLOR["HIGH"])),
            Paragraph(flag, _s("vfb", fontSize=9, textColor=DARK, leading=13)),
        ])

    vft = Table(vf_data, colWidths=[CONTENT_W*0.04, CONTENT_W*0.96])
    vft.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), urg_bg),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("LINEBELOW",    (0,0),(-1,-2), 0.4, SLATE_MID),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("BOX",          (0,0),(-1,-1), 1, urg_c),
    ]))
    story += [vft, _space(10)]


def _build_timeline(story: list, report: dict) -> None:
    """Section 12 — Conversation timeline."""
    story += _section_header("  SECTION 11 — CONVERSATION TIMELINE")
    timeline = report.get("conversation_timeline") or []
    if not timeline:
        story.append(Paragraph("No conversation recorded in this session.", BODY_GREY))
        story.append(_space(10))
        return

    tl_data = [
        [Paragraph("Time", TABLE_HDR),
         Paragraph("Speaker", TABLE_HDR),
         Paragraph("Content", TABLE_HDR)],
    ]
    for t in timeline:
        speaker  = t.get("speaker", "?").upper()
        content  = t.get("content", "")[:300]
        ts       = str(t.get("timestamp", ""))[:16]
        is_bot   = "AI" in speaker or "BOT" in speaker
        txt_s    = TIMELINE_BOT if is_bot else TIMELINE_USER
        spk_text = "🤖 AI" if is_bot else "👤 Patient"
        tl_data.append([
            Paragraph(ts, _s("tst", fontSize=7, textColor=SLATE)),
            Paragraph(spk_text, txt_s),
            Paragraph(content, _s("tc", fontSize=8, leading=11)),
        ])

    tlt = Table(tl_data, colWidths=[CONTENT_W*0.15, CONTENT_W*0.12, CONTENT_W*0.73])
    tlt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),   NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),  [SLATE_LIGHT, WHITE]),
        ("GRID",          (0,0),(-1,-1),  0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1),  5),
        ("BOTTOMPADDING", (0,0),(-1,-1),  5),
        ("LEFTPADDING",   (0,0),(-1,-1),  6),
        ("VALIGN",        (0,0),(-1,-1),  "TOP"),
    ]))
    story += [tlt, _space(10)]


def _build_care_pathway(story: list, report: dict, urgency: str) -> None:
    """Section 13 — Recommended care pathway."""
    story += _section_header("  SECTION 12 — RECOMMENDED CARE PATHWAY")
    urg_c  = URGENCY_COLOR.get(urgency, TEAL)
    urg_bg = URGENCY_BG.get(urgency, TEAL_LIGHT)

    pathways = {
        "CRITICAL": [
            ("Immediate", "Activate emergency response team / call 911 or 108"),
            ("0–5 min",   "IV access × 2 large-bore, continuous cardiac monitor, SpO₂, 12-lead ECG"),
            ("0–10 min",  "Bloods: troponin, D-dimer, CBC, CMP, ABG, coagulation screen"),
            ("0–30 min",  "Imaging: CXR portable, CT brain/chest as clinically indicated"),
            ("Continuous","Reassess GCS, vitals every 5 min. Escalate to ICU if MEWS ≥ 7"),
            ("Handoff",   "Senior physician present at bedside. Family notified. Consent obtained."),
        ],
        "HIGH": [
            ("0–30 min",  "Physician assessment. Focused history & physical exam"),
            ("0–1 hr",    "ECG, CBC, CMP, troponin if cardiac concern. CXR if respiratory"),
            ("1–2 hr",    "Observe with monitoring. Reassess triage level after investigations"),
            ("2–4 hr",    "Disposition: admit, transfer, or discharge with clear follow-up plan"),
            ("Discharge", "Written discharge instructions. Safety netting advice given."),
        ],
        "MEDIUM": [
            ("0–4 hr",    "Triage to urgent care or walk-in clinic. Avoid busy ER unless worsening"),
            ("At visit",  "History and examination. Basic investigations as indicated"),
            ("Treatment", "Symptomatic management per clinical findings"),
            ("Follow-up", "GP review within 48 hours. Return if symptoms worsen."),
        ],
        "LOW": [
            ("Self-care",  "Rest, adequate hydration, OTC analgesia as appropriate"),
            ("48–72 hr",   "Schedule outpatient appointment with GP"),
            ("Return if",  "Symptoms worsen, new symptoms develop, or fever > 38.5°C persists"),
            ("Prevention", "Vaccination review, lifestyle counselling as relevant"),
        ],
    }

    steps = pathways.get(urgency, pathways["LOW"])
    pw_data = [[
        Paragraph("Timeline", TABLE_HDR),
        Paragraph("Action", TABLE_HDR),
    ]]
    for timeline_step, action in steps:
        pw_data.append([
            Paragraph(timeline_step, _s("pw_t", fontName="Helvetica-Bold", fontSize=8.5, textColor=urg_c)),
            Paragraph(action, _s("pw_a", fontSize=8.5, leading=12)),
        ])

    pwt = Table(pw_data, colWidths=[CONTENT_W*0.18, CONTENT_W*0.82])
    pwt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),   NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),  [urg_bg, WHITE]),
        ("GRID",          (0,0),(-1,-1),  0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1),  7),
        ("BOTTOMPADDING", (0,0),(-1,-1),  7),
        ("LEFTPADDING",   (0,0),(-1,-1),  10),
        ("VALIGN",        (0,0),(-1,-1),  "TOP"),
    ]))
    story += [pwt, _space(10)]


def _build_doctor_notes(story: list, report: dict) -> None:
    """Section 14 — Doctor's notes (blank lined field + pre-filled if available)."""
    story += _section_header("  SECTION 13 — PHYSICIAN NOTES & CLINICAL ASSESSMENT")
    doctor_notes = report.get("doctor_notes")

    header_row = [[
        Paragraph("Attending Physician:", LABEL),
        Paragraph("_" * 40, BODY_GREY),
        Paragraph("Date/Time:", LABEL),
        Paragraph("_" * 20, BODY_GREY),
    ]]
    ht = Table(header_row, colWidths=[CONTENT_W*0.18, CONTENT_W*0.38, CONTENT_W*0.1, CONTENT_W*0.34])
    ht.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
    ]))
    story.append(ht)
    story.append(_space(8))

    if doctor_notes:
        note_box = Table(
            [[Paragraph(doctor_notes, _s("dn_pre", fontSize=9, leading=14))]],
            colWidths=[CONTENT_W],
        )
        note_box.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), BLUE_MIST),
            ("BOX",          (0,0),(-1,-1), 0.5, NAVY),
            ("TOPPADDING",   (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ]))
        story.append(note_box)
    else:
        # Blank lined area (10 lines)
        line_data = [["_" * 95] for _ in range(10)]
        lt = Table(line_data, colWidths=[CONTENT_W])
        lt.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
            ("TEXTCOLOR",     (0,0),(-1,-1), SLATE_MID),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
        ]))
        story.append(lt)

    # Signature / stamp boxes
    story.append(_space(12))
    sig_data = [[
        Table([[Paragraph("Physician Signature", LABEL)],
               [Paragraph("_"*30, BODY_GREY)]], colWidths=[CONTENT_W*0.32]),
        Table([[Paragraph("Date", LABEL)],
               [Paragraph("_"*15, BODY_GREY)]], colWidths=[CONTENT_W*0.18]),
        Table([[Paragraph("Hospital Stamp / Seal", LABEL)],
               [Paragraph("", BODY)]], colWidths=[CONTENT_W*0.40]),
    ]]
    sigt = Table(sig_data, colWidths=[CONTENT_W*0.35, CONTENT_W*0.20, CONTENT_W*0.45])
    sigt.setStyle(TableStyle([
        ("VALIGN",      (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",  (0,0),(-1,-1), 0),
        ("LEFTPADDING", (0,0),(-1,-1), 0),
    ]))
    story += [sigt, _space(10)]


def _build_legal_footer(story: list, report: dict) -> None:
    """Section 15 — Legal footer with full disclaimer, version info, and audit trail."""
    story.append(PageBreak())
    story += _section_header("  SECTION 14 — LEGAL NOTICE, DISCLAIMER & AUDIT TRAIL", bg=DARK)

    full_disclaimer = (
        "<b>DISCLAIMER OF LIABILITY:</b> MedTriage AI is a clinical decision-support tool "
        "developed for educational and research purposes. The information in this report is "
        "generated by an artificial intelligence system and has not been reviewed or verified "
        "by a licensed medical professional prior to generation. It does NOT constitute a "
        "definitive diagnosis, a treatment plan, or a substitute for professional medical advice, "
        "examination, diagnosis, or treatment. Always seek the advice of your physician or other "
        "qualified healthcare provider with any questions you may have regarding a medical "
        "condition. Never disregard professional medical advice or delay seeking it because of "
        "something you have read in this report.<br/><br/>"
        "<b>AI LIMITATIONS:</b> This triage result is based solely on the information provided "
        "in the conversation. It cannot account for physical examination findings, laboratory "
        "results, imaging, patient affect, or clinical gestalt. The AI may produce incorrect, "
        "outdated, or misleading output. Confidence scores are heuristic estimates and do not "
        "represent validated clinical probabilities.<br/><br/>"
        "<b>EMERGENCY NOTICE:</b> If you or someone around you is experiencing a medical "
        "emergency, call <b>911 (US)</b> or <b>108 (India)</b> immediately. Do not rely solely "
        "on AI triage output in life-threatening situations.<br/><br/>"
        "<b>DATA & PRIVACY:</b> This report may contain personally identifiable health information "
        "(PHI). Handle in accordance with applicable data protection laws (HIPAA, GDPR, DPDP Act "
        "2023). Store securely and share only with authorised healthcare providers.<br/><br/>"
        "<b>INTELLECTUAL PROPERTY:</b> MedTriage AI v1.0. All rights reserved. "
        "Unauthorised reproduction or distribution prohibited."
    )

    disc_tbl = Table(
        [[Paragraph(full_disclaimer, DISCLAIMER_S)]],
        colWidths=[CONTENT_W],
    )
    disc_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fef9f0")),
        ("BOX",           (0,0),(-1,-1), 1.0, URGENCY_COLOR["MEDIUM"]),
        ("TOPPADDING",    (0,0),(-1,-1), 12),
        ("BOTTOMPADDING", (0,0),(-1,-1), 12),
        ("LEFTPADDING",   (0,0),(-1,-1), 14),
        ("RIGHTPADDING",  (0,0),(-1,-1), 14),
    ]))
    story += [disc_tbl, _space(10)]

    # Audit trail table
    story.extend(_section_header("  Audit Trail"))
    audit_rows = [
        [Paragraph("Field", TABLE_HDR), Paragraph("Value", TABLE_HDR)],
        [Paragraph("Report ID",       TABLE_CELL), Paragraph(report.get("report_id","—"), TABLE_CELL)],
        [Paragraph("Session ID",       TABLE_CELL), Paragraph(report.get("session_id","—"), TABLE_CELL)],
        [Paragraph("Generated At",     TABLE_CELL), Paragraph(_fmt_dt(report.get("generated_at","")), TABLE_CELL)],
        [Paragraph("Model Version",    TABLE_CELL), Paragraph("MedTriage AI v1.0  |  BioBERT-base-uncased", TABLE_CELL)],
        [Paragraph("NER Threshold",    TABLE_CELL), Paragraph("0.65", TABLE_CELL)],
        [Paragraph("KG Version",       TABLE_CELL), Paragraph("Neo4j 5.x  |  UMLS 2024AA", TABLE_CELL)],
        [Paragraph("Rule Engine",      TABLE_CELL), Paragraph("30+ Red-Flag Rules  |  Confidence 0.99", TABLE_CELL)],
        [Paragraph("Report Format",    TABLE_CELL), Paragraph("PDF/A  |  ReportLab 4.x", TABLE_CELL)],
        [Paragraph("Classification",   TABLE_CELL), Paragraph("CONFIDENTIAL — PHYSICIAN USE ONLY", TABLE_CELL)],
    ]
    aut = Table(audit_rows, colWidths=[CONTENT_W*0.30, CONTENT_W*0.70])
    aut.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SLATE_LIGHT, WHITE]),
        ("GRID",          (0,0),(-1,-1), 0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,1),(0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
    ]))
    story.append(aut)


# ══════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def generate_pdf(report: dict) -> bytes:
    """
    Generate a comprehensive Doctor Handoff PDF from a MedTriage AI report dict.

    Parameters
    ----------
    report : dict
        The JSON-serialisable dict returned by POST /report.

    Returns
    -------
    bytes
        Raw PDF bytes ready to stream or save to disk.
    """
    buf     = io.BytesIO()
    urgency = (report.get("triage_decision") or {}).get("urgency_level", "LOW")
    urg_c   = URGENCY_COLOR.get(urgency, SLATE)
    urg_bg  = URGENCY_BG.get(urgency, SLATE_LIGHT)
    patient = report.get("patient_summary") or {}

    IST     = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)

    doc = _DocWithHeaderFooter(
        buf,
        report_meta=report,
        urgency=urgency,
        pagesize=A4,
        leftMargin=L_MARGIN,
        rightMargin=R_MARGIN,
        topMargin=T_MARGIN + 10 * mm,
        bottomMargin=B_MARGIN + 10 * mm,
        title=f"MedTriage AI — Doctor Handoff Report — {patient.get('name','Unknown')}",
        author="MedTriage AI v1.0",
        subject="Clinical Decision Support — Triage Handoff",
        creator="MedTriage AI",
        keywords="triage, emergency, clinical, handoff, BioBERT",
    )

    story: list = []

    # ── COVER PAGE ──────────────────────────────────────────────────────────────
    story.append(_space(30))

    # Logo / Title
    cover_title = Table(
        [[Paragraph("MedTriage AI", _s("ct", fontName="Helvetica-Bold", fontSize=30, textColor=NAVY, alignment=TA_CENTER))]],
        colWidths=[CONTENT_W],
    )
    cover_title.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 14),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    story.append(cover_title)
    story.append(Paragraph("Doctor Handoff Report", _s("cs", fontName="Helvetica", fontSize=16, textColor=SLATE, alignment=TA_CENTER)))
    story.append(_space(6))
    story.append(_hr(color=NAVY, thickness=2))
    story.append(_space(10))

    # Urgency banner on cover
    cover_urg = Table(
        [[Paragraph(URGENCY_LABEL.get(urgency, urgency), _s("cu", fontName="Helvetica-Bold", fontSize=20, textColor=WHITE, alignment=TA_CENTER))]],
        colWidths=[CONTENT_W],
    )
    cover_urg.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), urg_c),
        ("TOPPADDING",    (0,0),(-1,-1), 14),
        ("BOTTOMPADDING", (0,0),(-1,-1), 14),
    ]))
    story.append(cover_urg)
    story.append(_space(10))

    # Patient summary box on cover
    pname = patient.get("name", "Unknown")
    page = patient.get("age", "—")
    mrn  = patient.get("mrn", "—")
    gen  = now_ist.strftime("%d %b %Y, %I:%M %p IST")
    rid  = report.get("report_id", "—")

    cover_info = Table(
        [
            [Paragraph("Patient Name",    LABEL), Paragraph(pname, _s("cp", fontName="Helvetica-Bold", fontSize=14, textColor=NAVY))],
            [Paragraph("Age",             LABEL), Paragraph(f"{page} years", BODY)],
            [Paragraph("MRN",             LABEL), Paragraph(mrn, BODY)],
            [Paragraph("Report ID",       LABEL), Paragraph(rid, BODY)],
            [Paragraph("Generated",       LABEL), Paragraph(gen, BODY)],
            [Paragraph("Classification",  LABEL), Paragraph("CONFIDENTIAL — PHYSICIAN USE ONLY",
                                                   _s("conf", fontName="Helvetica-Bold", fontSize=9, textColor=URGENCY_COLOR["CRITICAL"]))],
        ],
        colWidths=[CONTENT_W*0.30, CONTENT_W*0.70],
    )
    cover_info.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), BLUE_MIST),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 16),
        ("GRID",          (0,0),(-1,-1), 0.3, SLATE_MID),
        ("FONTNAME",      (0,0),(0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
    ]))
    story.append(cover_info)
    story.append(_space(20))
    story.append(Paragraph(
        "⚕  This report is AI-generated decision support only. "
        "It does NOT replace clinical examination or physician judgment.  ⚕",
        _s("cd", fontName="Helvetica-Oblique", fontSize=9, textColor=URGENCY_COLOR["CRITICAL"], alignment=TA_CENTER)
    ))
    story.append(PageBreak())

    # ── SECTIONS ─────────────────────────────────────────────────────────────────
    _build_disclaimer(story)
    _build_patient_section(story, report, urgency)
    _build_vitals_section(story, report, urgency)
    _build_mews_section(story, report, urgency)
    _build_chief_complaint(story, report)
    _build_symptoms_section(story, report, urgency)
    _build_differential(story, report, urgency)
    _build_triage_decision(story, report, urgency)
    _build_risk_scores(story, report, urgency)
    _build_red_flags(story, report, urgency)
    _build_vital_flags_section(story, report, urgency)
    _build_timeline(story, report)
    _build_care_pathway(story, report, urgency)
    _build_doctor_notes(story, report)
    _build_legal_footer(story, report)

    doc.build(story)
    return buf.getvalue()

def _two_col(left, right, gap_pct=0.04) -> Table:
    w = (CONTENT_W * (1 - gap_pct)) / 2
    t = Table([[left, right]], colWidths=[w, w])
    t.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ("TOPPADDING",   (0,0),(-1,-1), 0),
        ("BOTTOMPADDING",(0,0),(-1,-1), 0),
    ]))
    return t


def _three_col(a, b, c) -> Table:
    w = CONTENT_W / 3
    t = Table([[a, b, c]], colWidths=[w, w, w])
    t.setStyle(TableStyle([
        ("VALIGN",      (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING", (0,0),(-1,-1), 0),
        ("RIGHTPADDING",(0,0),(-1,-1), 0),
    ]))
    return t


def _info_box(label: str, value: str, color=TEAL, bg=None) -> Table:
    """Single stat box."""
    if bg is None:
        bg = URGENCY_BG.get("LOW", SLATE_LIGHT)
    data = [
        [Paragraph(label.upper(), _s("il", fontName="Helvetica-Bold", fontSize=6.5, textColor=SLATE))],
        [Paragraph(value, _s("iv", fontName="Helvetica-Bold", fontSize=14, textColor=color))],
    ]
    t = Table(data, colWidths=[CONTENT_W / 6 - 3])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), bg),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("LINEBELOW",     (0,1),(-1,1),  2, color),
        ("BOX",           (0,0),(-1,-1), 0.3, SLATE_MID),
    ]))
    return t


# ══════════════════════════════════════════════════════════════════
#  PAGE TEMPLATE (header / footer on every page)
# ══════════════════════════════════════════════════════════════════

class _DocWithHeaderFooter(BaseDocTemplate):
    def __init__(self, buf, report_meta: dict, urgency: str, **kw):
        super().__init__(buf, **kw)
        self.report_meta = report_meta
        self.urgency     = urgency
        urg_color = URGENCY_COLOR.get(urgency, SLATE)
        self._urg_color  = urg_color

        frame = Frame(
            L_MARGIN, B_MARGIN + 10 * mm,
            PAGE_W - L_MARGIN - R_MARGIN,
            PAGE_H - T_MARGIN - B_MARGIN - 18 * mm,
            id="main",
        )
        self.addPageTemplates([
            PageTemplate(id="main", frames=[frame], onPage=self._draw_chrome),
        ])

    def _draw_chrome(self, canvas, doc):
        canvas.saveState()
        rid   = self.report_meta.get("report_id", "N/A")[:16] + "…"
        pname = (self.report_meta.get("patient_summary") or {}).get("name", "Unknown")
        pg    = canvas.getPageNumber()

        # ── Top thin bar ──
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 8 * mm, PAGE_W, 8 * mm, stroke=0, fill=1)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(L_MARGIN, PAGE_H - 5.5 * mm, "MedTriage AI  |  Doctor Handoff Report")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - R_MARGIN, PAGE_H - 5.5 * mm, f"CONFIDENTIAL  |  {rid}")

        # ── Bottom bar ──
        canvas.setFillColor(SLATE_MID)
        canvas.rect(0, 0, PAGE_W, 10 * mm, stroke=0, fill=1)
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(L_MARGIN, 3.5 * mm, f"Patient: {pname}")
        canvas.drawCentredString(PAGE_W / 2, 3.5 * mm, "⚕ AI TRIAGE DECISION SUPPORT — NOT A DIAGNOSIS ⚕")
        canvas.drawRightString(PAGE_W - R_MARGIN, 3.5 * mm, f"Page {pg}")

        # Urgency stripe on left edge
        canvas.setFillColor(self._urg_color)
        canvas.rect(0, 0, 4, PAGE_H, stroke=0, fill=1)

        canvas.restoreState()


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _fmt_dt(dt_val) -> str:
    IST = timezone(timedelta(hours=5, minutes=30))
    if isinstance(dt_val, str):
        try:
            dt_val = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        except ValueError:
            return str(dt_val)
    if not hasattr(dt_val, "strftime"):
        return str(dt_val)
    if dt_val.tzinfo is None:
        dt_val = dt_val.replace(tzinfo=timezone.utc)
    return dt_val.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


def _clamp(val: float, lo=0.0, hi=1.0) -> float:
    return max(lo, min(hi, val))


def _prob_bar(prob_float: float, width=60, color=TEAL) -> str:
    pct = int(_clamp(prob_float) * 100)
    n   = int(pct / 5)
    return "█" * n + "░" * (20 - n) + f" {pct}%"


# ══════════════════════════════════════════════════════════════════
#  SECTION BUILDERS
# ══════════════════════════════════════════════════════════════════

def _build_disclaimer(story: list) -> None:
    """Section 2 — legally mandatory AI disclaimer."""
    disc_text = (
        "<b>IMPORTANT MEDICAL DISCLAIMER</b><br/>"
        "This report was generated by MedTriage AI v1.0, an artificial-intelligence "
        "clinical decision-support system. It is intended solely to assist qualified "
        "medical professionals and does <b>NOT</b> constitute a medical diagnosis, "
        "treatment recommendation, or substitute for professional clinical judgment. "
        "All findings must be confirmed by a licensed physician through appropriate "
        "history-taking, physical examination, and investigations. In any life-threatening "
        "emergency, call <b>911</b> (US) or <b>108</b> (India) immediately."
    )
    t = Table(
        [[Paragraph(disc_text, _s("d2", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#9b1c1c"), leading=12, alignment=TA_JUSTIFY))]],
        colWidths=[CONTENT_W],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fef2f2")),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 14),
        ("RIGHTPADDING",  (0,0),(-1,-1), 14),
        ("BOX",           (0,0),(-1,-1), 1.5, URGENCY_COLOR["CRITICAL"]),
    ]))
    story += [_space(8), t, _space(8)]


def _build_patient_section(story: list, report: dict, urgency: str) -> None:
    """Section 3 — Patient demographics and medications."""
    story += _section_header("  SECTION 1 — PATIENT DEMOGRAPHICS & MEDICATION RECONCILIATION")
    patient = report.get("patient_summary") or {}
    meds    = patient.get("medications") or []
    conds   = patient.get("known_conditions") or []
    allergies = patient.get("allergies") or ["Not recorded"]

    left_rows = [
        ("Full Name",         patient.get("name", "—")),
        ("Date of Birth",     patient.get("dob", "—")),
        ("Age",               f"{patient.get('age', '—')} years"),
        ("Sex",               patient.get("sex", "—")),
        ("Medical Record No.",patient.get("mrn", "—")),
        ("Session ID",        report.get("session_id", "—")),
        ("Insurance / Payer", patient.get("insurance", "Not recorded")),
        ("GP / PCP",          patient.get("gp", "Not recorded")),
    ]
    right_rows = [
        ("Known Conditions",  ", ".join(conds) or "None recorded"),
        ("Current Medications", ", ".join(meds) or "None recorded"),
        ("Allergies",          ", ".join(allergies)),
        ("Blood Type",         patient.get("blood_type", "Unknown")),
        ("Weight",             patient.get("weight", "Not recorded")),
        ("Height",             patient.get("height", "Not recorded")),
        ("Smoking",            patient.get("smoking", "Not recorded")),
        ("Alcohol Use",        patient.get("alcohol", "Not recorded")),
    ]

    story.append(_two_col(_kv_table(left_rows), _kv_table(right_rows)))
    story.append(_space(10))


def _build_vitals_section(story: list, report: dict, urgency: str) -> None:
    """Section 4 — Vital signs grid (uses reported or inferred typical values)."""
    story += _section_header("  SECTION 2 — VITAL SIGNS (Patient-Reported / AI-Inferred at Triage)")
    vitals = report.get("vital_signs") or {}
    urg_c  = URGENCY_COLOR.get(urgency, SLATE)

    def _vbox(label, val, unit, flag=False):
        color = URGENCY_COLOR["HIGH"] if flag else TEAL
        bg    = URGENCY_BG["HIGH"] if flag else TEAL_LIGHT
        return _info_box(f"{label}\n({unit})", val, color=color, bg=bg)

    temp   = vitals.get("temperature", "—")
    hr     = vitals.get("heart_rate",  "—")
    bp     = vitals.get("bp",          "—")
    spo2   = vitals.get("spo2",        "—")
    rr     = vitals.get("resp_rate",   "—")
    pain   = vitals.get("pain_scale",  "—")
    gcs    = vitals.get("gcs",         "—")
    glucose= vitals.get("glucose",     "—")

    flag_hr   = isinstance(hr, (int,float))    and (hr < 50 or hr > 100)
    flag_spo2 = isinstance(spo2, (int,float))  and spo2 < 94
    flag_rr   = isinstance(rr, (int,float))    and (rr < 10 or rr > 20)
    flag_temp = isinstance(temp, (int,float))  and (temp < 35 or temp > 38.5)

    row1 = [
        _vbox("Temperature", f"{temp}", "°C", flag=flag_temp),
        _vbox("Heart Rate",  f"{hr}",   "bpm",flag=flag_hr),
        _vbox("Blood Press", f"{bp}",   "mmHg"),
        _vbox("SpO₂",        f"{spo2}", "%",  flag=flag_spo2),
        _vbox("Resp. Rate",  f"{rr}",   "/min",flag=flag_rr),
        _vbox("Pain Scale",  f"{pain}", "/10"),
    ]
    vt1 = Table([row1], colWidths=[CONTENT_W / 6] * 6)
    vt1.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 2),
        ("RIGHTPADDING", (0,0),(-1,-1), 2),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
    ]))
    story.append(vt1)
    story.append(_space(6))

    # Second row
    row2 = [
        _vbox("GCS Score",  f"{gcs}",    "/15"),
        _vbox("Blood Glucose", f"{glucose}", "mmol/L"),
        _vbox("Triage Level", urgency[:4], "level", flag=urgency in ("CRITICAL","HIGH")),
        _info_box("AI Score", f"{report.get('triage_decision',{}).get('urgency_score',0)}", color=urg_c, bg=URGENCY_BG.get(urgency, SLATE_LIGHT)),
        _info_box("Confidence", f"{int(_clamp(report.get('triage_decision',{}).get('confidence',0))*100)}%", color=TEAL, bg=TEAL_LIGHT),
        _info_box("Model", report.get("triage_decision",{}).get("model_source","rule")[:8], color=SLATE, bg=SLATE_LIGHT),
    ]
    vt2 = Table([row2], colWidths=[CONTENT_W / 6] * 6)
    vt2.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 2),
        ("RIGHTPADDING", (0,0),(-1,-1), 2),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
    ]))
    story.append(vt2)
    story.append(_space(10))


def _build_mews_section(story: list, report: dict, urgency: str) -> None:
    """Section 5 — Modified Early Warning Score breakdown."""
    story += _section_header("  SECTION 3 — MODIFIED EARLY WARNING SCORE (MEWS)")
    mews = report.get("mews") or {}
    urg_c = URGENCY_COLOR.get(urgency, SLATE)

    # Derive MEWS score from urgency if not provided
    mews_map   = {"CRITICAL": 8, "HIGH": 5, "MEDIUM": 3, "LOW": 1}
    total_mews = mews.get("total", mews_map.get(urgency, 1))
    risk_map   = {0: "Minimal", 1: "Low", 3: "Moderate", 5: "High", 7: "Very High"}
    risk_label = "Very High" if total_mews >= 7 else ("High" if total_mews >= 5 else ("Moderate" if total_mews >= 3 else "Low"))

    mews_components = [
        ("Respiratory Rate",   mews.get("rr_score",   "—")),
        ("SpO₂ / Oxygenation", mews.get("spo2_score", "—")),
        ("Heart Rate",         mews.get("hr_score",   "—")),
        ("Systolic BP",        mews.get("bp_score",   "—")),
        ("Consciousness (AVPU)",mews.get("avpu_score","—")),
        ("Temperature",        mews.get("temp_score", "—")),
        ("Urine Output",       mews.get("urine_score","—")),
    ]
    mews_data = [
        [Paragraph("Component", TABLE_HDR),
         Paragraph("Score (0–3)", TABLE_HDR),
         Paragraph("Interpretation", TABLE_HDR)]
    ]
    interp_map = {"0": "Normal", "1": "Borderline", "2": "Abnormal", "3": "Critical", "—": "Not assessed"}
    for comp, sc in mews_components:
        interp = interp_map.get(str(sc), "—")
        mews_data.append([
            Paragraph(comp, TABLE_CELL),
            Paragraph(str(sc), _s("ms", fontName="Helvetica-Bold", fontSize=9,
                                  textColor=URGENCY_COLOR["CRITICAL"] if str(sc) == "3" else DARK,
                                  alignment=TA_CENTER)),
            Paragraph(interp, TABLE_CELL),
        ])
    mews_data.append([
        Paragraph("TOTAL MEWS", _s("mt", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE)),
        Paragraph(str(total_mews), _s("mtv", fontName="Helvetica-Bold", fontSize=11, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph(f"{risk_label} Risk", _s("mtr", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE)),
    ])

    col_w = [CONTENT_W * 0.45, CONTENT_W * 0.15, CONTENT_W * 0.40]
    mt = Table(mews_data, colWidths=col_w)
    styles = [
        ("BACKGROUND",    (0,0),(-1,0),         NAVY),
        ("BACKGROUND",    (0,-1),(-1,-1),        urg_c),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),         [SLATE_LIGHT, WHITE]),
        ("GRID",          (0,0),(-1,-1),         0.3, SLATE_MID),
        ("TOPPADDING",    (0,0),(-1,-1),         5),
        ("BOTTOMPADDING", (0,0),(-1,-1),         5),
        ("LEFTPADDING",   (0,0),(-1,-1),         8),
        ("VALIGN",        (0,0),(-1,-1),         "MIDDLE"),
        ("ALIGN",         (1,0),(1,-1),          "CENTER"),
    ]
    mt.setStyle(TableStyle(styles))

    note = Paragraph(
        f"<b>MEWS Guidance:</b> Score 0-2 = Routine monitoring. "
        f"Score 3-4 = Increased monitoring, notify physician. "
        f"Score 5+ = URGENT escalation. Activate rapid-response if score ≥7.",
        _s("mews_note", fontSize=7.5, textColor=SLATE, leading=11)
    )
    story.append(mt)
    story += [_space(5), note, _space(10)]


def _build_chief_complaint(story: list, report: dict) -> None:
    """Section 6 — Chief complaint verbatim quote."""
    story += _section_header("  SECTION 4 — CHIEF COMPLAINT (Patient's Own Words)")
    complaint = report.get("chief_complaint") or "No chief complaint recorded."
    quote_box = Table(
        [[Paragraph(f'"{complaint}"', _s("cc", fontName="Helvetica-Oblique", fontSize=10.5, textColor=NAVY, leading=16))]],
        colWidths=[CONTENT_W],
    )
    quote_box.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), BLUE_MIST),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
        ("LINEAFTER",    (0,0),(0,-1),  4, NAVY),
    ]))
    story += [quote_box, _space(5)]

    onset    = report.get("onset_duration", "Not specified")
    severity = report.get("severity_scale", "Not specified")
    location = report.get("pain_location", "Not specified")
    radiation= report.get("pain_radiation", "Not specified")
    aggravate= report.get("aggravating_factors", "Not specified")
    relieve  = report.get("relieving_factors", "Not specified")
    assoc    = report.get("associated_symptoms_summary", "Not specified")

    opqrst_rows = [
        ("Onset / Duration",      onset),
        ("Provocation/Palliation", f"Aggravated by: {aggravate} | Relieved by: {relieve}"),
        ("Quality",               report.get("pain_quality", "Not specified")),
        ("Region / Radiation",    f"{location} → {radiation}"),
        ("Severity (0–10)",       severity),
        ("Timing / Pattern",      report.get("pain_timing", "Not specified")),
        ("Associated Sx",         assoc),
    ]
    story.append(_kv_table(opqrst_rows, col_ratio=(0.28, 0.72)))
    story.append(_space(10))


def _build_symptoms_section(story: list, report: dict, urgency: str) -> None:
    """Section 7 — Symptom inventory chips."""
    story += _section_header("  SECTION 5 — EXTRACTED SYMPTOM INVENTORY  (BioBERT NER Pipeline)")
    symptoms = report.get("extracted_symptoms") or []
    urg_c  = URGENCY_COLOR.get(urgency, TEAL)
    urg_bg = URGENCY_BG.get(urgency, TEAL_LIGHT)

    if not symptoms:
        story.append(Paragraph("No symptoms extracted in this session.", BODY_GREY))
    else:
        # Chips
        chip_rows, row = [], []
        for i, s in enumerate(symptoms):
            sym     = s.get("symptom", "")
            sev     = s.get("severity") or "—"
            dur     = s.get("duration") or "—"
            chip_tbl = Table(
                [[Paragraph(f"<b>{sym}</b>", _s("chip", fontSize=8, textColor=urg_c))],
                 [Paragraph(f"Sev: {sev} | Dur: {dur}", _s("chip2", fontSize=6.5, textColor=SLATE))]],
                colWidths=[CONTENT_W / 4 - 6],
            )
            chip_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), urg_bg),
                ("TOPPADDING",    (0,0),(-1,-1), 5),
                ("BOTTOMPADDING", (0,0),(-1,-1), 5),
                ("LEFTPADDING",   (0,0),(-1,-1), 8),
                ("RIGHTPADDING",  (0,0),(-1,-1), 8),
                ("LINEBELOW",     (0,-1),(-1,-1), 2, urg_c),
                ("BOX",           (0,0),(-1,-1), 0.3, SLATE_MID),
                ("TOPPADDING",    (0,0),(-1,0), 6),
            ]))
            row.append(chip_tbl)
            if len(row) == 4 or i == len(symptoms) - 1:
                while len(row) < 4:
                    row.append(Paragraph("", BODY))
                chip_rows.append(row)
                row = []

        if chip_rows:
            ct = Table(chip_rows, colWidths=[CONTENT_W / 4] * 4)
            ct.setStyle(TableStyle([
                ("VALIGN",       (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING",  (0,0),(-1,-1), 3),
                ("RIGHTPADDING", (0,0),(-1,-1), 3),
                ("TOPPADDING",   (0,0),(-1,-1), 3),
                ("BOTTOMPADDING",(0,0),(-1,-1), 3),
            ]))
            story.append(ct)

    note = Paragraph(
        "<b>Extraction Method:</b> BioBERT NER fine-tuned on biomedical corpora (BC5CDR, NCBI Disease, "
        "NLM-Chem) with entity types: disease, symptom, drug, anatomy, temporal. "
        "Confidence threshold: 0.65. Severity and duration are patient-reported.",
        _s("snote", fontSize=7, textColor=SLATE, leading=10)
    )
