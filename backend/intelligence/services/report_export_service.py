from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from feedback.models import Feedback
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4
BLACK = HexColor("#000000")
TEXT = HexColor("#102A43")
MUTED = HexColor("#52606d")
BORDER = HexColor("#d9e2ec")
TEAL = HexColor("#14746f")
BLUE = HexColor("#2c7da0")
GOLD = HexColor("#f0b429")

RATING_SHORT_LABELS = {
    "Waiting time before being seen": "Waiting Time",
    "Respect and dignity from staff": "Respect & Dignity",
    "Cleanliness of the health facility": "Cleanliness",
    "Explanation of your illness and treatment": "Health Explanation",
    "Availability of Medication": "Medication",
}

CHANGE_SHORT_LABELS = {
    Feedback.CHANGE.MORE_WORKERS: "Health workers",
    Feedback.CHANGE.MORE_MEDICINES: "Medicines",
    Feedback.CHANGE.WAITING_TIME: "Waiting Time",
    Feedback.CHANGE.LOWER_COST: "Lower/No Costs",
    Feedback.CHANGE.STAFF_ATTITUDE: "Staff Attitude",
    Feedback.CHANGE.OPENING_HOURS: "Operating Hours",
    Feedback.CHANGE.OTHER: "Other",
}

INSURANCE_SHORT_LABELS = {
    Feedback.INSURANCE.NHIMA: "NHIMA",
    Feedback.INSURANCE.PRIVATE: "Private",
    Feedback.INSURANCE.BOTH: "Both",
    Feedback.INSURANCE.NONE: "None",
    Feedback.INSURANCE.NOT_SURE: "Not Sure",
    "NHIMA (National Health Insurance)": "NHIMA",
    "Private Insurance": "Private",
    "Both NHIMA and private": "Both",
    "No insurance used": "None",
    "Not sure": "Not Sure",
}


