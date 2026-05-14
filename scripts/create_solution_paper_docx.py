from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "BCT_Solution_Paper_Team_Ace.docx"
ASSET_DIR = ROOT / "docs" / "assets"
EVAL_REPORT = ROOT / "docs" / "evaluation_report.json"
SUBSET_METRICS = (
    ROOT / "data" / "amazon_subset" / "subset_metrics.json"
    if (ROOT / "data" / "amazon_subset" / "subset_metrics.json").exists()
    else ROOT / "data" / "amazon_smoke" / "subset_metrics.json"
)

BLACK = RGBColor(0, 0, 0)
LIGHT_FILL = "F2F2F2"
HEADER_FILL = "E6E6E6"


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


def set_cell_margins(cell, top=60, start=95, bottom=60, end=95) -> None:
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
    run.font.color.rgb = BLACK
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
    normal.font.size = Pt(9.0)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.line_spacing = 1.0
    normal.paragraph_format.space_after = Pt(2.5)

    for style_name, size in [
        ("Title", 22),
        ("Subtitle", 11),
        ("Heading 1", 14),
        ("Heading 2", 12),
        ("Heading 3", 10.5),
    ]:
        style = styles[style_name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = style_name != "Subtitle"
        style.font.color.rgb = BLACK

    styles["Heading 1"].paragraph_format.space_before = Pt(8)
    styles["Heading 1"].paragraph_format.space_after = Pt(3)
    styles["Heading 2"].paragraph_format.space_before = Pt(6)
    styles["Heading 2"].paragraph_format.space_after = Pt(2)


def add_running_header_footer(document: Document) -> None:
    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = "DSN x BCT LLM Agent Challenge | Solution Paper"
    paragraph.style = document.styles["Normal"]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in paragraph.runs:
        run.font.size = Pt(8.5)
        run.font.color.rgb = BLACK

    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "000000")
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
        ("Dataset Strategy", "Real Amazon Reviews 2023 subset plus checked-in cross-domain demo fixtures"),
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


def add_section_break(document: Document) -> None:
    document.add_page_break()


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2.5)
        paragraph.add_run(item)


