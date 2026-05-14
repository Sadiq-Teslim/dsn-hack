from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BLACK = RGBColor(0, 0, 0)
HEADER_FILL = "E6E6E6"


def set_cell_width(cell, width_inches: float) -> None:
    cell.width = Inches(width_inches)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_inches * 1440)))
    tc_w.set(qn("w:type"), "dxa")


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, start=100, bottom=70, end=100) -> None:
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


def configure(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    styles = document.styles
    for name, size, bold in [
        ("Normal", 9.5, False),
        ("Title", 21, True),
        ("Subtitle", 11, False),
        ("Heading 1", 14, True),
        ("Heading 2", 12, True),
    ]:
        style = styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = BLACK
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.0


def add_header_footer(document: Document, label: str) -> None:
    section = document.sections[0]
    header = section.header.paragraphs[0]
    header.text = label
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in header.runs:
        run.font.size = Pt(8.5)
        run.font.color.rgb = BLACK
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("Team Ace | DSN x BCT LLM Agent Challenge")
    run.font.size = Pt(8.5)
    run.font.color.rgb = BLACK


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = header
        set_cell_width(cell, widths[index])
        set_cell_shading(cell, HEADER_FILL)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell.paragraphs[0].runs[0].font.bold = True
    for row_values in rows:
        row = table.add_row()
        for index, value in enumerate(row_values):
            cell = row.cells[index]
            cell.text = value
            set_cell_width(cell, widths[index])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2.5)
        paragraph.add_run(item)


def cover(document: Document, title: str, subtitle: str) -> None:
    for _ in range(5):
        document.add_paragraph()
    paragraph = document.add_paragraph(style="Title")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run(title)
    paragraph = document.add_paragraph(style="Subtitle")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run(subtitle)
    for line in [
        "Team Ace",
        "Teslim Sadiq | Yasir Oyebo | Abiodun Mark",
        "Contact: sadiqadetola08@gmail.com",
        "Data & AI Summit Hackathon 3.0",
        "May 2026",
    ]:
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(line)
        run.font.size = Pt(11)
        run.font.color.rgb = BLACK


def enforce_black(document: Document) -> None:
    parts = [document]
    for section in document.sections:
        parts.extend([section.header, section.footer])
    for part in parts:
        for paragraph in part.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = BLACK
        for table in part.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.color.rgb = BLACK


def build_task_a() -> Path:
    path = DOCS / "Task_A_User_Modeling_Team_Ace.docx"
    document = Document()
    configure(document)
    add_header_footer(document, "Task A: User Modeling | Team Ace")
    cover(
        document,
        "Task A: Dynamic User Modeling",
        "Simulating realistic ratings and grounded reviews with auditable LLM agents",
    )
    document.add_page_break()

    document.add_heading("Executive Summary", level=1)
    document.add_paragraph(
        "Task A asks the system to understand a user deeply enough to simulate how they would rate "
        "and review an unseen item. Team Ace solves this with a dynamic behavioral persona: a shared "
        "memory object containing rating bias, category affinity, likes, dislikes, tone, budget "
        "pressure, location, language preference, and review history."
    )
    add_table(
        document,
        ["Input", "Agent Decision", "Output"],
        [
            ["User persona", "Estimate rating bias, tone, preferences, dislikes, and contextual constraints", "Behavioral profile"],
            ["Product details", "Compare category, metadata, price, and text against persona memory", "Predicted star rating"],
            ["Evidence history", "Retrieve similar prior interactions and tone examples", "Grounded written review"],
        ],
        [1.5, 3.3, 1.7],
    )
    document.add_heading("Why This Is Different", level=2)
    add_bullets(
        document,
        [
            "The LLM does not invent the rating; local interpretable scoring predicts it first.",
            "Groq is used after the rating decision to improve fluency and review realism.",
            "The response includes confidence, reasoning, and evidence so judges can inspect behavior.",
            "If no hosted key is configured, deterministic fallback generation keeps the task reproducible.",
        ],
    )
    document.add_page_break()

    document.add_heading("Model and Data Strategy", level=1)
    document.add_paragraph(
        "The rating model combines user average, item average, category affinity, preference overlap, "
        "dislike penalties, text match, and budget sensitivity. Review generation is retrieval-"
        "augmented: the agent supplies similar prior reviews and persona traits to Groq, then validates "
        "the output shape before returning it."
    )
    add_table(
        document,
        ["Feature", "Reason It Matters"],
        [
            ["Rating bias", "Some users are naturally generous while others are strict."],
            ["Category affinity", "A user who loves games may judge games differently from beauty products."],
            ["Likes/dislikes", "Explicit preferences make the review more behaviorally faithful."],
            ["Budget level", "Nigerian price sensitivity changes both rating and wording."],
            ["Retrieval evidence", "Generated reviews stay grounded in the user's prior tone and history."],
        ],
        [1.8, 4.7],
    )
    document.add_heading("Evaluation", level=2)
    add_table(
        document,
        ["Metric", "Team Ace", "Baseline", "Interpretation"],
        [["RMSE", "0.7357", "1.3133", "Personalized behavior reduces rating error on the real Amazon subset."]],
        [1.3, 1.3, 1.3, 2.6],
    )
    document.add_page_break()

    document.add_heading("Demo, Reproducibility, and Limitations", level=1)
    add_bullets(
        document,
        [
            "Standalone deployment entrypoint: app.task_a_main:app.",
            "Web UI: root path opens the Task A review simulator directly.",
            "API endpoint: POST /api/v1/generate-review.",
            "Voice input fills product context; YarnGPT audio can read localized explanations.",
            "Docker and Render deployment configs are included for judge testing.",
        ],
    )
    document.add_paragraph(
        "Limitations: the checked-in Amazon subset is intentionally small, and some product metadata is "
        "review-derived when official metadata streaming is incomplete. Future work would add larger "
        "four-domain training, stronger BERTScore evaluation, embedding retrieval, and richer multi-turn "
        "memory."
    )
    document.add_heading("Conclusion", level=2)
    document.add_paragraph(
        "Task A demonstrates that review simulation can be both fluent and auditable. Team Ace predicts "
        "the behavior first, then lets the LLM speak in the user's voice."
    )
    enforce_black(document)
    document.save(path)
    return path


