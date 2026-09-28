"""Small, dependency-free PDF drawing toolkit built on fpdf2's own primitives - tables,
key/value blocks, and hand-drawn bar charts, shared by every SATRIA report section."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fpdf import FPDF

# ponytail: hand-drawn bar charts via fpdf2 primitives instead of pulling in matplotlib -
# this report only ever needs bars, and fpdf2 is already a dependency.
INK = (23, 35, 31)
MUTED = (100, 115, 109)
LINE = (216, 222, 217)
SELAT = (23, 102, 106)
OKSIDA = (155, 61, 54)
PERUNGGU = (167, 123, 69)
HEADER_BG = INK
ROW_ALT_BG = (244, 245, 242)


def _severity_color(severity: str) -> tuple[int, int, int]:
    return {"CRITICAL": OKSIDA, "HIGH": PERUNGGU}.get(severity, MUTED)


_ASCII_REPLACEMENTS = {
    "–": "-", "—": "-", "−": "-",  # en/em dash, minus sign
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...",
    "≥": ">=", "≤": "<=",
}


def _text(value: Any) -> str:
    """ASCII-safe string for the core Helvetica font (no em-dash/ellipsis/curly quotes/>=)."""
    if value is None:
        return "-"
    text = str(value)
    for source, target in _ASCII_REPLACEMENTS.items():
        if source in text:
            text = text.replace(source, target)
    return text


def _fmt(value: Any, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _fit(pdf: "FPDF", text: str, width: float) -> str:
    text = _text(text)
    if pdf.get_string_width(text) <= width - 2:
        return text
    while text and pdf.get_string_width(text + "...") > width - 2:
        text = text[:-1]
    return f"{text}..." if text else ""


def _ensure_space(pdf: "FPDF", height: float) -> bool:
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()
        return True
    return False


def _content_width(pdf: "FPDF") -> float:
    return pdf.w - pdf.l_margin - pdf.r_margin


def _section_title(pdf: "FPDF", text: str) -> None:
    _ensure_space(pdf, 16)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, _text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + _content_width(pdf), pdf.get_y())
    pdf.ln(3)


def _subheading(pdf: "FPDF", text: str) -> None:
    _ensure_space(pdf, 9)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*SELAT)
    pdf.cell(0, 7, _text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)


def _note(pdf: "FPDF", text: str) -> None:
    _ensure_space(pdf, 6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5.5, _text(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(1)


def _kv_table(pdf: "FPDF", rows: list[tuple[str, Any]], col1: float = 78) -> None:
    for label, value in rows:
        _ensure_space(pdf, 6)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(col1, 6, _text(label))
        pdf.set_text_color(*INK)
        pdf.multi_cell(_content_width(pdf) - col1, 6, _text(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _table(pdf: "FPDF", headers: list[str], rows: list[list[Any]], widths: list[float]) -> None:
    def draw_header() -> None:
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_text_color(255, 255, 255)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, _fit(pdf, header, width), fill=True)
        pdf.ln(7)
        pdf.set_text_color(*INK)

    if not rows:
        _note(pdf, "Tidak ada baris untuk ditampilkan.")
        return

    _ensure_space(pdf, 7)
    draw_header()
    pdf.set_font("Helvetica", "", 8)
    for index, row in enumerate(rows):
        if _ensure_space(pdf, 6):
            draw_header()
            pdf.set_font("Helvetica", "", 8)
        fill = index % 2 == 1
        if fill:
            pdf.set_fill_color(*ROW_ALT_BG)
        for value, width in zip(row, widths):
            pdf.cell(width, 6, _fit(pdf, value, width), fill=fill)
        pdf.ln(6)
    pdf.ln(3)


def _vbar_chart(pdf: "FPDF", data: list[tuple[str, float]], *, height: float = 40, color=SELAT) -> None:
    if not data:
        _note(pdf, "Tidak ada data untuk divisualisasikan.")
        return
    _ensure_space(pdf, height + 16)
    x0, y0 = pdf.l_margin, pdf.get_y()
    width = _content_width(pdf)
    gap = 3.0
    count = len(data)
    bar_w = (width - gap * (count - 1)) / count
    max_value = max((value for _, value in data), default=0) or 1
    pdf.set_draw_color(*LINE)
    pdf.line(x0, y0 + height, x0 + width, y0 + height)
    for index, (label, value) in enumerate(data):
        bar_x = x0 + index * (bar_w + gap)
        bar_h = (value / max_value) * (height - 10) if max_value else 0
        pdf.set_fill_color(*color)
        pdf.rect(bar_x, y0 + height - bar_h, bar_w, max(bar_h, 0.4), "F")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*INK)
        pdf.set_xy(bar_x - 3, y0 + height - bar_h - 5)
        pdf.cell(bar_w + 6, 4, _fmt(value, 0) if float(value).is_integer() else _fmt(value), align="C")
        pdf.set_text_color(*MUTED)
        pdf.set_xy(bar_x - 3, y0 + height + 1.5)
        pdf.cell(bar_w + 6, 4, _fit(pdf, label, bar_w + 6), align="C")
    pdf.set_xy(x0, y0 + height + 8)
    pdf.set_text_color(*INK)


def _hbar_chart(
    pdf: "FPDF",
    data: list[tuple[str, float, tuple[int, int, int]]],
    *,
    label_w: float = 62,
    value_w: float = 22,
    bar_h: float = 5.4,
    row_gap: float = 2.2,
    value_fmt=lambda value: _fmt(value),
) -> None:
    if not data:
        _note(pdf, "Tidak ada data untuk divisualisasikan.")
        return
    content_w = _content_width(pdf)
    bar_max = content_w - label_w - value_w
    max_value = max((value for _, value, _ in data), default=0) or 1
    for label, value, color in data:
        _ensure_space(pdf, bar_h + row_gap)
        x0, y0 = pdf.l_margin, pdf.get_y()
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*INK)
        pdf.set_xy(x0, y0)
        pdf.cell(label_w, bar_h, _fit(pdf, label, label_w))
        bar_len = max((value / max_value) * bar_max, 0.6) if max_value else 0.6
        pdf.set_fill_color(*color)
        pdf.rect(x0 + label_w, y0 + 0.5, bar_len, bar_h - 1, "F")
        pdf.set_xy(x0 + label_w + bar_max + 2, y0)
        pdf.set_text_color(*MUTED)
        pdf.cell(value_w, bar_h, value_fmt(value))
        pdf.set_xy(x0, y0 + bar_h + row_gap)
    pdf.set_text_color(*INK)
    pdf.ln(2)
