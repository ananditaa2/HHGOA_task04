# TigerDetect

## Graph-native fraud investigation for Hacker House Goa

TigerDetect is an explainable fraud investigation platform built for the Hacker House Goa IEEE-CIS investigation challenge. It combines graph evidence, closed-case precedent retrieval, deterministic policy reasoning, simulated evidence collection, SAR generation, and a live analyst workbench.

**Demo video:** [Watch the TigerDetect demo on YouTube](https://youtu.be/kthpoFhrTHw)

**Repository:** [github.com/ananditaa2/HHGOA_task04](https://github.com/ananditaa2/HHGOA_task04)

## What It Does

For each benchmark alert, TigerDetect:

- Investigates the customer, card, transaction, device, region, and connected activity.
- Detects card testing, card-not-present anomalies, new-device activity, out-of-region use, and shared-origin rings.
- Compares evidence against 5,565 closed investigations.
- Challenges fraud conclusions with a Devil's Advocate critic.
- Requests and simulates customer or analyst evidence.
- Produces initial and final next-best actions with `auto`, `L1`, or `L2` approval routes.
- Generates a regulatory SAR when policy requires it.
- Writes the investigation into graph case memory.
- Validates all 20 answer files against the required format.

## Architecture

```text
CSV data and case pack
        |
        v
RealDataStore --> GraphAdapter --> TigerGraph Savanna
                      |                  |
                      |                  +-- GSQL queries and graph storage
                      +-- In-memory fallback
                      +-- Local vector precedent index
        |
        v
InvestigationCoordinator
        |
        +-- Graph Detective
        +-- Conflict Evaluator
        +-- Devil's Advocate Critic
        +-- Evidence Simulator
        +-- Policy Engine
        +-- Optional Narrative Agent
        |
        v
Case record + SAR + next-best actions
```

The agent framework is custom Python orchestration using Pydantic state objects. It does not require LangChain, LangGraph, CrewAI, or AutoGen.

The official `tigergraph-mcp` package is supported as a separate MCP server. The app accepts its connection names directly: `TG_HOST`, `TG_SECRET`, and `TG_GRAPHNAME`. Legacy `TG_GRAPH` and `TG_API_TOKEN` names are also supported.

The scored pipeline is deterministic and does not require an LLM. An optional OpenAI-compatible call using `gpt-4o-mini` can polish the analyst narrative only.

## Quick Start

From the repository root:

```powershell
pip install -r requirements.txt
pytest -q
python scripts/run_all_cases.py
python -m uvicorn app.web_app:app --host 127.0.0.1 --port 8001
```

Open the API at [http://127.0.0.1:8001](http://127.0.0.1:8001).

The Streamlit analyst workbench can be started with:

```powershell
streamlit run app/streamlit_app.py
```

## API Endpoints

- `GET /api/system/status` - backend and graph connection status.
- `GET /api/cases` - all 20 benchmark case summaries.
- `GET /api/case/{case_id}` - complete case details and graph visualization data.
- `GET /api/investigate/{txn_id}` - run the full pipeline for a flagged transaction.
- `POST /api/investigate` - run a custom sandbox investigation.
- `GET /api/qa_audit` - run the 20-case conformance audit.

Example:

```text
http://127.0.0.1:8001/api/investigate/3514030
```

## TigerGraph Savanna Deployment

Create or start a Savanna workspace with a graph named `FraudGraph`. Use the workspace's **Connect** panel to obtain the instance endpoint. Do not use the portal URL `https://savanna.tgcloud.io` as `TG_HOST`.

Create a local `.env` file and set:

```env
GRAPH_BACKEND_MODE=tigergraph
TG_HOST=https://your-instance.i.tgcloud.io
TG_GRAPH=FraudGraph
TG_API_TOKEN=your_database_secret
# Official MCP aliases may be used instead:
# TG_GRAPHNAME=FraudGraph
# TG_SECRET=your_database_secret
```

Keep `.env` private. It is ignored by Git.

Preview the deployment:

```powershell
python scripts/deploy_tigergraph.py --dry-run
```

Install the schema and queries, stream the real graph data, run smoke tests, and activate the live backend:

```powershell
python scripts/deploy_tigergraph.py --stream --activate
```

The deployment script installs `gsql/schema.gsql`, `gsql/load_job.gsql`, and `gsql/fraud_queries.gsql`. It streams the graph vertices and relationships built from the available local benchmark CSVs. The workspace must be active and the API token must have graph write permissions.

To run the official MCP server for Cursor or another MCP client:

```powershell
uvx tigergraph-mcp
```

Configure that MCP server with the same `TG_HOST`, `TG_SECRET`, and `TG_GRAPHNAME` values. Never commit those values.

Verify the connection:

```text
http://127.0.0.1:8001/api/system/status
```

Expected live status:

```json
{
  "engine": "TigerGraph Savanna",
  "is_live_connected": true
}
```

If TigerGraph is unavailable, the adapter uses the in-memory fallback so local development and tests continue to work.

## Optional Narrative LLM

The core verdicts and case files are deterministic. To enable optional narrative generation, add the following to `.env`:

```env
NARRATIVE_LLM_ENABLED=true
OPENAI_API_KEY=your_key
NARRATIVE_LLM_MODEL=gpt-4o-mini
```

You can point `NARRATIVE_LLM_URL` at another OpenAI-compatible endpoint. The application falls back to a deterministic narrative if the key is absent or the request fails.

## Data

The benchmark data is not fully stored in GitHub because `transactions.csv` is larger than GitHub's 100 MB file limit. Place the provided files beside this README:

- `transactions.csv`
- `identity.csv`
- `closed_cases_history.csv`
- `case_pack.csv`

Do not use the original public IEEE-CIS/Kaggle files to recover outcomes. The benchmark IDs, times, and amounts are transformed for this challenge.

## Tests and QA

Run the tests with:

```powershell
pytest -q
```

The suite covers loaders, vector retrieval, coordinator output, schema validation, SAR consistency, narrative fallback, MCP tools, and deployment dry-run behavior.

The existing QA audit validates all 20 generated case files across schema, verdict arithmetic, SAR consistency, recommendation evolution, and policy-rule citations:

```powershell
python scripts/qa_audit.py
```

## Project Guide

- [Full assignment and fraud policy](README%20(2).md)
- [Deployment script](scripts/deploy_tigergraph.py)
- [FastAPI server](app/web_app.py)
- [Streamlit workbench](app/streamlit_app.py)
- [Agent coordinator](src/agents/coordinator.py)
- [TigerGraph schema](gsql/schema.gsql)
- [GSQL analytical queries](gsql/fraud_queries.gsql)
- [Demo script](submission_docs/DEMO_SCRIPT.md)
- [Submission answers](submission_docs/FORM_ANSWERS.md)

## Limitations

- Customer and analyst replies are deterministic simulations unless an external evidence provider is added.
- Local precedent retrieval uses dependency-free hashed-token vectors; native TigerGraph vector search is not required for local operation.
- Live deployment requires an active Savanna workspace, a correct instance endpoint, and a valid database secret.
- Continuous monitoring beyond the 20 benchmark cases is not enabled by default.