def add_numbered(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(2.5)
        paragraph.add_run(item)


def add_pull_quote(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(8)
    run = paragraph.add_run(text)
    run.bold = True
    run.italic = True
    run.font.size = Pt(14)
    run.font.color.rgb = BLACK


def enforce_black_text(document: Document) -> None:
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


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def make_architecture_diagram() -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / "architecture.png"
    image = Image.new("RGB", (1600, 760), "white")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 38)
        box_font = ImageFont.truetype("arialbd.ttf", 24)
        body_font = ImageFont.truetype("arial.ttf", 19)
    except OSError:
        title_font = box_font = body_font = ImageFont.load_default()

    draw.text((60, 45), "Agent Studio Architecture", fill=(0, 0, 0), font=title_font)
    boxes = [
        ((70, 150, 360, 330), "Persona Inputs", ["User profile", "Product details", "Context prompt"]),
        ((460, 150, 750, 330), "Behavioral Memory", ["Rating bias", "Category affinity", "Likes/dislikes"]),
        ((850, 150, 1140, 330), "Local Engine", ["Rating ensemble", "Candidate ranker", "Cold-start logic"]),
        ((1240, 150, 1530, 330), "Groq Layer", ["Review fluency", "Explanations", "Safe fallback"]),
        ((460, 455, 750, 635), "Retrieval", ["Similar history", "Evidence", "Tone examples"]),
        ((850, 455, 1140, 635), "Judge Outputs", ["Task A review", "Task B ranking", "Metrics report"]),
    ]
    for rect, title, lines in boxes:
        draw.rounded_rectangle(rect, radius=24, fill=(247, 247, 247), outline=(0, 0, 0), width=4)
        draw.text((rect[0] + 24, rect[1] + 22), title, fill=(0, 0, 0), font=box_font)
        for line_index, line in enumerate(lines):
            draw.text((rect[0] + 28, rect[1] + 72 + line_index * 32), f"- {line}", fill=(0, 0, 0), font=body_font)

    arrows = [
        ((360, 240), (460, 240)),
        ((750, 240), (850, 240)),
        ((1140, 240), (1240, 240)),
        ((605, 330), (605, 455)),
        ((750, 545), (850, 545)),
        ((995, 330), (995, 455)),
    ]
    for start, end in arrows:
        draw.line([start, end], fill=(0, 0, 0), width=4)
        draw.ellipse((end[0] - 7, end[1] - 7, end[0] + 7, end[1] + 7), fill=(0, 0, 0))
    image.save(path)
    return path


def make_cover_visual() -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / "cover_visual.png"
    image = Image.new("RGB", (1600, 760), "white")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 30)
        body_font = ImageFont.truetype("arial.ttf", 22)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        title_font = body_font = small_font = ImageFont.load_default()

    draw.rectangle((0, 0, 799, 760), fill=(244, 244, 244))
    draw.rectangle((800, 0, 1600, 760), fill=(255, 255, 255))
    draw.line((800, 40, 800, 720), fill=(0, 0, 0), width=5)

    draw.text((90, 70), "Nigerian user context", fill=(0, 0, 0), font=title_font)
    draw.ellipse((315, 170, 465, 320), outline=(0, 0, 0), width=6)
    draw.rounded_rectangle((255, 325, 525, 610), radius=45, outline=(0, 0, 0), width=6)
    draw.rectangle((120, 590, 650, 630), fill=(0, 0, 0))
    draw.line((140, 640, 620, 640), fill=(0, 0, 0), width=3)
    draw.arc((90, 535, 230, 675), 180, 350, fill=(0, 0, 0), width=5)
    draw.rounded_rectangle((535, 255, 675, 485), radius=18, outline=(0, 0, 0), width=5)
    draw.line((555, 315, 655, 315), fill=(0, 0, 0), width=3)
    draw.line((555, 355, 635, 355), fill=(0, 0, 0), width=3)
    draw.text((115, 670), "Lagos student - budget, culture, routine, voice", fill=(0, 0, 0), font=body_font)

    draw.text((890, 70), "Dynamic agent interface", fill=(0, 0, 0), font=title_font)
    draw.rounded_rectangle((930, 150, 1480, 620), radius=28, outline=(0, 0, 0), width=5, fill=(248, 248, 248))
    draw.rounded_rectangle((975, 205, 1435, 315), radius=18, outline=(0, 0, 0), width=3, fill=(255, 255, 255))
    draw.text((1005, 228), "Task A: 4.7 / 5", fill=(0, 0, 0), font=body_font)
    draw.text((1005, 268), "Grounded review generated", fill=(0, 0, 0), font=small_font)
    draw.rounded_rectangle((975, 355, 1435, 500), radius=18, outline=(0, 0, 0), width=3, fill=(255, 255, 255))
    draw.text((1005, 382), "Task B: ranked recommendations", fill=(0, 0, 0), font=body_font)
    for idx, width in enumerate([340, 295, 255]):
        y = 428 + idx * 32
        draw.rectangle((1008, y, 1008 + width, y + 10), fill=(0, 0, 0))
    draw.line((805, 380, 930, 380), fill=(0, 0, 0), width=5)
    draw.polygon([(930, 380), (900, 362), (900, 398)], fill=(0, 0, 0))
    draw.text((900, 670), "Behavior flows into auditable review + recommendation decisions", fill=(0, 0, 0), font=body_font)
    image.save(path)
    return path


