# Submission Form — Copy-Paste Answers

Answers for every field in the Hacker House Goa submission form. Replace the
`[...]` placeholders with your real links after publishing/recording.

---

## Public GitHub repo URL

```
https://github.com/ananditaa2/HHGOA_task04
```

## My repo has all 20 answer files in cases/, named exactly as in case_pack.csv

✅ **Yes** — verified: all 20 files (`HHG-001.json` … `HHG-020.json`) are on
`main` in the `cases/` folder, one per case-pack row, schema-validated
(100% QA audit pass) before the push.

## Demo video URL (3–5 min)

`[PASTE-YOUR-YOUTUBE-LINK-HERE]`

- Record using `submission_docs/DEMO_SCRIPT.md` (scene-by-scene script with timings).
- Upload to YouTube as **Unlisted**, publish, paste the link.
- Suggested free recording: OBS Studio or the Windows Game Bar (`Win+G`).

## Live UI URL (optional)

Optional — safe to leave blank. If you want it:

- Easiest: deploy the Streamlit app to https://share.streamlit.io
  (repo: `ananditaa2/HHGOA_task04`, main file: `app/streamlit_app.py`).
  Note: the UI works without `transactions.csv`, but per-case investigations
  need it — either include a trimmed copy or demo from the case JSON cache.
- Or skip the field; it is optional and the video covers the UI.

## LLM model used

```
No LLM is required for the core pipeline: verdicts, graph evidence, conflict
scoring, policy routing, and SAR narratives are produced by deterministic
rule + graph reasoning over TigerGraph, so results are reproducible offline.
An optional OpenAI-compatible call (default model: gpt-4o-mini, configurable
via NARRATIVE_LLM_MODEL) polishes the analyst narrative only when
NARRATIVE_LLM_ENABLED=true; otherwise a deterministic fallback narrative is
generated. Every deterministic output was used for the 20 scored case files.
```

## Agent framework used

```
Custom multi-agent orchestration built from scratch (no LangChain/CrewAI):
an InvestigationCoordinator runs six cooperating agents — Graph Detective,
Evidence Conflict Evaluator, Devil's Advocate (adversarial critic), Evidence
Simulator, Policy Engine (policy rules R1–R10 traversed as a graph), and an
Analyst Narrative Agent. Agents access the graph through a unified adapter
(live TigerGraph / in-memory fallback) and a TigerGraph MCP server exposing
7 tools conforming to the official tigergraph-mcp spec.
```

## Social post URLs

`[PASTE-EACH-TEAM-MEMBER'S-POST-LINK-HERE, one per line]`

- Ready-made content: `submission_docs/SOCIAL_POST.md` (X/Twitter thread +
  LinkedIn post — copy, personalize, post).
- **Must tag @TigerGraphDB and @247pmstudio** on every post.
- Every team member posts their own; paste all links in the field.

## Technical blog URL

`[PASTE-YOUR-PUBLISHED-BLOG-LINK-HERE]`

- The full article is written: `submission_docs/BLOG_POST.md`.
- Publish on Medium, dev.to, Hashnode, or as a LinkedIn Article, then paste
  the link. (Tip: dev.to/Medium render the mermaid diagram and formulas well.)

## How was your experience with TigerGraph?

```
What worked well: modeling the domain AND the policy as a graph was the
highlight — fraud rules R1–R10 are vertices with OVERRIDES and ESCALATES_TO
edges, so next-best-action becomes a graph traversal instead of nested
if/else. GSQL accumulators made the card-testing and device-ring centrality
algorithms concise, and REST++ upserts let us stream the benchmark CSVs into
FraudGraph in bounded batches via scripts/deploy_tigergraph.py.

What was confusing or slow: first-time setup — REST++ vs GSQL-server ports
behave differently between Savanna cloud hosts (443) and local Community
Edition (9000/14240), and token/secret management took some trial and error.
We handled it in the client by deriving ports from TG_HOST.

What we wish existed: native vector similarity search on vertex attributes
(we built a pluggable embedding store over the 5,565 closed cases and would
love to push it into the graph), and a single one-command flow that installs
schema + loading job + queries and reports per-phase failures.
```

*(Adjust details to match what you actually ran — this draft reflects the repo as built.)*

## Anything else you want to tell us?

```
Engineering quality highlights beyond the 20 case files:
- 8-test pytest suite (loaders, agents, schema validator, SAR/verdict
  consistency, MCP tools, vector retrieval) — all passing.
- Post-run QA audit: 100% pass across all 6 audit vectors on the 20 files.
- Vector precedent retrieval: all 5,565 closed cases embedded and ranked by
  cosine similarity, satisfying the graph + vector storage/retrieval item.
- Live investigation: GET /api/investigate/{txn_id} runs the full agent
  pipeline on demand on any flagged transaction.
- Honest limitations section in the README (simulated customer responses,
  embedding approach, deployment prerequisites).
```

## TigerGraph deployment: Savanna / Community Edition

Pick **based on what you actually ran**:

- Created a free-tier instance at tgcloud.io and ran
  `python scripts/deploy_tigergraph.py --stream --activate` against it → **Savanna**
- Ran TigerGraph CE locally (Docker) and deployed there → **Community Edition**
- If you haven't deployed to a live instance yet, do that first (free Savanna
  tier takes ~5 minutes to spin up), then answer honestly.
