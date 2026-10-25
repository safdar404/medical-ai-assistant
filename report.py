"""PDF guidance report (bonus) built with ReportLab.

ReportLab's built-in fonts cover Latin-script languages only (it cannot shape
Urdu/Arabic or render Hindi/Chinese without extra fonts), so the app offers the
PDF for Latin-script answers and a Markdown report for every language.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

from .config import APP_NAME, DISCLAIMER, EMERGENCY_NUMBERS, URGENCY_INFO

INK = colors.HexColor("#0F2A3D")
MUTED = colors.HexColor("#566573")


def _para(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text or ""))


def build_pdf_report(patient: dict, assessment: dict | None, final_urgency: str | None,
                     safety_reasons: list[str], narrative: str | None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=f"{APP_NAME} guidance report")
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], alignment=0, textColor=INK, fontSize=19)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], textColor=INK, fontSize=12.5, spaceBefore=9, spaceAfter=3)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11, textColor=MUTED)

    def box(text: str, fill: str, edge: str) -> Table:
        return Table([[Paragraph(text, small if fill == "#FFF4E5" else body)]], colWidths=[doc.width],
                     style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fill)),
                            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(edge)),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])

    story = [Paragraph(f"{APP_NAME} — guidance report", h1),
             Paragraph(f"Generated {datetime.now():%d %B %Y, %H:%M}", small), Spacer(1, 6),
             box(f"<b>Educational only — not a diagnosis.</b> {escape(DISCLAIMER)}", "#FFF4E5", "#E0A84F")]
    if final_urgency:
        info = URGENCY_INFO[final_urgency]
        story += [Spacer(1, 8), box(f"<b>Urgency level: {final_urgency}.</b> {escape(info['meaning'])}"
                                    + (f"<br/>Emergency numbers: {escape(EMERGENCY_NUMBERS)}"
                                       if final_urgency == "EMERGENCY" else ""),
                                    "#FFFFFF", info["colour"])]
        for reason in safety_reasons:
            story.append(Paragraph(f"• {escape(reason)}", small))

    story.append(Paragraph("Patient information", h2))
    story.append(Table([[k, Paragraph(escape(str(v)), body)] for k, v in patient.items()],
                       colWidths=[doc.width * 0.28, doc.width * 0.72],
                       style=[("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E1E8"))]))
    if assessment:
        story += [Paragraph("Summary", h2), Paragraph(_para(assessment["summary"]), body),
                  Paragraph("Possible conditions — for education only, not a diagnosis", h2)]
        story += [Paragraph(f"<b>{escape(c['name'])}</b> — {_para(c['reason'])}", body)
                  for c in assessment["possible_conditions"]]
        for title, key in [("Recommended next steps", "recommended_next_steps"),
                           ("Questions for your doctor", "questions_for_doctor"),
                           ("Warning signs — get help immediately", "warning_signs")]:
            story.append(Paragraph(title, h2))
            story += [Paragraph(f"{i}. {_para(x)}", body) for i, x in enumerate(assessment[key], 1)]
    if narrative:
        story.append(Paragraph("Guidance", h2))
        story += [Paragraph(_para(re.sub(r"^#+\s*|^[-*]\s+", "", p.strip())), body)
                  for p in narrative.split("\n") if p.strip()]
    story += [Spacer(1, 10), Paragraph(escape(DISCLAIMER), small)]
    doc.build(story)
    return buffer.getvalue()