def build_task_b() -> Path:
    path = DOCS / "Task_B_Recommendation_Team_Ace.docx"
    document = Document()
    configure(document)
    add_header_footer(document, "Task B: Recommendation | Team Ace")
    cover(
        document,
        "Task B: Contextual Recommendation",
        "Ranking cross-domain items with dynamic personas, cold-start logic, and Nigerian context",
    )
    document.add_page_break()

    document.add_heading("Executive Summary", level=1)
    document.add_paragraph(
        "Task B asks the system to recommend what a user will choose next, not merely what is globally "
        "popular. Team Ace ranks products through a local behavioral engine that combines persona "
        "memory, context text, category affinity, preference match, popularity, diversity, and cold-start "
        "fallbacks."
    )
    add_table(
        document,
        ["Input", "Agent Decision", "Output"],
        [
            ["User persona", "Extract budget, interests, category affinity, likes, dislikes, and local context", "Personalized demand signal"],
            ["Current context", "Match the user's immediate need against product metadata and category priors", "Context-aware ranking"],
            ["Catalog candidates", "Score, diversify, and explain top items", "Ranked recommendations"],
        ],
        [1.5, 3.3, 1.7],
    )
    document.add_heading("Why This Is Different", level=2)
    add_bullets(
        document,
        [
            "The ranker works across grocery, movies, games, and beauty rather than one narrow domain.",
            "Cold-start personas still receive useful rankings from explicit context and category priors.",
            "Groq explains the ranked list after local scoring, preserving reproducibility.",
            "Nigerian context shapes reasons without caricature: budget, family use, routines, weather, and voice.",
        ],
    )
    document.add_page_break()

    document.add_heading("Ranking Model and Experiments", level=1)
    document.add_paragraph(
        "The recommender uses candidate generation from the product catalog, then scores each item with "
        "popularity, rating volume, category affinity, explicit preference match, context text match, "
        "dislike penalties, budget fit, and diversity. This produces a ranked list that is explainable "
        "and stable without relying on an opaque LLM score."
    )
    add_table(
        document,
        ["Experiment", "Purpose"],
        [
            ["Popularity-only baseline", "Tests whether personalization improves over generic ranking."],
            ["Cold-start personas", "Validates recommendations when little or no history exists."],
            ["Cross-domain ranking", "Checks whether one persona can receive useful items across categories."],
            ["No Groq fallback", "Confirms the core ranking still works without hosted generation."],
        ],
        [2.1, 4.4],
    )
    document.add_heading("Evaluation", level=2)
    add_table(
        document,
        ["Metric", "Team Ace", "Baseline", "Interpretation"],
        [
            ["NDCG@10", "0.0481", "0.0194", "Personalized rankings place held-out choices higher."],
            ["Hit Rate@10", "0.1163", "0.0349", "More held-out items appear in the top 10."],
        ],
        [1.3, 1.3, 1.3, 2.6],
    )
    document.add_page_break()

    document.add_heading("Demo, Reproducibility, and Limitations", level=1)
    add_bullets(
        document,
        [
            "Standalone deployment entrypoint: app.task_b_main:app.",
            "Web UI: root path opens the Task B recommendation workspace directly.",
            "API endpoint: POST /api/v1/recommend.",
            "Yarn Mode converts recommendation explanations into Nigerian-localized voice scripts.",
            "Docker and Render deployment configs are included for judge testing.",
        ],
    )
    document.add_paragraph(
        "Limitations: the checked-in subset is sparse, so absolute NDCG values are modest. The strongest "
        "next step is a larger four-domain candidate pool with dense metadata and embedding retrieval. "
        "The current evidence still shows the desired direction: personalized ranking beats popularity."
    )
    document.add_heading("Conclusion", level=2)
    document.add_paragraph(
        "Task B demonstrates a recommendation agent that reasons before it speaks. The result is a "
        "ranked list that is contextual, auditable, culturally aware, and deployable as its own service."
    )
    enforce_black(document)
    document.save(path)
    return path


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for path in [build_task_a(), build_task_b()]:
        print(path)


if __name__ == "__main__":
    main()
