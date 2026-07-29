from fpdf import FPDF


def text_to_pdf_bytes(text: str, title: str = "") -> bytes:
    """Renders plain text to a simple single-column PDF (letter body only —
    no attempt at CV-grade layout, see cv.pdf which is Clara's own untouched
    file). cp1252 rather than the default latin-1 core-font encoding — plain
    latin-1 can't represent em-dashes/curly quotes that show up routinely in
    generated French prose, cp1252 (a superset) can, without needing to bundle
    a Unicode TTF font just for this.
    """
    pdf = FPDF()
    pdf.core_fonts_encoding = "cp1252"
    pdf.add_page()

    if title:
        pdf.set_font("Helvetica", style="B", size=13)
        pdf.multi_cell(0, 8, title)
        pdf.ln(4)

    pdf.set_font("Helvetica", size=11)
    for paragraph in text.split("\n"):
        pdf.multi_cell(0, 6, paragraph)
        pdf.ln(2)

    return bytes(pdf.output())
