# AGENTS.md

## Project Overview

This repository implements a data ingestion and transformation pipeline that extracts data from Azure SQL Server and loads it into Snowflake.

The pipeline is implemented in Python and follows a Medallion architecture consisting of Bronze, Silver, and Gold data layers.

The pipeline supports incremental data ingestion and modular transformation workflows designed for reliability, scalability, and maintainability.


## Agents

| Agent | Invoke as | Purpose |
|-------|-----------|---------|
| `pipeline-architect` | `@pipeline-architect` | DISCOVER — maps a business use case to source tables, PKs, strategies, and a ready-to-run onboarding command |
| `table-onboarding` | `@table-onboarding` | Primary entry point — all-in-one onboarding for a single table |
| `multi-table-onboarding` | `@multi-table-onboarding` | Batch onboarding for 2–5 tables in one command |
| `connection-tester` | `@connection-tester` | Pre-flight SQL Server + Snowflake connectivity check (read-only) |
| `ingestion-agent` | `@ingestion-agent` | Regenerate ingestion script only |
| `transformation-agent` | `@transformation-agent` | dbt Silver/Gold model generation |
| `data-quality-agent` | `@data-quality-agent` | dbt tests — schema.yml + singular SQL tests |
| `source-explorer` | `@source-explorer` | Read-only source data model explorer |
| `code-review` | `@code-review` | Code quality gate — 10 Python rules + 6 dbt rules |

> Keep this table in sync with the Copilot Agents table in `CLAUDE.md`.


## Architecture

- **Source System**: Azure SQL Server
- **Processing Layer**: Python-based ETL pipelines
- **Target Platform**: Snowflake Data Cloud
- **Data Architecture**: Medallion Architecture (Bronze → Silver → Gold)
- **Transformations**: dbt with Snowflake adapter

### Data Layers

- **Bronze**: Raw ingestion from source systems with minimal transformation
- **Silver**: Cleaned and standardized data including deduplication, normalization, and type standardization
- **Gold**: Analytics-ready data models optimized for reporting and business intelligence


## Dev Environment

- **Language**: Python 3.10+
- Install dependencies: `pip install -r requirements.txt`
- Copy `.env.example` to `.env` and populate credentials (never commit `.env`)
- Configuration lives in `pipeline/config.yaml` — connection details (non-secret) and table definitions
- dbt project is under `dbt/` — always run via `./dbt_run.sh` (auto-loads `.env`), never bare `dbt`

### Primary Libraries

- `pymssql` for Azure SQL Server connectivity
- `pandas` for data processing
- `snowflake-connector-python[pandas]` for Snowflake ingestion
- `dbt-snowflake` for transformations


## Repository Structure

```
pipeline/
  config.yaml              # Source/target config + table list
  ingestion/               # Per-table Python ingestion scripts
    ingest_template.py     # Canonical template — all scripts derived from this
  utils/                   # Shared modules (config_loader, database_client, extractor, snowflake_loader, local_state)
  state/                   # Watermark JSON files for incremental ingestion

dbt/
  models/silver/           # Silver dbt models (dedup)
  models/gold/             # Gold dbt models (aggregation)
  models/sources.yml       # Bronze source definitions
  tests/                   # Singular dbt test files
  macros/                  # Custom macros (generate_schema_name)

.github/
  agents/                  # Custom Copilot agent definitions (.agent.md)
  skills/                  # Reusable skill definitions (SKILL.md per folder)
  copilot-instructions.md  # Copilot-specific agent workflow instructions
```


## Coding Standards

All generated pipeline code must follow these rules. They are enforced by the `@code-review` agent.

### Python Rules

- Functions only — no classes except `Exception` subclasses
- No wrapper functions (functions that only call one other function)
- No nested function definitions
- All imports at the top of the file — never inside functions
- No defensive coding for impossible scenarios (trust internal module contracts)
- Functions are ≤ ~50 lines and serve a single clearly-named purpose
- No duplicated logic — extract to a shared utility if the same pattern appears twice
- Parameterized SQL only — no f-string or string-concatenation SQL queries
- Config loaded via `pipeline.utils.config_loader` only — never raw `open()` + `yaml.safe_load()`
- Never hardcode credentials, server names, or database names
- Match the structure of `pipeline/ingestion/ingest_template.py`
- The `importlib.import_module` pattern in ingestion scripts is intentional — preserve it
- Include docstrings for all functions
- Use type hints where appropriate
- Log pipeline start/end events and record counts

### dbt Rules

- Every model must start with `{{ config(materialized=...) }}`
- No hardcoded schema or database identifiers — use `{{ source() }}` and `{{ ref() }}`
- Silver models read from Bronze via `{{ source('bronze', 'bronze_<table>') }}`
- Gold models read from Silver via `{{ ref('silver_<table>') }}`
- Schema routing is handled by `generate_schema_name.sql` macro — never prefix schemas manually
- Singular tests in `dbt/tests/` follow the 0 rows = PASS convention


## Snowflake Development Standards

### Schemas

- `BRONZE` — raw ingested data
- `SILVER` — cleaned and deduplicated
- `GOLD` — analytics-ready aggregates

### Naming Conventions

- `bronze_<table_name>`
- `silver_<table_name>`
- `gold_<table_name>`

### SQL Conventions

- Double-quoted identifiers for column names to preserve case (`"ColumnName"`)
- Use `SELECT * EXCLUDE (rn)` — Snowflake-native syntax
- Transformations must be deterministic
- Pipelines must be idempotent
- Use MERGE statements for incremental updates


## Ingestion Patterns

### Incremental Tables

- Watermark-based extraction: `WHERE watermark_column > last_processed_timestamp`
- MERGE upsert into Bronze via staging table
- Watermark state stored in `pipeline/state/<table>_watermark.json`
- Watermark is written only after successful load (fail-safe retry)
- First run with no watermark state performs a full initial load automatically

### Full Refresh Tables

- Full extract from source
- TRUNCATE + INSERT into Bronze (via staging table)
- No watermark state management

### Incremental SQL Pattern

```sql
SELECT *
FROM source_table
WHERE updated_at > :last_processed_timestamp
```


## Data Pipeline Design Principles

- **Configuration Driven**: Pipeline behavior controlled via `config.yaml`
- **Modular**: Separate ingestion, transformation, and validation stages
- **Idempotent**: Pipelines are safe to re-run without creating duplicates
- **Observable**: Log key pipeline events, record counts, and processing metrics
- **Fail-Safe**: Watermark only advances after successful load — failed runs re-extract from last checkpoint


## Security

- Credentials must never be hardcoded in any file
- Connection details (non-secret) live in `pipeline/config.yaml`
- Credentials only in `.env` (gitignored) or secret managers
- `.env.example` is the credential template — never contains real values


## Testing

- dbt schema tests: `unique` + `not_null` on primary keys
- Singular tests in `dbt/tests/`: row count check (Silver ≤ Bronze), watermark coverage check
- Run tests: `./dbt_run.sh test --project-dir dbt --select <model_name>`
- Run code quality review: `@code-review Review <filepath>`