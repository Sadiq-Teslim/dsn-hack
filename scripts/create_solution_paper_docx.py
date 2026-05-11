from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "BCT_Solution_Paper.docx"

ACCENT = RGBColor(36, 89, 77)
BURGUNDY = RGBColor(127, 29, 45)
MUTED = RGBColor(95, 91, 83)
LIGHT_FILL = "F7F1E8"
HEADER_FILL = "EDE3D3"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width_inches: float) -> None:
    cell.width = Inches(width_inches)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_inches * 1440)))
    tc_w.set(qn("w:type"), "dxa")


def set_cell_margins(cell, top=90, start=120, bottom=90, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.append(OxmlElement("w:cantSplit"))


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = tr_pr.find(qn("w:tblHeader"))
    if tbl_header is None:
        tbl_header = OxmlElement("w:tblHeader")
        tr_pr.append(tbl_header)
    tbl_header.set(qn("w:val"), "true")


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Page ")
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.8)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.space_after = Pt(6)

    for style_name, size, color in [
        ("Title", 22, BURGUNDY),
        ("Subtitle", 12, MUTED),
        ("Heading 1", 16, ACCENT),
        ("Heading 2", 13, BURGUNDY),
        ("Heading 3", 11.5, ACCENT),
    ]:
        style = styles[style_name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = style_name != "Subtitle"
        style.font.color.rgb = color

    styles["Heading 1"].paragraph_format.space_before = Pt(12)
    styles["Heading 1"].paragraph_format.space_after = Pt(6)
    styles["Heading 2"].paragraph_format.space_before = Pt(9)
    styles["Heading 2"].paragraph_format.space_after = Pt(4)


def add_running_header_footer(document: Document) -> None:
    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = "DSN x BCT LLM Agent Challenge | Solution Paper"
    paragraph.style = document.styles["Normal"]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in paragraph.runs:
        run.font.size = Pt(8.5)
        run.font.color.rgb = MUTED

    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "CFC1AD")
    border.append(bottom)
    paragraph._p.get_or_add_pPr().append(border)

    add_page_number(section.footer.paragraphs[0])


