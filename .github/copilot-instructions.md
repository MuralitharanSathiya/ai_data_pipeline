# Copilot Agent Workflow

> **Project standards, coding rules, and architecture details are in `AGENTS.MD` at the repo root.**
> This file covers Copilot-specific agent and skill usage only.


## AI Agent System

This repository uses GitHub Copilot custom agents (`.github/agents/`) and skills (`.github/skills/`) to automate pipeline development.

Agents should reuse existing skills and configuration files whenever possible.
Agents should prefer using existing skills rather than generating logic from scratch.


## Agents

| Agent | Role |
|---|---|
| `@table-onboarding` | Primary entry point — one command generates all artifacts for a new table |
| `@multi-table-onboarding` | Batch onboarding for up to 5 tables in one command |
| `@connection-tester` | Pre-flight validation of SQL Server + Snowflake connectivity (read-only) |
| `@ingestion-agent` | Regenerate just the ingestion script for an existing config entry |
| `@transformation-agent` | Generate or update Silver/Gold dbt models |
| `@data-quality-agent` | Generate dbt validation tests |
| `@code-review` | Post-generation quality gate — 10 Python rules + 6 dbt rules |
| `@pipeline-architect` | DISCOVER — paste a business use case; agent maps it to source tables, technical details, and a ready-to-run onboarding command |


## Skills

Skills represent reusable data engineering capabilities invoked by agents.

| Skill | Used By | What It Generates |
|---|---|---|
| `pipeline-bootstrap` | table-onboarding | 5 shared utility Python modules + directory structure (idempotent) |
| `dbt-bootstrap` | table-onboarding | dbt project structure + `dbt_run.sh` wrapper (idempotent) |
| `config-generator` | table-onboarding | `pipeline/config.yaml` (append mode) + `.env.example` |
| `ingest-script-generator` | ingestion-agent | Substitutes markers in `ingest_template.py` → `ingest_<table>.py` |
| `dbt-model-generator` | transformation-agent | Silver (dedup) + Gold (aggregation) dbt models + `sources.yml` entry |
| `dbt-test-generator` | data-quality-agent | `schema.yml` test blocks + singular SQL test files |
| `incremental-extraction` | Reference | Watermark-based extraction patterns |
| `medallion-transform` | Reference | Bronze/Silver/Gold transformation patterns |
| `snowflake-loader` | Reference | MERGE upsert and TRUNCATE+INSERT patterns |
| `sqlserver-connection` | Reference | SQL Server connection and parameterized query patterns |


------------------------------------------------------------------------

## Quick Start: Onboarding a New Table

### Pre-flight check (optional but recommended)

```
@connection-tester Test connections for Orders
```

Validates SQL Server + Snowflake credentials before generating files.

### Full onboarding — incremental table

```
@table-onboarding Onboard table Orders from rs schema, primary key OrderId, watermark UpdatedAt
```

### Full onboarding — full refresh table (no watermark)

```
@table-onboarding Onboard table DimProduct from rs schema, primary key ProductId, strategy full_refresh
```

### With Silver/Gold business rules

```
@table-onboarding Onboard table Orders from rs schema, primary key OrderId, watermark UpdatedAt.
Silver: filter out rows where status = 'CANCELLED'.
Gold: group by CustomerRegion and sum TotalAmount.
```

### Generated artifacts

| File | Purpose |
|---|---|
| `pipeline/config.yaml` | Table entry appended (source/target sections preserved) |
| `.env.example` | Credential placeholder template (created if not exists) |
| `pipeline/ingestion/ingest_orders.py` | Run with `python pipeline/ingestion/ingest_orders.py` |
| `dbt/models/silver/silver_orders.sql` | Silver dbt model (dedup by PK, latest watermark wins) |
| `dbt/models/gold/gold_orders.sql` | Gold dbt model (daily aggregation) |
| `dbt/models/silver/schema.yml` | Silver dbt tests (unique + not_null on PK) |
| `dbt/models/gold/schema.yml` | Gold dbt tests (not_null + unique on metric_date) |
| `dbt/tests/silver_orders_row_count.sql` | Row count check: Silver ≤ Bronze (0 rows = PASS) |
| `dbt/tests/silver_orders_watermark_coverage.sql` | Watermark coverage check (incremental only) |
| `dbt/models/sources.yml` | Bronze source entry appended |
| `pipeline/state/orders_watermark.json` | Auto-created on first incremental run |

### After onboarding

```bash
# 1. Populate credentials
cp .env.example .env
# Edit .env: set AZURE_SQL_USER, AZURE_SQL_PASSWORD, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD

# 2. Run ingestion (Bronze layer)
python pipeline/ingestion/ingest_orders.py

# 3. Run Silver + Gold transformations and tests (all in one command)
./dbt_run.sh build --project-dir dbt --select silver_orders gold_orders

# Note: always use ./dbt_run.sh — it auto-loads .env before invoking dbt.
# Bare 'dbt build' will fail with "Env var required but not provided: SNOWFLAKE_USER".
```

### Code quality review (after generation)

```
@code-review Review pipeline/ingestion/ingest_orders.py
```


------------------------------------------------------------------------

## Individual Agents (for targeted re-generation)

| Agent | Use When |
|---|---|
| `@ingestion-agent` | Regenerate just the ingestion script for an existing config entry |
| `@transformation-agent` | Regenerate or update Silver/Gold dbt models |
| `@data-quality-agent` | Regenerate or add validation checks |
| `@pipeline-architect` | DISCOVER — paste a business use case; agent maps it to source tables, technical details, and a ready-to-run onboarding command |
| `@code-review` | Review any generated Python or dbt file against quality standards |