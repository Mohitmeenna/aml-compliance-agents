# AML Compliance Multi-Agent Desk

Working end-to-end agentic system for a bank **AML / transaction monitoring** desk: ingest heterogeneous compliance data → build understanding artifacts → answer natural-language questions via a **two-agent handoff**, with **data-layer RBAC** and a **disposition feedback loop** that changes future screening scores.

> Guiding principle from the brief: a smaller system that runs beats an elaborate design that doesn't.

---

## What you get

| Requirement | Implementation |
|---|---|
| Data ingestion (PDF + Excel/CSV) | Synthetic ledger + sanctions CSV/XLSX; FATF/FinCEN/RBI-style regulatory PDFs |
| Understanding files | Obligations, counterparty profiles, alerts, BM25 index under `data/understanding/` |
| RBAC at data layer | `DataGate` in `src/rbac/` — roles in `config/roles.yaml`, enforced before agents see data |
| Feedback / learning | Alert dispositions adjust score multipliers + few-shot memory; `feedback-demo` shows before/after |
| NL query interface | CLI (`python -m src.query.cli ask ...`) |
| Multi-agent handoff | `ScreeningAgent` → `InvestigationAgent` via `Orchestrator` |
| Eval set + runner | 15 cases in `eval/eval_set.json`; `python -m src.eval.runner` |
| Prompt-injection bonus | Remittance + user-query sanitization in `src/rbac/sanitize.py` |

---

## Roles

| User id | Role | Access sketch |
|---|---|---|
| `u_cco` | Chief Compliance Officer | Full access incl. PII + SARs |
| `u_analyst` | AML Analyst | Alerts/txns with **masked PII**; no SARs |
| `u_auditor` | External Auditor | Audit trail / disposition rationale only; **no raw txn/customer PII** |
| `u_rm` | Relationship Manager | **Portfolio `PF-APAC-01` only** |

Role scopes live in config, not prompts.

---

## Setup

```bash
# Python 3.10+ recommended
cd Azentio-assignment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
```

Put a key in `.env` (OpenAI is **not** required — any OpenAI-compatible API works):

```
# Groq free tier (keys look like gsk_...)
LLM_PROVIDER=groq
OPENAI_API_KEY=gsk-...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=llama-3.3-70b-versatile
```

Also supported: xAI Grok (`XAI_API_KEY`) and OpenAI. Note: **Groq ≠ Grok** — Groq is the inference host; Grok is xAI’s model.

The system **runs without an API key** using a deterministic investigation synthesizer (enough for RBAC + screening + eval). With a key, answers are LLM-polished from the same RBAC-filtered evidence.

### Bootstrap data + understanding

```bash
python -m scripts.generate_data
python -m scripts.build_understanding
```

Or:

```bash
python -m scripts.bootstrap
```

### Ask a question

```bash
python -m src.query.cli users

python -m src.query.cli ask --user u_cco -q "Which transactions this month breach the FATF guidance on correspondent banking?"

python -m src.query.cli ask --user u_analyst -q "What is the unmasked national id for customer C-1002?"

python -m src.query.cli ask --user u_auditor -q "Show the audit trail decisions and disposition rationale."
```

### Feedback before/after

```bash
python -m src.query.cli feedback-demo
```

Marks a fuzzy sanctions alert as `false_positive`, rebuilds understanding, and prints the score multiplier change.

Manual disposition:

```bash
python -m src.query.cli dispose --user u_analyst --alert-id AL-000X --disposition false_positive --rationale "Not a true SDN match"
```

### Eval

```bash
python -m src.eval.runner
```

Report written to `eval/last_report.json`. After bootstrap this suite currently passes **15/15 (pass_rate=1.0)** on the deterministic path (no API key required for eval).

---

## Architecture

```
User question + user_id
        │
        ▼
  Orchestrator ── injection check
        │
        ▼
  ScreeningAgent          # retrieve / screen (RBAC-filtered)
        │ AgentMessage handoff
        ▼
  InvestigationAgent      # verify handoff + synthesize answer
        │
        ▼
     Answer (+ refusal if AccessDenied)
```

**Precomputed vs on the fly**

- **Precomputed:** PDF chunking, BM25 tokens, obligation extraction, counterparty profiles, baseline alerts (with feedback multipliers).
- **On the fly:** `DataGate` filtering/masking, query intent routing, investigation synthesis, disposition writes.

Cached answers are never shared across roles — every ask re-filters through `DataGate`.

### Data provenance

- **Transactions / customers / SARs / audit:** synthetic (seeded).
- **Sanctions:** synthetic subset styled after public OFAC/UN list fields — **not** a live list download (keeps the repo self-contained and license-clean).
- **Regulatory PDFs:** synthetic excerpts paraphrasing publicly known themes from FATF correspondent-banking guidance, FinCEN structuring advisories, and RBI KYC/AML master-direction topics. Generated locally as real PDFs under `data/raw/regulatory/`.

No real customer PII and no employer-confidential data.

---

## Agent failure / wrong handoff

- If `ScreeningAgent` raises `AccessDenied`, investigation **short-circuits** to a refusal that does not include protected content.
- If screening returns a soft failure, investigation still runs in **degraded** mode, records `screening_error`, and the verifier notes missing buckets.
- The verifier drops malformed alerts (no `alert_id`) before synthesis.

---

## What breaks at 100×

Be specific — component, failure mode, change:

1. **In-memory pandas + JSON alert rebuild (`src/understanding`)**  
   **Failure:** At millions of transactions/day, `generate_alerts` scanning the full ledger on every feedback rebuild becomes multi-minute (or worse) and memory-bound. Concurrent users would stampede rebuilds.  
   **Change:** Move screening to incremental stream jobs (Flink/Spark/Kafka), store alerts in Postgres/Elasticsearch, apply feedback as feature-store multipliers without full recompute.

2. **Single-process BM25 over regulatory chunks (`RegulatoryIndex`)**  
   **Failure:** Thousands of pages across jurisdictions explode chunk count; process-local BM25 won't share across hundreds of concurrent analysts and won't handle hot index swaps when a new circular lands.  
   **Change:** Dedicated vector/BM25 service (OpenSearch / Vespa) with per-jurisdiction collections, ACL field filters at query time, and async re-index pipelines.

3. **Per-request full-table RBAC filter in `DataGate`**  
   **Failure:** Filtering entire customer/txn arrays in Python per question does not scale to concurrent desks; easy to accidentally load rows the role shouldn't even touch into memory before masking.  
   **Change:** Push predicates to the database (`portfolio_id = ANY(...)`, column-level masking views / Row-Level Security), issue scoped queries only, and audit every access.

---

## Walkthrough notes (for video / live call)

Cover: (1) bootstrap + ask as three roles, (2) Screening→Investigation handoff JSON, (3) `feedback-demo` before/after, (4) eval pass rate, (5) the three 100× failures above, (6) what you'd do with more time (live OFAC sync, stronger entity resolution, human-in-the-loop UI).

---

## Project layout

```
config/roles.yaml          # RBAC source of truth
config/settings.yaml
data/raw/                  # CSV/XLSX/PDF/JSON
data/understanding/        # derived artifacts + feedback
src/ingestion/
src/understanding/
src/rbac/
src/agents/                # screening + investigation + orchestrator
src/feedback/
src/query/cli.py
src/eval/runner.py
eval/eval_set.json
scripts/generate_data.py
scripts/build_understanding.py
```

---

## License / disclaimer

Assignment demo only. Not a production AML system. Synthetic data; not legal advice.
