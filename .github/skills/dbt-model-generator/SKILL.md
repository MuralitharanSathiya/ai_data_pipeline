# Skill: dbt-model-generator

## Purpose

Generate standard Silver and Gold dbt models for a newly onboarded table. This is the **standard onboarding path** — it produces the starter dedup (Silver) and daily aggregation (Gold) models. For custom business logic on top of these starters, the `@transformation-agent` reasons directly.

---

## When to Use

Invoked by `@transformation-agent` during standard table onboarding (called from `@table-onboarding`):

```
@transformation-agent Generate dbt models for Orders, primary key OrderId, watermark UpdatedAt
```

---

## Inputs

| Input | Description | Required |
|-------|-------------|----------|
| TABLE_NAME | Exact table name as in source (e.g., `Orders`) | Yes |
| TABLE_LOWER | Lowercase (e.g., `orders`) | Yes |
| PRIMARY_KEY | Business key column (e.g., `OrderId`) | Yes |
| WATERMARK_COLUMN | Timestamp column for ordering (e.g., `UpdatedAt`) | Yes (incremental) / No (full_refresh) |
| INGESTION_STRATEGY | `incremental` or `full_refresh` | Yes |

---

## Outputs

1. `dbt/models/silver/silver_<TABLE_LOWER>.sql`
2. `dbt/models/gold/gold_<TABLE_LOWER>.sql`
3. Append source table entry to `dbt/models/sources.yml`

---

## Silver Model Pattern

```sql
{{ config(materialized='table') }}

-- Silver: TABLE_NAME
-- Source: {{ source('bronze', 'bronze_TABLE_LOWER') }}
-- Purpose: Deduplicate by PRIMARY_KEY (latest WATERMARK_COLUMN wins), guard null keys

WITH ranked AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (
            PARTITION BY b."PRIMARY_KEY"
            ORDER BY b."WATERMARK_COLUMN" DESC
        ) AS rn
    FROM {{ source('bronze', 'bronze_TABLE_LOWER') }} b
    WHERE b."PRIMARY_KEY" IS NOT NULL
),
cleaned AS (
    SELECT * EXCLUDE (rn)
    FROM ranked
    WHERE rn = 1
)
SELECT * FROM cleaned
```

**For `full_refresh` tables** (no watermark): replace `ORDER BY b."WATERMARK_COLUMN" DESC` with `ORDER BY b."PRIMARY_KEY" ASC` for deterministic tie-breaking.

---

## Gold Model Pattern

```sql
{{ config(materialized='table') }}

-- Gold: TABLE_NAME
-- Source: {{ ref('silver_TABLE_LOWER') }}
-- Purpose: Analytics-ready daily summary

SELECT
    DATE_TRUNC('day', "WATERMARK_COLUMN") AS metric_date,
    COUNT(*)                               AS record_count,
    COUNT(DISTINCT "PRIMARY_KEY")          AS unique_records
FROM {{ ref('silver_TABLE_LOWER') }}
GROUP BY 1
ORDER BY 1
```

**For `full_refresh` tables** (no watermark): omit `DATE_TRUNC` grouping; use `COUNT(*)` and `COUNT(DISTINCT "PRIMARY_KEY")` without date dimension, or ask the developer what aggregation dimension makes sense.

---

## sources.yml Append

After generating the model files, append a new table entry to `dbt/models/sources.yml` under the `bronze` source's `tables:` list. Read the existing file first — do not overwrite it, only append.

```yaml
      - name: bronze_TABLE_LOWER
```

If `sources.yml` does not exist yet, `dbt-bootstrap` must be run first.

---

## Skill Rules

1. Always generate both Silver and Gold files together
2. Use `{{ source('bronze', 'bronze_<table_lower>') }}` for Bronze — never hardcode `BRONZE.bronze_<table>`
3. Use `{{ ref('silver_<table_lower>') }}` for Silver → Gold — never hardcode `SILVER.silver_<table>`
4. No `CREATE OR REPLACE TABLE` — dbt handles materialization via `{{ config() }}`
5. Double-quoted identifiers: `"ColumnName"` (Snowflake preserves case)
6. Use `SELECT * EXCLUDE (rn)` — Snowflake-native syntax to drop the ranking column
7. Include comment header (source, purpose) in each model
8. SQL only — no Python or connection logic in model files
9. Append to `sources.yml` — check for existing entry first to avoid duplicates
