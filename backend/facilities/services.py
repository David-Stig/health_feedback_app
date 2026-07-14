from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_WIDTH, PAGE_HEIGHT = A4
TEXT = HexColor("#102A43")
BLACK = HexColor("#000000")
QR_SIZE = 70 * mm


def build_feedback_poster_pdf(facility) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"{facility.name} Feedback Poster")

    qr_reader = _build_qr_reader(facility)

    top_margin = PAGE_HEIGHT - (24 * mm)
    content_width = PAGE_WIDTH - (36 * mm)

    y_position = top_margin
    y_position -= 8 * mm

    y_position = _draw_centered_text(
        pdf,
        "GIVE US YOUR FEEDBACK",
        y_position,
        font_name="Helvetica-Bold",
        font_size=22,
        color=BLACK,
    )
    y_position -= 5 * mm

    y_position = _draw_wrapped_text(
        pdf,
        "Help us improve health services across Zambia by sharing your experience at this health facility.",
        y_position,
        max_width=content_width,
        font_name="Helvetica",
        font_size=12,
        color=BLACK,
        leading=18,
    )
    y_position -= 8 * mm

    y_position = _draw_wrapped_text(
        pdf,
        facility.name,
        y_position,
        max_width=content_width,
        font_name="Helvetica-Bold",
        font_size=18,
        color=BLACK,
        leading=24,
    )
    y_position -= 8 * mm

    y_position = _draw_centered_text(
        pdf,
        "Scan the QR Code",
        y_position,
        font_name="Helvetica-Bold",
        font_size=16,
        color=BLACK,
    )
    y_position -= 10 * mm

    qr_x = (PAGE_WIDTH - QR_SIZE) / 2
    qr_y = y_position - QR_SIZE
    pdf.drawImage(
        qr_reader,
        qr_x,
        qr_y,
        width=QR_SIZE,
        height=QR_SIZE,
        preserveAspectRatio=True,
        mask="auto",
    )
    y_position = qr_y - (8 * mm)

    y_position = _draw_centered_text(
        pdf,
        "Scan to share your feedback securely.",
        y_position,
        font_name="Helvetica",
        font_size=11,
        color=BLACK,
    )

    footer_y = 18 * mm
    pdf.setStrokeColor(BLACK)
    pdf.setLineWidth(1)
    pdf.line(30 * mm, footer_y + (8 * mm), PAGE_WIDTH - (30 * mm), footer_y + (8 * mm))
    _draw_centered_text(
        pdf,
        "MOH – Improving Healthcare Together",
        footer_y + (3 * mm),
        font_name="Helvetica-Bold",
        font_size=11,
        color=BLACK,
    )

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def poster_filename_for_facility(facility) -> str:
    from django.utils.text import slugify

    facility_slug = slugify(facility.name) or f"facility-{facility.pk}"
    return f"{facility_slug}-feedback-poster.pdf"


def _build_qr_reader(facility) -> ImageReader:
    qr_image = facility.build_qr_image().get_image().convert("RGB")
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    return ImageReader(qr_buffer)


def _draw_centered_text(pdf, text, y_position, *, font_name, font_size, color):
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    text_width = stringWidth(text, font_name, font_size)
    pdf.drawString((PAGE_WIDTH - text_width) / 2, y_position, text)
    return y_position - font_size


def _draw_wrapped_text(pdf, text, y_position, *, max_width, font_name, font_size, color, leading):
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(color)
    lines = _wrap_text(text, font_name, font_size, max_width)
    for line in lines:
        text_width = stringWidth(line, font_name, font_size)
        pdf.drawString((PAGE_WIDTH - text_width) / 2, y_position, line)
        y_position -= leading
    return y_position


def _wrap_text(text, font_name, font_size, max_width):
    words = text.split()
    if not words:
        return [""]

    lines = []
    current_line = words[0]
    for word in words[1:]:
        candidate = f"{current_line} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current_line = candidate
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines
