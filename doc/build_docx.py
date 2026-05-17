"""Convert doc/35_FINAL_REPORT.md to docx with the report's style spec.

Spec:
- Margins: 0.5 in on all four sides
- Body font: Times New Roman, 10 pt
- Section / subsection headings: Times New Roman, 12 pt
- Document title: Times New Roman, 16 pt
- All tables get full single-line borders
- Code blocks keep monospace (Consolas / Courier) at 9 pt for ASCII layout

Run: python doc/build_docx.py
"""
from pathlib import Path

import pypandoc
from docx import Document
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOC_DIR = Path(__file__).resolve().parent
MD_PATH = DOC_DIR / "35_FINAL_REPORT.md"
DOCX_PATH = DOC_DIR / "35_FINAL_REPORT.docx"

BODY_FONT = "Times New Roman"
CODE_FONT = "Consolas"

CODE_STYLE_NAMES = {"Source Code", "Verbatim Char", "Code", "macro"}


def _set_run_font(run_element, font_name):
    """Force <w:rFonts> attributes for ascii/hAnsi/cs/eastAsia on an rPr element."""
    rFonts = run_element.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        run_element.append(rFonts)
    for k in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(k), font_name)


def _style_set(doc, style_name, font_name, size_pt, bold=None):
    if style_name not in [s.name for s in doc.styles]:
        return
    style = doc.styles[style_name]
    style.font.name = font_name
    style.font.size = Pt(size_pt)
    if bold is not None:
        style.font.bold = bold
    rPr = style.element.get_or_add_rPr()
    _set_run_font(rPr, font_name)


def _is_code_paragraph(paragraph):
    return paragraph.style.name in CODE_STYLE_NAMES


def _force_run_font(run, font_name, size_pt):
    """Override any run-level font / size from pandoc."""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    rPr = run._element.get_or_add_rPr()
    _set_run_font(rPr, font_name)
    # explicit <w:sz> values for half-points
    for tag in ("w:sz", "w:szCs"):
        existing = rPr.find(qn(tag))
        if existing is not None:
            rPr.remove(existing)
        sz = OxmlElement(tag)
        sz.set(qn("w:val"), str(int(size_pt * 2)))
        rPr.append(sz)


def _add_table_borders(table, color="auto", size_eighths_of_point=4):
    tbl = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    tblBorders = OxmlElement("w:tblBorders")
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{name}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(size_eighths_of_point))
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), color)
        tblBorders.append(b)
    tblPr.append(tblBorders)


def _walk_paragraph_runs(paragraph):
    yield from paragraph.runs


def _apply_fonts(doc):
    # 1. style-level defaults (cascade to most paragraphs)
    _style_set(doc, "Normal", BODY_FONT, 10)
    _style_set(doc, "Title", BODY_FONT, 16, bold=True)
    _style_set(doc, "Heading 1", BODY_FONT, 14, bold=True)
    _style_set(doc, "Heading 2", BODY_FONT, 12, bold=True)
    _style_set(doc, "Heading 3", BODY_FONT, 12, bold=True)
    _style_set(doc, "Heading 4", BODY_FONT, 11, bold=True)
    _style_set(doc, "Heading 5", BODY_FONT, 11, bold=True)
    _style_set(doc, "Heading 6", BODY_FONT, 10, bold=True)
    _style_set(doc, "Compact", BODY_FONT, 10)
    _style_set(doc, "First Paragraph", BODY_FONT, 10)
    _style_set(doc, "Body Text", BODY_FONT, 10)
    _style_set(doc, "Caption", BODY_FONT, 9)
    _style_set(doc, "Image Caption", BODY_FONT, 9)
    # code blocks: keep monospace, drop to 9 pt for ASCII layout fit
    _style_set(doc, "Source Code", CODE_FONT, 9)
    _style_set(doc, "Verbatim Char", CODE_FONT, 9)

    # 2. run-level pass — pandoc emits explicit <w:rFonts> on every run, which
    # would otherwise override the style.  walk every paragraph and re-stamp.
    for paragraph in doc.paragraphs:
        is_code = _is_code_paragraph(paragraph)
        font = CODE_FONT if is_code else BODY_FONT
        # paragraph style determines the size; here we just enforce the font.
        # for body paragraphs we also enforce 10 pt unless the paragraph is a
        # heading style (which keeps its own size from the style cascade).
        style_name = paragraph.style.name
        if style_name.startswith("Heading"):
            # let the style's font.size take effect by clearing run-level size
            for run in _walk_paragraph_runs(paragraph):
                run.font.name = font
                rPr = run._element.get_or_add_rPr()
                _set_run_font(rPr, font)
                # remove explicit size (let style handle it)
                for tag in ("w:sz", "w:szCs"):
                    existing = rPr.find(qn(tag))
                    if existing is not None:
                        rPr.remove(existing)
        else:
            size = 9 if is_code else 10
            for run in _walk_paragraph_runs(paragraph):
                _force_run_font(run, font, size)

    # 3. tables — same pass, but also include caption-style cells
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    is_code = _is_code_paragraph(paragraph)
                    font = CODE_FONT if is_code else BODY_FONT
                    size = 9 if is_code else 10
                    for run in _walk_paragraph_runs(paragraph):
                        _force_run_font(run, font, size)


def convert():
    print(f"[1/3] pandoc {MD_PATH.name} -> {DOCX_PATH.name}")
    pypandoc.convert_file(
        str(MD_PATH),
        "docx",
        outputfile=str(DOCX_PATH),
        extra_args=[
            "--standalone",
            "--from=markdown+fenced_code_blocks+pipe_tables+backtick_code_blocks",
            f"--resource-path={DOC_DIR}",
        ],
    )

    print("[2/3] python-docx: 0.5-in margins")
    doc = Document(str(DOCX_PATH))
    for section in doc.sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    print("[3/3] python-docx: TNR 10/12pt fonts + table borders")
    _apply_fonts(doc)
    for table in doc.tables:
        _add_table_borders(table)

    doc.save(str(DOCX_PATH))
    size_mb = DOCX_PATH.stat().st_size / (1024 * 1024)
    print(f"done: {DOCX_PATH}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    convert()