def build_intelligence_report_pdf(report) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=0)
    pdf.setTitle(report.title)

    y = PAGE_HEIGHT - (18 * mm)
    logo_reader = _load_logo_reader()
    if logo_reader:
        logo_width = 42 * mm
        logo_height = 16 * mm
        pdf.drawImage(
            logo_reader,
            (PAGE_WIDTH - logo_width) / 2,
            y - logo_height,
            width=logo_width,
            height=logo_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        y -= 24 * mm

    y = _draw_centered_text(pdf, "CRHE REPORTS", y, font_name="Helvetica-Bold", font_size=18, color=BLACK)
    y -= 2 * mm
    y = _draw_wrapped_centered_text(
        pdf,
        report.title,
        y,
        max_width=PAGE_WIDTH - (34 * mm),
        font_name="Helvetica-Bold",
        font_size=15,
        color=TEXT,
        leading=18,
    )
    y -= 4 * mm
    y = _draw_centered_text(
        pdf,
        f"{report.report_code} | Version {report.version} | {report.get_status_display()}",
        y,
        font_name="Helvetica",
        font_size=10,
        color=MUTED,
    )
    y -= 10 * mm

    info_rows = [
        ("Reporting period", f"{report.period_start:%d %b %Y} to {report.period_end:%d %b %Y}"),
        (
            "Comparison period",
            f"{report.comparison_start:%d %b %Y} to {report.comparison_end:%d %b %Y}"
            if report.comparison_start and report.comparison_end
            else "Not available",
        ),
        ("Facility scope", report.facility.name if report.facility else "All facilities"),
        ("Generated", report.generated_at.strftime("%d %b %Y %H:%M")),
    ]
    y = _draw_info_grid(pdf, info_rows, y)
    y -= 6 * mm

    y = _draw_section_heading(pdf, "Executive Summary", y)
    y = _draw_paragraph(
        pdf,
        report.executive_summary or "No executive summary recorded.",
        y,
        font_name="Helvetica",
        font_size=10,
        color=TEXT,
        leading=14,
    )

    latest_version = report.latest_version
    if latest_version and latest_version.recommendations:
        y -= 4 * mm
        y = _draw_section_heading(pdf, "Draft Recommendations", y)
        for recommendation in latest_version.recommendations[:5]:
            y = _draw_bullet_paragraph(
                pdf,
                f"{recommendation.get('title', '')}: {recommendation.get('detail', '')}",
                y,
            )

    insights = list(report.insights.filter(report_version=latest_version, is_hidden=False)) if latest_version else []
    if insights:
        y -= 4 * mm
        y = _draw_section_heading(pdf, "Key Insights", y)
        chart_payloads = _build_key_insight_chart_payloads(latest_version, insights)
        for chart_payload in chart_payloads:
            required_height = _chart_block_height(chart_payload["labels"])
            if y - required_height < 30 * mm:
                _draw_footer(pdf)
                pdf.showPage()
                y = PAGE_HEIGHT - (22 * mm)
                y = _draw_section_heading(pdf, "Key Insights (continued)", y)
            y = _draw_horizontal_bar_chart(
                pdf,
                chart_payload["title"],
                chart_payload["labels"],
                chart_payload["values"],
                y,
                color=chart_payload["color"],
                value_formatter=chart_payload.get("value_formatter"),
            )
            y -= 3 * mm
        if not chart_payloads:
            y = _draw_paragraph(
                pdf,
                "No chart data was available for the selected report period.",
                y,
                font_name="Helvetica",
                font_size=10,
                color=MUTED,
                leading=14,
            )

    if report.management_comments:
        y -= 4 * mm
        y = _draw_section_heading(pdf, "Management Comments", y)
        y = _draw_paragraph(
            pdf,
            report.management_comments,
            y,
            font_name="Helvetica",
            font_size=10,
            color=TEXT,
            leading=14,
        )

    _draw_footer(pdf)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def report_pdf_filename(report) -> str:
    slug = slugify(report.title) or report.report_code.lower()
    return f"{slug}.pdf"


def _load_logo_reader():
    logo_path = Path(settings.BASE_DIR) / "static" / "images" / "CRHE_logo.png"
    if not logo_path.exists():
        return None
    return ImageReader(str(logo_path))


def _draw_info_grid(pdf, rows, y):
    left = 22 * mm
    right = PAGE_WIDTH - (22 * mm)
    column_gap = 8 * mm
    column_width = ((right - left) - column_gap) / 2
    row_height = 16 * mm

    for index, (label, value) in enumerate(rows):
        row = index // 2
        col = index % 2
        box_x = left + (col * (column_width + column_gap))
        box_y = y - ((row + 1) * row_height)
        pdf.setStrokeColor(BORDER)
        pdf.roundRect(box_x, box_y, column_width, row_height - (2 * mm), 4, stroke=1, fill=0)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(box_x + (4 * mm), box_y + (row_height - 7 * mm), label.upper())
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(box_x + (4 * mm), box_y + (row_height - 12 * mm), str(value))
    return y - ((len(rows) + 1) // 2 * row_height)


def _draw_section_heading(pdf, text, y):
    if y < 40 * mm:
        _draw_footer(pdf)
        pdf.showPage()
        y = PAGE_HEIGHT - (22 * mm)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColor(BLACK)
    pdf.drawString(22 * mm, y, text)
    return y - 7 * mm


def _draw_paragraph(pdf, text, y, *, font_name, font_size, color, leading):
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    width = PAGE_WIDTH - (44 * mm)
    for line in _wrap_text(str(text), font_name, font_size, width):
        if y < 28 * mm:
            _draw_footer(pdf)
            pdf.showPage()
            y = PAGE_HEIGHT - (22 * mm)
            pdf.setFont(font_name, font_size)
            pdf.setFillColor(color)
        pdf.drawString(22 * mm, y, line)
        y -= leading
    return y


def _draw_bullet_paragraph(pdf, text, y):
    bullet_x = 24 * mm
    text_x = 29 * mm
    width = PAGE_WIDTH - (51 * mm)
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(TEXT)
    wrapped_lines = _wrap_text(str(text), "Helvetica", 10, width)
    for index, line in enumerate(wrapped_lines):
        if y < 28 * mm:
            _draw_footer(pdf)
            pdf.showPage()
            y = PAGE_HEIGHT - (22 * mm)
            pdf.setFont("Helvetica", 10)
            pdf.setFillColor(TEXT)
        if index == 0:
            pdf.drawString(bullet_x, y, "-")
        pdf.drawString(text_x, y, line)
        y -= 13
    return y


def _draw_centered_text(pdf, text, y, *, font_name, font_size, color):
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    width = stringWidth(text, font_name, font_size)
    pdf.drawString((PAGE_WIDTH - width) / 2, y, text)
    return y - font_size


def _draw_wrapped_centered_text(pdf, text, y, *, max_width, font_name, font_size, color, leading):
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    for line in _wrap_text(text, font_name, font_size, max_width):
        width = stringWidth(line, font_name, font_size)
        pdf.drawString((PAGE_WIDTH - width) / 2, y, line)
        y -= leading
    return y


def _wrap_text(text, font_name, font_size, max_width):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_footer(pdf):
    footer_y = 14 * mm
    pdf.setStrokeColor(BORDER)
    pdf.line(20 * mm, footer_y + (8 * mm), PAGE_WIDTH - (20 * mm), footer_y + (8 * mm))
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    footer_text = "CRHE internal report export"
    pdf.drawString((PAGE_WIDTH - stringWidth(footer_text, "Helvetica", 9)) / 2, footer_y + (3 * mm), footer_text)


def _build_key_insight_chart_payloads(latest_version, insights):
    if not latest_version:
        return []

    insight_snapshot = latest_version.insight_snapshot or []
    ratings = [
        item for item in insight_snapshot
        if item.get("metric_name") not in {"Submission volume", "Average rating", "Free-text topic"}
        and item.get("current_value") is not None
    ][:5]
    structured_counts = latest_version.supporting_statistics.get("structured_counts", {})
    change_rows = structured_counts.get("change", [])[:5]
    topics = (latest_version.topic_snapshot or [])[:5]

    charts = []
    volume_insight = next((item for item in insight_snapshot if item.get("metric_name") == "Submission volume"), None)
    if volume_insight:
        charts.append(
            {
                "title": "Submission volume comparison",
                "labels": ["Current period", "Comparison period"],
                "values": [
                    float(volume_insight.get("current_value") or 0),
                    float(volume_insight.get("comparison_value") or 0),
                ],
                "color": BLUE,
                "value_formatter": lambda value: f"{int(value)}",
            }
        )
    average_rating_insight = next((item for item in insight_snapshot if item.get("metric_name") == "Average rating"), None)
    if average_rating_insight:
        charts.append(
            {
                "title": "Average rating comparison",
                "labels": ["Current period", "Comparison period"],
                "values": [
                    float(average_rating_insight.get("current_value") or 0),
                    float(average_rating_insight.get("comparison_value") or 0),
                ],
                "color": TEAL,
                "value_formatter": lambda value: f"{value:.1f}",
            }
        )
    if ratings:
        charts.append(
            {
                "title": "Average rating by category",
                "labels": [_shorten_label(item.get("metric_name", "")) for item in ratings],
                "values": [float(item.get("current_value") or 0) for item in ratings],
                "color": TEAL,
                "value_formatter": lambda value: f"{value:.1f}",
            }
        )
    if change_rows:
        charts.append(
            {
                "title": "Top requested changes",
                "labels": [_shorten_label(row.get("change", "Not provided")) for row in change_rows],
                "values": [int(row.get("total", 0)) for row in change_rows],
                "color": GOLD,
                "value_formatter": lambda value: f"{int(value)}",
            }
        )
    if topics:
        charts.append(
            {
                "title": "Top free-text topics",
                "labels": [_shorten_label(topic.get("topic", "")) for topic in topics],
                "values": [int(topic.get("count", 0)) for topic in topics],
                "color": BLUE,
                "value_formatter": lambda value: f"{int(value)}",
            }
        )
    return charts


def _chart_block_height(labels):
    return (12 * mm) + (max(len(labels), 1) * 10 * mm)


def _draw_horizontal_bar_chart(pdf, title, labels, values, y, *, color, value_formatter=None):
    left = 24 * mm
    label_width = 52 * mm
    chart_width = 92 * mm
    row_height = 8 * mm
    bar_height = 4 * mm
    title_gap = 7 * mm
    max_value = max(values) if values else 0

    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(TEXT)
    pdf.drawString(left, y, title)
    y -= title_gap

    if not labels or not values or max_value <= 0:
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(left, y, "No chart data available.")
        return y - 8 * mm

    for label, value in zip(labels, values):
        row_baseline = y - (2 * mm)
        bar_y = row_baseline - (bar_height / 2)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(TEXT)
        pdf.drawString(left, row_baseline, label)
        pdf.setStrokeColor(BORDER)
        pdf.setFillColor(BORDER)
        pdf.roundRect(left + label_width, bar_y, chart_width, bar_height, 2, stroke=0, fill=1)
        fill_width = chart_width * (float(value) / float(max_value)) if max_value else 0
        pdf.setFillColor(color)
        pdf.roundRect(left + label_width, bar_y, fill_width, bar_height, 2, stroke=0, fill=1)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 8)
        rendered_value = value_formatter(value) if callable(value_formatter) else str(value)
        pdf.drawRightString(left + label_width + chart_width + (18 * mm), row_baseline, rendered_value)
        y -= row_height
    return y - 2 * mm


def _shorten_label(value):
    raw_value = str(value or "").strip()
    label = (
        RATING_SHORT_LABELS.get(raw_value)
        or CHANGE_SHORT_LABELS.get(raw_value)
        or INSURANCE_SHORT_LABELS.get(raw_value)
        or raw_value.replace("NHIMA (National Health Insurance)", "NHIMA")
    )
    if len(label) <= 28:
        return label
    return f"{label[:25].rstrip()}..."
