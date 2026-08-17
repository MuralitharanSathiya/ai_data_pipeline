---
name: silver-gold-sql-generator
description: "DEPRECATED — replaced by dbt-model-generator. Generates pipeline/transformations/silver_<table>.sql and gold_<table>.sql using Snowflake medallion transformation patterns."
---

> **DEPRECATED:** This skill has been replaced by `dbt-model-generator`.
> The `@transformation-agent` and `@table-onboarding` now use `dbt-model-generator`, which
> generates dbt models in `dbt/models/silver/` and `dbt/models/gold/` instead of raw SQL files.
> This file is kept for reference only. Do not invoke this skill for new tables.

# Skill: silver-gold-sql-generator

## Purpose

Generate ready-to-run Silver and Gold transformation SQL files for a specific table.
This skill produces concrete, executable SQL — not a template.

This skill is invoked by **transformation-agent** and **table-onboarding** agent.

For complex transformation rules (joins, JSON flattening, custom aggregations, multi-source),
the **transformation-agent** may reason directly using the `medallion-transform` skill as
a reference instead of using this skill.

------------------------------------------------------------------------

## Inputs Required

| Input | Description | Required |
|---|---|---|
| `TABLE_NAME` | Exact source/bronze table name (e.g. `Orders`) | Yes |
| `TABLE_LOWER` | Lowercase table name (e.g. `orders`) | Yes |
| `PRIMARY_KEY` | Business key column name (e.g. `OrderId`) | Yes |
| `WATERMARK_COLUMN` | Timestamp column for ordering (e.g. `UpdatedAt`) | Yes for incremental; omit for full_refresh |
| `SILVER_BUSINESS_RULES` | Additional filtering or cleaning rules | No |

------------------------------------------------------------------------

## Outputs

Creates two files:

```
pipeline/transformations/silver_<TABLE_LOWER>.sql
pipeline/transformations/gold_<TABLE_LOWER>.sql
```

Example for table `Orders`:
- `pipeline/transformations/silver_orders.sql`
- `pipeline/transformations/gold_orders.sql`

------------------------------------------------------------------------

## Silver SQL Template

Substitute `TABLE_LOWER`, `PRIMARY_KEY`, and `WATERMARK_COLUMN` before writing:

```sql
-- Silver transformation for TABLE_NAME
-- Source:  BRONZE.bronze_TABLE_LOWER
-- Target:  SILVER.silver_TABLE_LOWER
-- Purpose: Deduplicate by PRIMARY_KEY (latest WATERMARK_COLUMN wins), guard null keys

CREATE OR REPLACE TABLE SILVER.silver_TABLE_LOWER AS
WITH ranked AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (
            PARTITION BY b."PRIMARY_KEY"
            ORDER BY b."WATERMARK_COLUMN" DESC
        ) AS rn
    FROM BRONZE.bronze_TABLE_LOWER b
    WHERE b."PRIMARY_KEY" IS NOT NULL
),
cleaned AS (
    SELECT * EXCLUDE (rn)
    FROM ranked
    WHERE rn = 1
)
SELECT * FROM cleaned;
```

Silver guidance:
- `PARTITION BY b."PRIMARY_KEY"` deduplicates by business key.
- `ORDER BY b."WATERMARK_COLUMN" DESC` keeps the most recent version.
- `WHERE b."PRIMARY_KEY" IS NOT NULL` prevents null-key rows from entering Silver.
- `SELECT * EXCLUDE (rn)` drops the row-number helper column (Snowflake syntax).
- If `SILVER_BUSINESS_RULES` were provided, add them as additional WHERE clauses or
  CASE expressions in the `cleaned` CTE, with one comment per rule.

**For full_refresh tables** (no watermark): omit the `ORDER BY b."WATERMARK_COLUMN" DESC`
clause and replace with `ORDER BY 1 DESC` or simply deduplicate without ordering, depending
on the business rule. Document the reasoning with a comment.

------------------------------------------------------------------------

## Gold SQL Template

Substitute `TABLE_LOWER`, `WATERMARK_COLUMN`, and `PRIMARY_KEY` before writing:

```sql
-- Gold transformation for TABLE_NAME
-- Source:  SILVER.silver_TABLE_LOWER
-- Target:  GOLD.gold_TABLE_LOWER
-- Purpose: Analytics-ready daily summary

CREATE OR REPLACE TABLE GOLD.gold_TABLE_LOWER AS
SELECT
    DATE_TRUNC('day', "WATERMARK_COLUMN") AS metric_date,
    COUNT(*)                               AS record_count,
    COUNT(DISTINCT "PRIMARY_KEY")          AS unique_records
FROM SILVER.silver_TABLE_LOWER
GROUP BY 1
ORDER BY 1;
```

Gold guidance:
- Default Gold model is a daily row count — a safe, universal starting point.
- If `SILVER_BUSINESS_RULES` included Gold-layer instructions (dimensions to group by,
  measures to sum), add them as additional SELECT columns and GROUP BY dimensions with comments.
- `CREATE OR REPLACE TABLE` ensures reruns are idempotent.

------------------------------------------------------------------------

## Skill Rules

1. Always create both Silver and Gold files together.
2. Files go in `pipeline/transformations/`, filenames are lowercase.
3. Use `SELECT * EXCLUDE (rn)` — Snowflake native syntax. Do not use a subquery workaround.
4. Use `CREATE OR REPLACE TABLE` for idempotency in both files.
5. Use double-quoted column identifiers (`"ColumnName"`) to preserve case in Snowflake.
6. Include the comment header block (source, target, purpose) at the top of each file.
7. SQL only — no Python, no connection logic in these files.
8. Never hardcode database or schema names beyond `BRONZE`, `SILVER`, `GOLD`.
