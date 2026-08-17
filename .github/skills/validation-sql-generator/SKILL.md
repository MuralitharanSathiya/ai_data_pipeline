---
name: validation-sql-generator
description: "DEPRECATED — replaced by dbt-test-generator. Generates pipeline/validation/<table>_tests.sql with four standard data quality checks across Bronze and Silver layers."
---

> **DEPRECATED:** This skill has been replaced by `dbt-test-generator`.
> The `@data-quality-agent` and `@table-onboarding` now use `dbt-test-generator`, which
> appends test blocks to `dbt/models/silver/schema.yml` and `dbt/models/gold/schema.yml`
> and creates singular test files in `dbt/tests/`.
> This file is kept for reference only. Do not invoke this skill for new tables.

# Skill: validation-sql-generator

## Purpose

Generate a per-table validation SQL file containing four standard data quality checks
across Bronze and Silver layers.

Each check is a standalone SELECT that returns zero rows on PASS and non-zero rows on
FAIL — compatible with manual execution in Snowflake Worksheets and CI assertion patterns.

This skill is invoked by **data-quality-agent** and **table-onboarding** agent.

------------------------------------------------------------------------

## Inputs Required

| Input | Description | Required |
|---|---|---|
| `TABLE_NAME` | Exact table name (e.g. `Orders`) | Yes |
| `TABLE_LOWER` | Lowercase table name (e.g. `orders`) | Yes |
| `PRIMARY_KEY` | Primary key column name (e.g. `OrderId`) | Yes |
| `WATERMARK_COLUMN` | Watermark timestamp column (e.g. `UpdatedAt`) | Yes for incremental; omit CHECK_4 for full_refresh |

------------------------------------------------------------------------

## Output

Creates one file:

```
pipeline/validation/<TABLE_LOWER>_tests.sql
```

Example: `pipeline/validation/orders_tests.sql`

**Do NOT write to `pipeline/validation/tests.sql`** — per-table files prevent merge conflicts
and enable per-table CI execution.

------------------------------------------------------------------------

## Validation SQL Template

Substitute `TABLE_NAME`, `TABLE_LOWER`, `PRIMARY_KEY`, and `WATERMARK_COLUMN` before writing.

```sql
-- Validation tests for TABLE_NAME
-- Run each check independently.
-- Each query returns 0 rows on PASS, >0 rows on FAIL.
-- Source bronze:  BRONZE.bronze_TABLE_LOWER
-- Source silver:  SILVER.silver_TABLE_LOWER

------------------------------------------------------------------------
-- CHECK 1: Row count
-- Silver must not have MORE rows than Bronze (dedup makes Silver <= Bronze).
-- FAIL: Silver has more rows than Bronze — indicates missing dedup logic.
------------------------------------------------------------------------
SELECT
    'CHECK_1_ROW_COUNT'                 AS check_name,
    bronze_count,
    silver_count,
    (silver_count - bronze_count)       AS row_delta,
    'FAIL'                              AS result
FROM (
    SELECT
        (SELECT COUNT(*) FROM BRONZE.bronze_TABLE_LOWER) AS bronze_count,
        (SELECT COUNT(*) FROM SILVER.silver_TABLE_LOWER) AS silver_count
)
WHERE silver_count > bronze_count;

------------------------------------------------------------------------
-- CHECK 2: Duplicate detection
-- Silver must have no duplicate PRIMARY_KEY values after deduplication.
-- FAIL: any PRIMARY_KEY appears more than once in Silver.
------------------------------------------------------------------------
SELECT
    'CHECK_2_SILVER_DUPLICATES'  AS check_name,
    "PRIMARY_KEY"                AS duplicate_key,
    COUNT(*)                     AS occurrence_count
FROM SILVER.silver_TABLE_LOWER
GROUP BY "PRIMARY_KEY"
HAVING COUNT(*) > 1;

------------------------------------------------------------------------
-- CHECK 3: Null primary key
-- Bronze must have no NULL PRIMARY_KEY rows.
-- FAIL: any NULL PRIMARY_KEY found in Bronze.
------------------------------------------------------------------------
SELECT
    'CHECK_3_NULL_PRIMARY_KEY'  AS check_name,
    COUNT(*)                    AS null_key_count
FROM BRONZE.bronze_TABLE_LOWER
WHERE "PRIMARY_KEY" IS NULL
HAVING COUNT(*) > 0;

------------------------------------------------------------------------
-- CHECK 4: Watermark coverage
-- Silver max WATERMARK_COLUMN must equal Bronze max WATERMARK_COLUMN.
-- FAIL: Silver max watermark is older than Bronze — records may have been dropped.
------------------------------------------------------------------------
SELECT
    'CHECK_4_WATERMARK_COVERAGE'                              AS check_name,
    bronze_max_watermark,
    silver_max_watermark,
    'FAIL'                                                    AS result
FROM (
    SELECT
        (SELECT MAX("WATERMARK_COLUMN") FROM BRONZE.bronze_TABLE_LOWER) AS bronze_max_watermark,
        (SELECT MAX("WATERMARK_COLUMN") FROM SILVER.silver_TABLE_LOWER) AS silver_max_watermark
)
WHERE silver_max_watermark < bronze_max_watermark;
```

------------------------------------------------------------------------

## Notes on full_refresh Tables

For `full_refresh` tables with no watermark column:
- **Omit CHECK_4** entirely (no watermark to compare).
- Add a comment: `-- CHECK_4 skipped: table uses full_refresh strategy (no watermark column)`.
- Checks 1, 2, and 3 still apply.

------------------------------------------------------------------------

## Skill Rules

1. Create one file per table in `pipeline/validation/`, named `<TABLE_LOWER>_tests.sql`.
2. Never write to `pipeline/validation/tests.sql`.
3. Each check must be a standalone SELECT — no stored procedures or scripts.
4. Every check includes a `check_name` string column for self-describing output.
5. Checks return zero rows on PASS and non-zero rows on FAIL.
6. Include the check number, description, and fail condition as a comment block above each SELECT.
7. Use double-quoted identifiers for column names to preserve case in Snowflake.
8. Omit CHECK_4 for `full_refresh` tables and replace with the skip comment.