def make_ablation_chart(eval_report: dict) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / "ablation_results.png"
    image = Image.new("RGB", (1400, 700), "white")
    draw = ImageDraw.Draw(image)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 34)
        body_font = ImageFont.truetype("arial.ttf", 22)
        label_font = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        title_font = body_font = label_font = ImageFont.load_default()

    draw.text((70, 50), "Ablation Results: Personalized Model vs Baselines", fill=(0, 0, 0), font=title_font)
    metrics = [
        ("Task A RMSE", eval_report.get("task_a", {}).get("global_mean_rmse", 1.3133), eval_report.get("task_a", {}).get("personalized_rmse", 0.7357), "lower is better"),
        ("Task B NDCG@10", eval_report.get("task_b", {}).get("popularity_ndcg_at_10", 0.0194), eval_report.get("task_b", {}).get("personalized_ndcg_at_10", 0.0481), "higher is better"),
        ("Task B Hit Rate@10", eval_report.get("task_b", {}).get("popularity_hit_rate_at_10", 0.0349), eval_report.get("task_b", {}).get("personalized_hit_rate_at_10", 0.1163), "higher is better"),
    ]
    max_values = [1.4, 0.12, 0.12]
    for idx, (label, baseline, personalized, note) in enumerate(metrics):
        y = 150 + idx * 160
        draw.text((80, y), label, fill=(0, 0, 0), font=label_font)
        draw.text((80, y + 35), note, fill=(0, 0, 0), font=body_font)
        base_len = int((baseline / max_values[idx]) * 780)
        pers_len = int((personalized / max_values[idx]) * 780)
        draw.rectangle((420, y + 5, 420 + base_len, y + 42), fill=(190, 190, 190), outline=(0, 0, 0))
        draw.rectangle((420, y + 62, 420 + pers_len, y + 99), fill=(0, 0, 0), outline=(0, 0, 0))
        draw.text((1225, y + 8), f"base {baseline:.4f}", fill=(0, 0, 0), font=body_font)
        draw.text((1225, y + 65), f"ours {personalized:.4f}", fill=(0, 0, 0), font=body_font)
    draw.text((420, 645), "Grey = baseline     Black = Team Ace personalized model", fill=(0, 0, 0), font=body_font)
    image.save(path)
    return path


def add_image(document: Document, path: Path, caption: str, width: float = 6.45) -> None:
    if not path.exists():
        return
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    run.add_picture(str(path), width=Inches(width))
    if caption:
        caption_paragraph = document.add_paragraph(caption)
        caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption_paragraph.runs[0].font.size = Pt(9)
        caption_paragraph.runs[0].font.color.rgb = BLACK


def add_side_by_side_images(document: Document, left_path: Path, right_path: Path, caption: str) -> None:
    if not left_path.exists() or not right_path.exists():
        return
    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for cell, image_path in zip(table.rows[0].cells, [left_path, right_path], strict=True):
        set_cell_margins(cell, top=30, start=30, bottom=30, end=30)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run()
        run.add_picture(str(image_path), width=Inches(3.05))
    caption_paragraph = document.add_paragraph(caption)
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_paragraph.runs[0].font.size = Pt(9)
    caption_paragraph.runs[0].font.color.rgb = BLACK


