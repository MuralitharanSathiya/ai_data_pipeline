# Skill: dbt-test-generator

## Purpose

Generate dbt test definitions for a newly onboarded table. Appends model test blocks to `schema.yml` files in `dbt/models/silver/` and `dbt/models/gold/`. Also creates singular test SQL files in `dbt/tests/` for row-count and watermark checks that cannot be expressed as schema.yml tests.

---

## When to Use

Invoked by `@data-quality-agent` during standard table onboarding (called from `@table-onboarding`):

```
@data-quality-agent Generate dbt tests for Orders, primary key OrderId, watermark UpdatedAt
```

---

## Inputs

| Input | Description | Required |
|-------|-------------|----------|
| TABLE_NAME | Exact table name (e.g., `Orders`) | Yes |
| TABLE_LOWER | Lowercase (e.g., `orders`) | Yes |
| PRIMARY_KEY | PK column (e.g., `OrderId`) | Yes |
| WATERMARK_COLUMN | Timestamp column (e.g., `UpdatedAt`) | Yes (incremental) / No (full_refresh) |
| INGESTION_STRATEGY | `incremental` or `full_refresh` | Yes |

---

## Outputs

1. Append model block to `dbt/models/silver/schema.yml`
2. Append model block to `dbt/models/gold/schema.yml`
3. Create `dbt/tests/silver_TABLE_LOWER_row_count.sql` (CHECK_1)
4. Create `dbt/tests/silver_TABLE_LOWER_watermark_coverage.sql` (CHECK_4, incremental only)

---

## Silver schema.yml Block (append to `models:` list)

```yaml
  - name: silver_TABLE_LOWER
    description: "Deduplicated Silver table for TABLE_NAME. Primary key: PRIMARY_KEY."
    columns:
      - name: "PRIMARY_KEY"
        quote: true
        description: "Business key — must be unique and non-null after deduplication."
        tests:
          - unique
          - not_null
```

---

## Gold schema.yml Block (append to `models:` list)

```yaml
  - name: gold_TABLE_LOWER
    description: "Analytics-ready daily summary for TABLE_NAME."
    columns:
      - name: metric_date
        tests:
          - not_null
          - unique
      - name: record_count
        tests:
          - not_null
```

---

## Singular Test: Row Count (CHECK_1)

File: `dbt/tests/silver_TABLE_LOWER_row_count.sql`

Returns 0 rows on PASS (Silver row count ≤ Bronze row count).

```sql
-- CHECK_1: Silver must not have MORE rows than Bronze after deduplication.
-- Returns 0 rows = PASS, >0 rows = FAIL.

WITH bronze_count AS (
    SELECT COUNT(*) AS cnt FROM {{ source('bronze', 'bronze_TABLE_LOWER') }}
),
silver_count AS (
    SELECT COUNT(*) AS cnt FROM {{ ref('silver_TABLE_LOWER') }}
)
SELECT
    'silver_row_count_exceeds_bronze' AS check_name,
    silver_count.cnt                  AS silver_rows,
    bronze_count.cnt                  AS bronze_rows
FROM silver_count
CROSS JOIN bronze_count
WHERE silver_count.cnt > bronze_count.cnt
```

---

## Singular Test: Watermark Coverage (CHECK_4, incremental only)

File: `dbt/tests/silver_TABLE_LOWER_watermark_coverage.sql`

Returns 0 rows on PASS (Silver max watermark = Bronze max watermark).

```sql
-- CHECK_4: Silver max WATERMARK_COLUMN must equal Bronze max — no records dropped.
-- Returns 0 rows = PASS, >0 rows = FAIL.
-- Skipped for full_refresh tables (no watermark column).

WITH bronze_max AS (
    SELECT MAX("WATERMARK_COLUMN") AS max_wm FROM {{ source('bronze', 'bronze_TABLE_LOWER') }}
),
silver_max AS (
    SELECT MAX("WATERMARK_COLUMN") AS max_wm FROM {{ ref('silver_TABLE_LOWER') }}
)
SELECT
    'silver_watermark_behind_bronze'  AS check_name,
    bronze_max.max_wm                 AS bronze_max_watermark,
    silver_max.max_wm                 AS silver_max_watermark
FROM silver_max
CROSS JOIN bronze_max
WHERE silver_max.max_wm < bronze_max.max_wm
```

**For `full_refresh` tables:** skip this file entirely. Add a comment at the top of the Silver `schema.yml` model block:
```yaml
    # CHECK_4 skipped: table uses full_refresh strategy (no watermark column)
```

---

## Appending Rules

1. **Read before writing** — always read the existing `schema.yml` before appending
2. **Never overwrite** — locate the `models:` list and append the new block at the end
3. **Duplicate check** — if a model block with the same `name:` already exists, skip (do not add again)
4. **Create if missing** — if `schema.yml` does not exist yet, create it with the required header:
   ```yaml
   version: 2

   models:
   ```
   Then append the model block.

---

## Skill Rules

1. `schema.yml` tests use built-in dbt tests (`unique`, `not_null`) — no dbt-utils package required for column-level tests
2. Singular tests in `dbt/tests/` follow the dbt convention: SELECT returns 0 rows = PASS, >0 rows = FAIL
3. Double-quoted identifiers: `"ColumnName"` for Snowflake case-sensitivity
4. Use `{{ source('bronze', ...) }}` and `{{ ref(...) }}` — never hardcode schema-qualified names
5. One singular test file per check — do not combine multiple checks in one file
