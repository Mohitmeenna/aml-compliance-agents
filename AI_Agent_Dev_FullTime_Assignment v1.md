# Tech Round Assignment — AI Agent Developer (Full-Time)

## Overview

Design and build a **working agentic solution** for a bank's **AML / transaction monitoring and regulatory compliance** desk.

The system ingests a large volume of heterogeneous compliance data (regulatory circulars in PDF, transaction ledgers in Excel, sanctions and watchlist files), turns it into something agents can reason over, enforces **role-based access control** in line with who is lawfully allowed to see what, and improves over time through a **feedback loop** driven by analyst dispositions.

A compliance user should be able to ask questions in natural language — *"which transactions this month breach the FATF guidance on correspondent banking?"*, *"summarise the open alerts on this counterparty"* — and the agents should fetch the right data, respect access rules, and carry out the next steps.

The guiding principle: **minimal fluff — the solution should actually work.** A smaller system that runs end-to-end beats an elaborate design that doesn't.

---

## Timeline & Communication

- You have **24 hours** from the time you receive this brief to build, submit, and share a walkthrough.
- **Questions are encouraged — but there's a window.** Email us your questions within **1 hour of receiving this assignment.** Treat scoping and clarifying questions as part of the exercise — asking good questions is a positive signal, not a negative one. Get them in early.
- We'll reply to questions raised inside that first hour as quickly as we can. Questions sent after the window may not get a response before your submission is due.

---

## What to Build

### 1. Data ingestion
- Take real compliance data from **any public source** — e.g. FATF recommendations and guidance notes, RBI / MAS / FCA circulars, FinCEN advisories (PDF), plus a transaction dataset and a sanctions list (Excel / CSV / XML). See **Data** below for pointers.
- Handle **both** formats: structured tabular data (`.xlsx` / `.csv` — transactions, customer master, watchlists) and unstructured or semi-structured documents (`.pdf` — circulars, guidance, policy manuals).
- Convert the raw data into **usable chunks** suitable for retrieval and reasoning. Regulatory documents are hierarchical and cross-referential — how you preserve that structure matters.

### 2. Understanding layer
- Generate **"understanding files"** — derived artifacts (rule summaries, extracted obligations and thresholds, entity-resolved counterparty profiles, metadata, embeddings/index, schema notes) that let agents answer accurately instead of re-parsing raw files every time.
- Be ready to explain what you chose to precompute vs. compute on the fly, and why.

### 3. Role-based access control (RBAC)
- Different roles get different access. Enforce it **at the data layer**, not just in the UI.
- Example rules — design your own role/permission model around these:
  - **Chief Compliance Officer** — full access, including customer PII and filed suspicious-activity reports.
  - **AML Analyst** — sees flagged transactions and alert history, but **masked customer PII** (no full identity documents, no unmasked account holder details).
  - **External Auditor** — sees the audit trail, decisions, and rationale, but **not** raw customer data or the underlying transaction PII.
  - Add at least one more restricted role of your choosing (e.g. a relationship manager scoped to their own portfolio only).
- The agent must **not leak restricted data** to a user who shouldn't see it — including when the answer would require combining restricted and permitted sources, and including via aggregates or inference that reveal a protected value.

### 4. Feedback & learning loop
- Implement a mechanism that lets the agents **learn from adoption**.
- In this domain the natural signal is **alert disposition**: an analyst marks an alert as a true hit, a false positive, or escalates it. Feed that back so future screening and answers improve — retrieval re-ranking, threshold tuning, few-shot memory, eval-driven prompt updates, whatever your design needs.
- Show that feedback **actually changes future behaviour.** Demonstrate a before/after.

### 5. Query interface
- A user should be able to **ask questions in natural language**, and the agents should fetch the relevant data and perform the next steps to answer.
- The interface can be minimal (CLI, simple web UI, notebook) — we care that it works, not that it's pretty.

---

## Additional Requirements (Full-Time Level)

These three are **required**, not bonus.

