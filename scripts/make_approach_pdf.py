"""Generate SOLUTION_APPROACH.pdf — submission leave-behind (not a talk script)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.paths import ROOT


def styles():
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle(
            "T",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            spaceAfter=6,
            textColor=colors.HexColor("#0f172a"),
        ),
        "subtitle": ParagraphStyle(
            "ST",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#0f172a"),
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor("#1e293b"),
        ),
        "body": ParagraphStyle(
            "B",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            textColor=colors.HexColor("#1e293b"),
        ),
        "bullet": ParagraphStyle(
            "Bu",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            leftIndent=12,
            spaceAfter=2,
            textColor=colors.HexColor("#1e293b"),
        ),
        "code": ParagraphStyle(
            "C",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            backColor=colors.HexColor("#f1f5f9"),
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=8,
            textColor=colors.HexColor("#0f172a"),
        ),
        "meta": ParagraphStyle(
            "M",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "Cap",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=8,
        ),
    }
    return s


def bullets(items, sty):
    return [
        Paragraph(f"• {item}", sty["bullet"]) for item in items
    ]


def main() -> None:
    out = ROOT / "SOLUTION_APPROACH.pdf"
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="AML Compliance Multi-Agent Desk — Solution Approach",
        author="Assignment Submission",
    )
    s = styles()
    story = []

    story.append(Paragraph("AML Compliance Multi-Agent Desk", s["title"]))
    story.append(
        Paragraph(
            "Solution Approach & Architecture Overview<br/>"
            "AI Agent Developer Assignment Submission",
            s["subtitle"],
        )
    )
    story.append(
        Paragraph(
            "Repository: https://github.com/Mohitmeenna/aml-compliance-agents<br/>"
            "Eval status: 15/15 pass (pass_rate = 1.0) after bootstrap",
            s["meta"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # 1
    story.append(Paragraph("1. Problem & Goal", s["h1"]))
    story.append(
        Paragraph(
            "Build a working agentic system for a bank AML / transaction-monitoring desk. "
            "The system must ingest heterogeneous compliance data (regulatory PDFs + tabular "
            "ledgers/sanctions), convert it into artifacts agents can reason over, enforce "
            "role-based access at the data layer, answer natural-language questions, and "
            "improve over time from analyst alert dispositions. The guiding constraint from "
            "the brief: a smaller system that runs end-to-end beats an elaborate design that does not.",
            s["body"],
        )
    )

    # 2
    story.append(Paragraph("2. High-Level Architecture", s["h1"]))
    story.append(
        Paragraph(
            "The solution is a Python multi-agent pipeline with a single data-access choke point "
            "(DataGate). Every question is scoped to a user profile; agents never see raw tables "
            "directly.",
            s["body"],
        )
    )
    arch = (
        "  User question + user_id\n"
        "              |\n"
        "              v\n"
        "        Orchestrator  ---- prompt-injection check on user input\n"
        "              |\n"
        "              v\n"
        "      ScreeningAgent  ---- retrieve / screen via DataGate (RBAC)\n"
        "              |            BM25 regulatory retrieval, alerts, txns\n"
        "              |  AgentMessage handoff (structured evidence JSON)\n"
        "              v\n"
        "   InvestigationAgent ---- verify handoff + synthesize answer\n"
        "              |            (LLM if key present, else deterministic)\n"
        "              v\n"
        "           Answer / ACCESS_DENIED (no content leak on refusal)"
    )
    story.append(Preformatted(arch, s["code"]))
    story.append(
        Paragraph(
            "Figure: request path from question to answer, with RBAC applied before synthesis.",
            s["caption"],
        )
    )

    story.append(Paragraph("2.1 Agent boundaries", s["h2"]))
    story.extend(
        bullets(
            [
                "<b>ScreeningAgent</b> — intent detection, retrieval, sanctions/structuring/correspondent screening assembly. Owns evidence gathering; fails closed on AccessDenied.",
                "<b>InvestigationAgent</b> — consumes the handoff, verifies consistency (drops malformed alerts, notes missing buckets), drafts the final answer from evidence only.",
                "<b>Orchestrator</b> — wires the handoff, blocks instruction-injection style user queries, short-circuits refusals so protected content never reaches synthesis.",
            ],
            s,
        )
    )
    story.append(
        Paragraph(
            "When screening fails softly, investigation continues in degraded mode and surfaces "
            "the screening error instead of inventing evidence. That makes the handoff observable "
            "and matches how a real desk separates screening from investigation write-up.",
            s["body"],
        )
    )

    # 3
    story.append(Paragraph("3. Data & Ingestion", s["h1"]))
    story.append(
        Paragraph(
            "Public / synthetic sources only — no real customer PII and no employer-confidential data.",
            s["body"],
        )
    )
    data_rows = [
        [Paragraph("<b>Source</b>", s["body"]), Paragraph("<b>Format</b>", s["body"]), Paragraph("<b>Notes</b>", s["body"])],
        [
            Paragraph("Customer master + transaction ledger", s["body"]),
            Paragraph("CSV / XLSX", s["body"]),
            Paragraph("Synthetic seeded AML patterns (structuring, sanctions hit, correspondent flags)", s["body"]),
        ],
        [
            Paragraph("Sanctions / watchlist", s["body"]),
            Paragraph("CSV / XLSX", s["body"]),
            Paragraph("Synthetic subset styled after OFAC/UN fields (self-contained, license-clean)", s["body"]),
        ],
        [
            Paragraph("Regulatory guidance", s["body"]),
            Paragraph("PDF", s["body"]),
            Paragraph("Synthetic excerpts paraphrasing public FATF / FinCEN / RBI themes; real PDF files under data/raw/regulatory/", s["body"]),
        ],
        [
            Paragraph("SARs + audit trail", s["body"]),
            Paragraph("JSON", s["body"]),
            Paragraph("Synthetic filings and disposition events for RBAC demos", s["body"]),
        ],
    ]
    t = Table(data_rows, colWidths=[1.7 * inch, 0.9 * inch, 4.0 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "PDFs are chunked on Section/Chapter/Advisory headings to preserve hierarchy rather "
            "than blind fixed-size splits. Tabular files are normalized through pandas with NaN cleanup.",
            s["body"],
        )
    )

    # 4
    story.append(Paragraph("4. Understanding Layer", s["h1"]))
    story.append(
        Paragraph(
            "Raw files are converted into derived artifacts under <b>data/understanding/</b> so agents "
            "do not re-parse PDFs and re-score the ledger on every question.",
            s["body"],
        )
    )
    story.append(Paragraph("Precomputed", s["h2"]))
    story.extend(
        bullets(
            [
                "Regulatory chunks + BM25 token index",
                "Obligation / threshold extraction (e.g. CTR ~ USD 10,000; structuring window)",
                "Counterparty activity profiles",
                "Baseline screening alerts with feedback-adjusted score multipliers",
            ],
            s,
        )
    )
    story.append(Paragraph("Computed on the fly (per request)", s["h2"]))
    story.extend(
        bullets(
            [
                "DataGate filtering and PII masking for the active role",
                "Query intent routing and evidence assembly",
                "Answer synthesis (LLM or deterministic)",
                "Disposition writes that rebuild multipliers",
            ],
            s,
        )
    )
    story.append(
        Paragraph(
            "<b>Why this split:</b> parsing and full-ledger screening are relatively stable and expensive; "
            "access control must stay request-scoped so a cached CCO answer can never be reused for an auditor.",
            s["body"],
        )
    )

    # 5
    story.append(Paragraph("5. Role-Based Access Control (data layer)", s["h1"]))
    story.append(
        Paragraph(
            "Permissions live in <b>config/roles.yaml</b> — not only in prompts. "
            "<b>src/rbac/DataGate</b> is the only path agents use to read customers, transactions, "
            "alerts, SARs, sanctions, audit events, and regulatory chunks.",
            s["body"],
        )
    )
    role_rows = [
        [Paragraph("<b>Profile</b>", s["body"]), Paragraph("<b>Role</b>", s["body"]), Paragraph("<b>Access sketch</b>", s["body"])],
        [Paragraph("u_cco", s["body"]), Paragraph("Chief Compliance Officer", s["body"]), Paragraph("Full access including PII and SARs", s["body"])],
        [Paragraph("u_analyst", s["body"]), Paragraph("AML Analyst", s["body"]), Paragraph("Alerts/txns with masked PII; no SARs / ID docs", s["body"])],
        [Paragraph("u_auditor", s["body"]), Paragraph("External Auditor", s["body"]), Paragraph("Audit trail + disposition rationale; no raw txn/customer PII", s["body"])],
        [Paragraph("u_rm", s["body"]), Paragraph("Relationship Manager", s["body"]), Paragraph("Portfolio PF-APAC-01 only", s["body"])],
    ]
    rt = Table(role_rows, colWidths=[0.9 * inch, 1.7 * inch, 4.0 * inch])
    rt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(rt)
    story.append(Spacer(1, 6))
    story.extend(
        bullets(
            [
                "Refusals return a standard ACCESS_DENIED message with <b>no protected payload</b>.",
                "Masking rules (partial name, last-4 accounts, redacted IDs) apply when a role can read a record but not PII.",
                "Aggregates / clever phrasing cannot bypass the gate: the model only receives already-filtered JSON.",
            ],
            s,
        )
    )

    # 6
    story.append(Paragraph("6. Feedback & Learning Loop", s["h1"]))
    story.append(
        Paragraph(
            "Analysts disposition alerts as <b>true_hit</b>, <b>false_positive</b>, or <b>escalate</b>. "
            "Each disposition updates a per-feedback_key score multiplier and appends a few-shot memory "
            "entry; understanding/alerts are then rebuilt so future screening scores change.",
            s["body"],
        )
    )
    story.extend(
        bullets(
            [
                "Demo command: <font face='Courier'>python -m src.query.cli feedback-demo</font>",
                "Observed before/after on a fuzzy sanctions candidate: multiplier 1.0 → 0.65; alert score 0.95 → 0.617",
                "This is behavioural change, not only logging a thumbs-down.",
            ],
            s,
        )
    )

    # 7
    story.append(Paragraph("7. Query Interface & LLM", s["h1"]))
    story.append(
        Paragraph(
            "The interface is a minimal CLI (<font face='Courier'>python -m src.query.cli ask ...</font>). "
            "The assignment explicitly allows CLI / simple UI; correctness matters more than polish.",
            s["body"],
        )
    )
    story.extend(
        bullets(
            [
                "OpenAI is <b>not</b> required. Any OpenAI-compatible API works (Groq free tier tested with llama-3.3-70b-versatile).",
                "Without a key, InvestigationAgent uses a deterministic synthesizer — sufficient for RBAC, screening, and eval.",
                "With a key, the same RBAC-filtered evidence JSON is passed to the model for a clearer investigation-style answer.",
                "Bonus: remittance narratives and override-style user queries are sanitized / blocked (prompt-injection surface).",
            ],
            s,
        )
    )

    # 8
    story.append(Paragraph("8. Evaluation Suite", s["h1"]))
    story.append(
        Paragraph(
            "Ship-with: <font face='Courier'>eval/eval_set.json</font> (15 cases) and "
            "<font face='Courier'>python -m src.eval.runner</font>. Role scopes are enforced in code "
            "before the model sees data. Current reported pass rate after bootstrap: <b>15/15 (1.0)</b>.",
            s["body"],
        )
    )
    story.append(Paragraph("Coverage includes:", s["h2"]))
    story.extend(
        bullets(
            [
                "Admin (CCO) + two non-admins (analyst, auditor) + portfolio-scoped RM",
                "At least one RBAC refusal path per restricted profile family",
                "Questions that answer differently by profile (e.g. unmasked PII)",
                "Questions needing both regulatory document retrieval and transaction/alert evidence",
                "Injection / override attempt that must not leak national IDs",
            ],
            s,
        )
    )
    story.append(
        Paragraph(
            "Checks are structural (denial flags, required/forbidden substrings, leak tests, "
            "regulatory+txn evidence presence) so the suite stays honest under LLM wording variance.",
            s["body"],
        )
    )

    # 9
    story.append(Paragraph("9. What Breaks at 100×", s["h1"]))
    story.append(
        Paragraph(
            "Three concrete failure modes if this moved from the sample set to bank-scale volume:",
            s["body"],
        )
    )
    story.extend(
        bullets(
            [
                "<b>In-memory alert rebuild</b> — full ledger rescreen on feedback becomes multi-minute and memory-bound under millions of txns/day. Change: streaming screening + durable alert store; feedback as feature multipliers without full recompute.",
                "<b>Process-local BM25</b> — thousands of pages across jurisdictions and hundreds of concurrent users need a shared search service. Change: OpenSearch/Vespa with jurisdiction collections and ACL filters at query time.",
                "<b>Per-request full-table DataGate filtering</b> — loading then masking entire tables in Python does not scale and risks touching rows a role should never load. Change: DB row-level security / masked views and scoped queries only.",
            ],
            s,
        )
    )

    # 10
    story.append(Paragraph("10. How to Run (for reviewers)", s["h1"]))
    run = (
        "pip install -r requirements.txt\n"
        "copy .env.example .env          # optional: add Groq/OpenAI-compatible key\n"
        "python -m scripts.bootstrap\n"
        "python -m src.eval.runner\n"
        "python -m src.query.cli ask --user u_cco -q "
        '"Which transactions this month breach the FATF guidance on correspondent banking?"\n'
        "python -m src.query.cli feedback-demo"
    )
    story.append(Preformatted(run, s["code"]))

    # 11
    story.append(Paragraph("11. Deliverables Map", s["h1"]))
    story.extend(
        bullets(
            [
                "Working code + README with setup and 100× section — repository linked above",
                "Eval set + runner + pass-rate note — eval/ and README",
                "Understanding artifacts — data/understanding/ (regenerable via scripts/build_understanding.py)",
                "Walkthrough — live call (talk track: WALKTHROUGH_SCRIPT.docx) or recorded video",
                "This PDF — concise written approach for email attachment",
            ],
            s,
        )
    )

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    story.append(
        Paragraph(
            "Disclaimer: assignment demo only. Synthetic data. Not a production AML system and not legal advice.",
            s["meta"],
        )
    )

    doc.build(story)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