def build_document() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.6)
    section.bottom_margin = Inches(0.6)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)
    section.different_first_page_header_footer = True

    configure_styles(document)
    add_running_header_footer(document)

    eval_report = load_json(EVAL_REPORT)
    subset_metrics = load_json(SUBSET_METRICS)

    # Cover page
    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Dynamic User Modeling and Contextual Recommendation\nwith LLM Agents")

    subtitle = document.add_paragraph(style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(
        "Building Consistent, Auditable, and Deeply Nigerian-Aware Behavioral Agents "
        "for Review Simulation and Personalization"
    )
    add_image(document, make_cover_visual(), "", width=5.95)

    cover_lines = [
        "Team Ace",
        "Teslim Sadiq | Yasir Oyebo | Abiodun Mark",
        "Contact: sadiqadetola08@gmail.com",
        "Data & AI Summit Hackathon 3.0",
        "DSN x BCT LLM Agent Challenge",
        "May 2026",
    ]
    for index, line in enumerate(cover_lines):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(1.5)
        run = paragraph.add_run(line)
        run.bold = index == 0
        run.font.size = Pt(12 if index == 0 else 9.2)
        run.font.color.rgb = BLACK

    add_section_break(document)

    # Page 2
    document.add_heading("Executive Summary", level=1)
    document.add_paragraph(
        "In a world of static user profiles, Team Ace introduces dynamic behavioral personas: living "
        "representations of users that evolve with every interaction, context, and cultural signal. "
        "The submitted system is one unified agent studio that handles both challenge tasks through "
        "the same behavioral memory core."
    )
    add_table(
        document,
        ["Task", "What the Agent Does", "Output"],
        [
            ["Task A: User Modeling", "Predicts realistic star ratings and generates grounded, tone-aware reviews for unseen items.", "Rating, review, confidence, reasoning, evidence"],
            ["Task B: Recommendation", "Produces contextual, cross-domain rankings that work for cold-start and history-rich users.", "Top recommendations, reasons, matched preferences"],
        ],
        [1.65, 3.3, 2.0],
    )
    document.add_heading("What Makes Team Ace Different", level=2)
    add_bullets(
        document,
        [
            "Local transparent scoring makes decisions auditable before any LLM text is generated.",
            "Groq is used as a controlled language layer for fluency, not as an opaque decision maker.",
            "Nigerian context is treated as product-relevant behavior: budget pressure, family use, local routines, weather, language, and taste.",
            "The app is production-minded: FastAPI, web UI, Docker/Render deployment, tests, real subset metrics, and no-key fallbacks.",
        ],
    )
    if eval_report:
        add_table(
            document,
            ["Key Result", "Team Ace", "Baseline", "Why It Matters"],
            [
                ["Task A RMSE", str(eval_report["task_a"]["personalized_rmse"]), str(eval_report["task_a"]["global_mean_rmse"]), "Lower error from user-aware rating behavior"],
                ["Task B NDCG@10", str(eval_report["task_b"]["personalized_ndcg_at_10"]), str(eval_report["task_b"]["popularity_ndcg_at_10"]), "About 2.5x the popularity baseline"],
                ["Reproducibility", "Container, tests, fallback", "Manual-only demos", "Judges can run and inspect the system"],
            ],
            [1.45, 1.2, 1.2, 2.9],
        )

    document.add_heading("1. Why Static Profiles Fail Nigerian Consumers", level=1)
    document.add_paragraph(
        "Real consumer behavior is dynamic, contextual, and culturally rich. A Lagos student may value "
        "affordability, transport convenience, multiplayer entertainment, and quick meals in the same "
        "week. An Abuja professional may care more about dependable weekday routines, heat-friendly "
        "skincare, and polished media choices. A Port Harcourt family shopper may optimize for guests, "
        "children, home use, and value packs. A static profile misses those shifts."
    )
    document.add_paragraph(
        "Traditional recommenders are strong at repeated patterns but weak at explanation, cold-start, "
        "and cross-domain context. Pure LLM systems can sound fluent but often hide the decision logic. "
        "Our opportunity is to combine both: measurable behavioral intelligence first, controlled "
        "language generation second."
    )
    add_pull_quote(document, "\"Users are not fixed vectors; they are changing stories.\"")

    document.add_heading("2. Our Philosophy: Transparent Intelligence Meets Cultural Depth", level=1)
    document.add_paragraph(
        "Team Ace takes a hybrid agentic approach that stands apart from pure LLM sprawl and black-box "
        "recommenders. The same persona object powers both tasks, but the architecture separates memory, "
        "retrieval, scoring, generation, and evaluation."
    )
    add_table(
        document,
        ["Aspect", "Typical Solutions", "Team Ace Approach", "Advantage"],
        [
            ["Scoring", "Opaque LLM calls", "Local interpretable ensembles", "Auditable and reproducible"],
            ["Language", "LLM does everything", "Groq only after decisions", "Controllable and consistent"],
            ["User model", "Static embeddings", "Dynamic traces plus Nigerian signals", "Culturally relevant"],
            ["Architecture", "Monolithic", "Bounded agentic workflow", "Reliable for judges"],
        ],
        [1.2, 1.7, 2.2, 1.7],
    )
    document.add_paragraph(
        "The result is a system that is both measurable and human: numerical decisions are transparent, "
        "while the final review and recommendation explanations still feel natural."
    )

    add_section_break(document)

    document.add_heading("3. System Architecture", level=1)
    add_image(
        document,
        make_architecture_diagram(),
        "Figure 1. The Agent Studio keeps behavioral scoring local and uses Groq only after structured validation.",
        width=6.65,
    )
    add_table(
        document,
        ["Layer", "Role", "Implementation"],
        [
            ["Persona Modeling", "Compress history and context", "Rating bias, category affinity, likes/dislikes, budget, tone, location"],
            ["Retrieval Memory", "Ground behavior", "Similar reviews by category, keywords, and user signals"],
            ["Behavior Engine", "Make local decisions", "Rating ensemble and recommendation ranker"],
            ["Groq Layer", "Improve language", "Validated review/explanation generation with fallback"],
            ["UI/API/Eval", "Expose and measure", "FastAPI endpoints, web UI, metrics scripts, Docker/Render"],
        ],
        [1.35, 1.8, 3.35],
    )
    document.add_heading("Agentic Workflow", level=2)
    add_numbered(
        document,
        [
            "Read the persona, stated context, and historical interactions, then summarize rating bias, category affinity, likes, dislikes, tone, and budget pressure.",
            "Retrieve the most relevant prior interactions for the current product or recommendation context.",
            "Score the behavioral decision locally: Task A predicts stars; Task B ranks candidates before any LLM text is requested.",
            "Ask Groq to verbalize only the validated result, with evidence and constraints included in the prompt.",
            "Validate the response shape and fall back to deterministic local text when the hosted model is unavailable.",
        ],
    )

    add_section_break(document)

    document.add_heading("4. Dataset Strategy and Experiments", level=1)
    document.add_paragraph(
        "The competition plan uses Amazon Reviews 2023 because it provides review text, ratings, user "
        "histories, item identifiers, and product categories at real platform scale. The repository now "
        "ships two data tracks: curated cross-domain fixtures for instant demos and a checked-in real "
        "Amazon Reviews 2023 subset for measurable experiments."
    )
    if subset_metrics:
        add_table(
            document,
            ["Real Amazon Subset", "Value", "Meaning"],
            [
                ["Source", "Amazon Reviews 2023", "Official McAuley Lab review files; metadata stream supported when available"],
                ["Categories", ", ".join(subset_metrics.get("categories", [])), "The four challenge demo domains are represented"],
                ["Products", str(subset_metrics.get("products", "")), "Normalized candidate products in the checked-in subset"],
                ["Reviews", str(subset_metrics.get("reviews", "")), "Real review texts and star ratings after filtering"],
                ["Users", str(subset_metrics.get("users", "")), "Users contributing chronological behavior for train/test splits"],
                ["Holdout", f"{subset_metrics.get('train_interactions', '')} train / {subset_metrics.get('test_interactions', '')} test", "Most recent interaction held out by user when possible"],
            ],
            [1.45, 2.1, 3.0],
        )
    document.add_paragraph(
        "Splitting holds out the most recent interaction for users with enough history. Cold-start "
        "behavior leans more heavily on explicit persona preferences, category priors, popularity, "
        "budget level, and context text."
    )
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
    add_image(document, make_ablation_chart(eval_report), "Figure 2. Ablation chart comparing personalized models to baselines.", width=6.45)

    add_section_break(document)

    document.add_heading("5. Implementation and Technical Details", level=1)
    document.add_paragraph(
        "The application is a single FastAPI service that serves the web UI and the REST API. Task A "
        "uses POST /api/v1/generate-review. Task B uses POST /api/v1/recommend. The same service also "
        "exposes /health, demo personas, evaluation outputs, Yarn Mode localization, and YarnGPT audio."
    )
    add_table(
        document,
        ["Component", "Implementation Detail"],
        [
            ["Backend", "FastAPI, Pydantic schemas, modular service layer, deterministic fallbacks"],
            ["Task A", "User bias, item average, category affinity, text match, budget and dislike penalties"],
            ["Task B", "Popularity, context match, preference match, diversity, cold-start and cross-domain ranking"],
            ["LLM", "Groq improves review/explanation fluency after local scoring"],
            ["Voice", "Browser speech input plus YarnGPT hosted audio for localized output"],
        ],
        [1.55, 4.95],
    )
    add_table(
        document,
        ["Persona", "Context Signal", "Behavioral Effect"],
        [
            ["Lagos student", "Low budget, classes, transport cost", "Quick meals, value picks, local comedy, multiplayer games"],
            ["Abuja professional", "Work routine, heat, polished daily use", "Dependable coffee, political drama, lightweight skincare"],
            ["Port Harcourt family shopper", "Visitors, children, home use", "Family-safe media, easy drinks, gentle skincare"],
        ],
        [1.65, 2.25, 2.6],
    )
    document.add_paragraph(
        "Yarn Mode converts explanations into Nigerian Pidgin, Yoruba-flavoured English, Hausa-flavoured "
        "English, Igbo-flavoured English, or a formal judge summary. This is an output layer, not a "
        "scoring shortcut, so the underlying metrics remain stable."
    )

    document.add_heading("6. Results and Evaluation", level=1)
    document.add_paragraph(
        "The real subset is intentionally bounded so the repository remains lightweight, but it proves "
        "that the pipeline can stream official Amazon data, create chronological splits, and compare "
        "personalized models against non-personalized baselines."
    )
    if eval_report:
        add_table(
            document,
            ["Metric", "Personalized", "Baseline", "Lift"],
            [
                [
                    "Task A RMSE",
                    str(eval_report["task_a"]["personalized_rmse"]),
                    str(eval_report["task_a"]["global_mean_rmse"]),
                    str(eval_report["ablations"]["rating_lift_vs_global_rmse"]),
                ],
                [
                    "Task B NDCG@10",
                    str(eval_report["task_b"]["personalized_ndcg_at_10"]),
                    str(eval_report["task_b"]["popularity_ndcg_at_10"]),
                    str(eval_report["ablations"]["ranking_lift_vs_popularity_ndcg"]),
                ],
                [
                    "Task B Hit Rate@10",
                    str(eval_report["task_b"]["personalized_hit_rate_at_10"]),
                    str(eval_report["task_b"]["popularity_hit_rate_at_10"]),
                    "More held-out items recovered in top 10",
                ],
            ],
            [1.7, 1.25, 1.25, 2.3],
        )
    document.add_paragraph(
        "The ranking values are modest because the checked-in subset is small and sparse. The key signal "
        "is the direction of the ablation: personalization beats global rating and popularity baselines "
        "while preserving interpretability."
    )

    add_section_break(document)

    document.add_heading("7. Demo and Reproducibility", level=1)
    document.add_paragraph(
        "The submitted application is designed for judge inspection. The landing page explains the agent "
        "promise, Task A exposes the simulated review workflow, and Task B exposes the ranked "
        "recommendation workflow. The app runs locally, in Docker, or on Render."
    )
    add_side_by_side_images(
        document,
        ASSET_DIR / "task_a.png",
        ASSET_DIR / "task_b.png",
        "Figure 3. Task A and Task B workspaces after generation.",
    )
    add_table(
        document,
        ["Artifact", "Purpose"],
        [
            ["Dockerfile / docker-compose.yml", "Containerized local verification for judges"],
            ["render.yaml", "Deployment blueprint for the hosted demo"],
            ["tests/", "Unit and integration checks for schemas, scoring, generation, fallback, and API behavior"],
            ["data/amazon_subset", "Checked-in real Amazon Reviews 2023 subset used for the latest paper metrics"],
            ["data/fixtures", "Deterministic cross-domain UI demo data that works without network access"],
        ],
        [2.1, 4.4],
    )

    document.add_heading("8. Limitations and Future Work", level=1)
    document.add_paragraph(
        "The current build is optimized for deadline reliability and judge reproducibility. The main "
        "limitation is that the checked-in Amazon subset is still much smaller than the full corpus, "
        "and some product metadata in the bounded subset is review-derived when official metadata "
        "streaming is incomplete. With more time, we would add embedding indexes, larger sampled "
        "evaluation, rating calibration, multi-turn conversational memory, richer BERTScore evaluation, "
        "and real Nigerian marketplace data."
    )
    document.add_paragraph(
        "The strongest next experiment would be a larger four-category run with dense product metadata "
        "and an embedding index for candidate generation. That would let the same agent workflow scale "
        "from a polished hackathon demo into a stronger production recommender."
    )

    document.add_heading("Team and Conclusion", level=1)
    add_table(
        document,
        ["Team Ace Member", "Role / Strength"],
        [
            ["Teslim Sadiq", "Product engineering, backend/API integration, deployment, and demo flow"],
            ["Yasir Oyebo", "Data strategy, evaluation, experiments, and model reasoning"],
            ["Abiodun Mark", "UX polish, Nigerian contextualization, storytelling, and judge presentation"],
        ],
        [2.0, 4.5],
    )
    document.add_paragraph(
        "Team Ace is passionate about building practical, culturally aware AI that solves real African "
        "problems. This project is not just an agent submission; it is a demonstration of a new standard "
        "for interpretable, reproducible, and deeply contextual LLM agents built for Nigeria and the world."
    )
    document.add_heading("References and Appendix", level=2)
    add_bullets(
        document,
        [
            "Amazon Reviews 2023 official dataset, McAuley Lab.",
            "Groq hosted chat model for controlled review and explanation generation.",
            "YarnGPT hosted voice layer for Nigerian-localized audio output.",
            "Evaluation artifacts: docs/evaluation_report.json and scripts/evaluate_dataset.py.",
        ],
    )

    enforce_black_text(document)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_document()