### A. Multi-agent with a real handoff
Use **at least two agents** with a genuine division of labour and a handoff between them — for example a planner/executor split, a retriever with a separate verifier, or a screening agent feeding an investigation agent. We want to see how you handle orchestration, state passing between agents, and what happens when one agent fails or returns something wrong.

### B. An eval set and a way to run it

Ship 10–15 evaluation questions with expected answers, plus a script that runs them and reports pass/fail. Seed three user profiles — one admin, two non-admins at different permission levels. Role scopes live in config, not prompt text, and are enforced before the model sees the data. Include at least:

One RBAC refusal per profile. A refusal says access was denied without leaking the content.
One question that answers differently by profile.
Two questions needing a regulatory document and transaction data.

We will run this. It should be honest about what currently fails.

### C. A written "what breaks at 100×" section
In your `README`, a short section on what fails when this system goes from your sample dataset to a real bank's volume — millions of transactions a day, thousands of pages of circulars across jurisdictions, hundreds of concurrent users. Be specific: name the component, the failure mode, and what you'd change. We'd rather see three sharp, honest failure modes than a generic list.

---

## Bonus (not required, but rewarded)

- **Prompt injection handling** — defend against malicious instructions embedded in the ingested data or in user input. Note that this is a live attack surface in this domain: free-text fields such as wire transfer remittance information, payment narratives, and counterparty names are attacker-controlled and flow straight into your pipeline.

---

## Data

- Use **public sources only.** Suggested starting points:
  - **Regulatory / guidance (PDF)** — FATF Recommendations and guidance notes, FinCEN advisories, RBI Master Directions on KYC/AML, MAS Notice 626, Wolfsberg Group principles.
  - **Sanctions / watchlists** — OFAC SDN list, UN Consolidated List, EU consolidated sanctions list (all publicly downloadable, structured).
  - **Transactions** — any public or synthetic AML transaction dataset (e.g. PaySim, IBM's synthetic AML dataset), or generate your own synthetic ledger. Say clearly in your README which you used.
- Do **not** use any real customer data, real PII, or any internal or confidential data from a current or former employer. Synthetic customer data is expected and fine.

---

## Deliverables

1. **Working code** — a repository (GitHub or zip) we can run. Include a `README` with setup and run instructions, your **"what breaks at 100×"** section, and any keys/config we need to supply.
2. **The eval set and its runner script**, with a note on current pass rate.
3. **A walkthrough** — either a recorded video (5–10 min) **or** a live walkthrough on the evaluation call. Cover: what you built, how the agents divide work, what you'd do differently with more time, and where it breaks at scale.
4. Any understanding files / indexes your system generates (or a script that regenerates them).

Submit the repo/zip link and walkthrough (or a note that you'll present live) by email within the 24-hour window.

---

## Evaluation Criteria

| Weight | Criterion | How it's judged |
|---|---|---|
| **50%** | **Working solution** | Does it run end-to-end? Ingest → understand → answer → enforce RBAC → feedback. Your eval set is part of this. |
| **25%** | **Architecture clarity & understanding** | Assessed during the walkthrough call — can you explain your design, your agent boundaries, and defend your choices? |
| **15%** | **Ability to distinguish what fails at scale** | Assessed on your written section **and** the walkthrough — what breaks at 100× the data / users, and why? |
| **5%** | **Creativity** | Clever FE/BE hacks, elegant shortcuts, thoughtful UX. |
| **5%** | **Communication** | Clarity of README, walkthrough, and email questions. |

A note on the split: half the score is simply **does it work.** Prioritize a running end-to-end system over breadth of features.

---

## Ground Rules

- Use any language, framework, model, or library you like.
- AI coding tools are allowed — but you must be able to **explain every part** of what you submit during the walkthrough.
- Scope aggressively. Within 24 hours, it's better to fully finish ingestion + RBAC + a working two-agent flow + a small honest eval set than to half-build everything.
- You are not expected to be an AML expert. We are evaluating your agent engineering, not your compliance knowledge — the domain is here because it has genuinely hard data, access, and scale problems. Ask if a regulatory concept is unclear.

Good luck — and get your questions to us within the first hour.