def add_metadata_table(document: Document) -> None:
    table = document.add_table(rows=3, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    rows = [
        ("Competition", "Data & AI Summit Hackathon 3.0: DSN x BCT LLM Agent Challenge"),
        ("System", "Containerized FastAPI application with web UI, REST API, and Groq-backed generation"),
        ("Dataset Strategy", "Amazon Reviews 2023 subset: Grocery, Movies & TV, Video Games, and Beauty"),
    ]
    for row, (label, value) in zip(table.rows, rows, strict=True):
        row.cells[0].text = label
        row.cells[1].text = value
        for index, cell in enumerate(row.cells):
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_width(cell, 2.0 if index == 0 else 4.5)
            set_cell_margins(cell)
            if index == 0:
                set_cell_shading(cell, HEADER_FILL)
                cell.paragraphs[0].runs[0].font.bold = True
            else:
                set_cell_shading(cell, "FFFFFF")


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_repeat_table_header(table.rows[0])
    set_row_cant_split(table.rows[0])
    for idx, header in enumerate(headers):
        cell = table.rows[0].cells[idx]
        cell.text = header
        set_cell_width(cell, widths[idx])
        set_cell_shading(cell, HEADER_FILL)
        set_cell_margins(cell)
        cell.paragraphs[0].runs[0].font.bold = True
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for row_values in rows:
        row = table.add_row()
        set_row_cant_split(row)
        for idx, value in enumerate(row_values):
            cell = row.cells[idx]
            cell.text = value
            set_cell_width(cell, widths[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.add_run(item)


def add_numbered(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.add_run(item)


def build_document() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    configure_styles(document)
    add_running_header_footer(document)

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Dynamic User Modeling and Contextual Recommendation with LLM Agents")

    subtitle = document.add_paragraph(style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Solution paper for the DSN x BCT LLM Agent Challenge")

    add_metadata_table(document)

    document.add_heading("Executive Summary", level=1)
    document.add_paragraph(
        "The system models users as dynamic behavioral agents rather than static profiles. "
        "It combines local, reproducible scoring with retrieval-augmented Groq generation so the "
        "submission can be evaluated by machines, inspected by judges, and still run when no API key "
        "is supplied. One container exposes both required tasks: simulated reviews and personalized "
        "recommendations."
    )
    add_bullets(
        document,
        [
            "Task A predicts a star rating from user bias, category affinity, item quality, keyword fit, and budget sensitivity, then generates a grounded review.",
            "Task B ranks products across grocery, movies, games, and beauty using popularity, preference match, context match, category affinity, and cold-start fallbacks.",
            "Nigerian context is represented through persona fields such as location, budget, language preference, family use cases, weekday routines, harmattan weather, and local media taste.",
        ],
    )

    document.add_heading("1. Problem Framing", level=1)
    document.add_paragraph(
        "Online reviews are compact records of behavior: users reveal what they value, how harshly "
        "they rate products, which tradeoffs matter, and how context changes their choices. The "
        "challenge is therefore not only to summarize past activity, but to simulate how a person "
        "would react to an unseen item and what they are likely to choose next."
    )
    document.add_paragraph(
        "Our design treats the persona as the shared memory object between both tasks. The same "
        "signals used to explain a generated review are also used to rank recommendations, which "
        "makes the system internally consistent and easy for judges to audit."
    )

    document.add_heading("2. Architecture", level=1)
    add_table(
        document,
        ["Layer", "Role", "Implementation"],
        [
            ["Persona modeling", "Compress user history into behavior signals", "Rating bias, category affinity, likes/dislikes, budget level, tone, and Nigerian context fields"],
            ["Retrieval", "Ground generation in prior behavior", "Nearest history items by category and keyword overlap"],
            ["Rating model", "Predict Task A stars", "Weighted ensemble of item quality, user average, category affinity, preference overlap, dislike overlap, and budget adjustment"],
            ["Recommender", "Rank Task B candidates", "Popularity, volume, category affinity, context match, preference match, dislike penalty, and budget fit"],
            ["Generation", "Produce natural language", "Groq chat completions for final review/explanation, deterministic local fallback for reproducibility"],
        ],
        [1.4, 2.0, 3.1],
    )
    document.add_paragraph(
        "The Groq layer is deliberately separated from the ranking and rating logic. This prevents "
        "the LLM from becoming an opaque scoring engine and keeps the metrics reproducible. Groq "
        "improves fluency and explanation quality, while local models determine the behavioral "
        "decision."
    )

    document.add_page_break()
    document.add_heading("3. Dataset and Splitting Strategy", level=1)
    document.add_paragraph(
        "The competition plan uses Amazon Reviews 2023 because it provides item metadata, review "
        "text, ratings, user histories, and multiple product domains. The repository ships with a "
        "small Amazon-style fixture dataset so evaluators can run the app instantly. The same schema "
        "is used for larger sampled categories."
    )
    add_bullets(
        document,
        [
            "Primary domains: Grocery and Gourmet Food, Movies and TV, Video Games, and All Beauty.",
            "Train/test construction: hold out each user's most recent interaction where enough history exists.",
            "Cold-start support: when history is sparse, rely more heavily on item metadata, popularity, context text, and stated persona preferences.",
        ],
    )

    document.add_heading("4. Experiments and Ablations", level=1)
    add_table(
        document,
        ["Experiment", "Purpose", "Expected Signal"],
        [
            ["Item-average baseline", "Measure whether personalization improves rating prediction", "Lower RMSE from persona and category features"],
            ["Popularity-only ranking", "Benchmark non-personalized recommendation quality", "Higher NDCG@10 when persona/context features are enabled"],
            ["No retrieval evidence", "Test whether grounding improves review fidelity", "Lower qualitative fidelity and weaker review specificity"],
            ["No Groq generation", "Separate language quality from behavioral scoring", "Metrics remain runnable; human readability drops"],
            ["Cold-start personas", "Validate behavior with little/no history", "Reasonable rankings from metadata and stated preferences"],
        ],
        [1.7, 2.4, 2.4],
    )

    document.add_page_break()
    document.add_heading("5. Current Fixture Results", level=1)
    document.add_paragraph(
        "The checked-in fixture split is intentionally small and should be interpreted as a smoke "
        "test, not a final leaderboard score. It verifies that the app, endpoints, and evaluation "
        "pipeline are coherent before scaling to the larger Amazon subset."
    )
    add_table(
        document,
        ["Metric", "Fixture Result", "Interpretation"],
        [
            ["Task A RMSE", "0.507", "Rating predictor is stable on the smoke split"],
            ["Task A ROUGE-L", "0.418", "Placeholder fixture score unless optional NLP metrics are installed"],
            ["Task B NDCG@10", "0.810", "Held-out items are ranked near the top"],
            ["Task B Hit Rate@10", "1.000", "Every held-out item appears in the top ten"],
        ],
        [1.8, 1.4, 3.3],
    )

    document.add_heading("6. Nigerian Contextualization", level=1)
    document.add_paragraph(
        "The system includes Nigerian contextual signals without forcing slang or stereotypes. "
        "Location, budget, family role, language preference, weather, transport cost, and local media "
        "taste influence the final output only where they naturally affect value and choice."
    )
    add_table(
        document,
        ["Persona", "Context Signal", "Behavioral Effect"],
        [
            ["Lagos student", "Low budget, classes, friends, transport cost", "Prioritizes quick meals, value, local comedy, and multiplayer entertainment"],
            ["Abuja professional", "Work routine, heat, polished daily use", "Prefers dependable coffee, political drama, and lightweight skincare"],
            ["Port Harcourt family shopper", "Home use, visitors, children, reliability", "Prefers family-safe media, easy drinks for guests, and gentle skincare"],
        ],
        [1.8, 2.3, 2.4],
    )

    document.add_page_break()
    document.add_heading("7. Reproducibility and Deployment", level=1)
    add_numbered(
        document,
        [
            "Run the FastAPI service locally or through Docker Compose; the same container serves the UI and REST API.",
            "Set GROQ_API_KEY to enable hosted generation, or omit it to use deterministic fallback text.",
            "Use /api/v1/generate-review, /api/v1/recommend, /api/v1/evaluation, scripts/evaluate.py, and scripts/build_dataset.py for scoring and larger Amazon subset runs.",
        ],
    )

    document.add_heading("8. Limitations and Next Steps", level=1)
    document.add_paragraph(
        "The current build is optimized for deadline reliability and judge reproducibility. The main "
        "limitation is that the repository includes a small fixture dataset rather than the full "
        "Amazon corpus. With more time, we would add embedding indexes, larger sampled evaluation, "
        "rating calibration, multi-turn conversational memory, and real Nigerian marketplace data."
    )

    # Keep the final section from dangling alone.
    document.add_section(WD_SECTION.CONTINUOUS)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_document()
