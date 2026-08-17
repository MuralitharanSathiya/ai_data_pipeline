---
name: medallion-transform
description: Define Bronze, Silver, and Gold transformation patterns for deterministic, idempotent analytics pipelines.
---

# Medallion Transform

## Purpose

Use this skill when generating SQL and workflow logic for Bronze, Silver, and Gold layers.
The goal is deterministic, idempotent, and analytics-ready transformations.

## When To Use

- Bronze raw tables already exist.
- Transformation agent must build Silver and Gold assets.
- Pipelines require reusable SQL templates for cleaning and aggregation.

## Layer Definitions

- Bronze: Raw ingested data with minimal transformation (`bronze_<table_name>`).
- Silver: Cleaned, deduplicated, and normalized data (`silver_<table_name>`).
- Gold: Business-ready aggregates and semantic models (`gold_<table_name>`).

## Bronze Pattern

- Preserve source columns and ingestion metadata.
- Add load timestamp (`ingested_at`) where needed.
- Avoid business logic in Bronze.

## Silver Pattern: Deduplicate, Clean, Normalize

```sql
CREATE OR REPLACE TABLE SILVER.silver_<table_name> AS
WITH ranked AS (
    SELECT
        b.*,
        ROW_NUMBER() OVER (
            PARTITION BY b.<business_key>
            ORDER BY b.updated_at DESC
        ) AS rn
    FROM BRONZE.bronze_<table_name> b
),
cleaned AS (
    SELECT
        <business_key>,
        TRIM(<string_col>) AS <string_col>,
        TRY_TO_TIMESTAMP_NTZ(updated_at) AS updated_at,
        TRY_TO_NUMBER(<numeric_col>) AS <numeric_col>
    FROM ranked
    WHERE rn = 1
)
SELECT *
FROM cleaned;
```

Silver guidance:
- Deduplicate by business key with latest `updated_at`.
- Standardize datatypes and null handling.
- Apply deterministic cleaning rules only.

## Gold Pattern: Analytics-Ready Aggregations

```sql
CREATE OR REPLACE TABLE GOLD.gold_<subject_area> AS
SELECT
    DATE_TRUNC('day', updated_at) AS metric_date,
    <dimension_col>,
    COUNT(*) AS record_count,
    SUM(<measure_col>) AS total_measure
FROM SILVER.silver_<table_name>
GROUP BY 1, 2;
```

Gold guidance:
- Model data for BI/reporting consumption.
- Use explicit dimensions/measures and consistent grain.
- Keep logic traceable back to Silver inputs.

## Workflow Guidance

1. Read source-to-target mappings from `config.yaml`.
2. Build Bronze references as immutable inputs.
3. Build Silver tables with dedupe and normalization.
4. Build Gold tables with business aggregates.
5. Validate row counts and key metrics between layers.
6. Keep transformations idempotent (safe to rerun).

## Quality And Determinism Checklist

- Naming conventions follow `bronze_`, `silver_`, `gold_`.
- Deduplication keys are explicit and stable.
- Type conversion uses safe functions (for example, `TRY_TO_*`).
- Null handling and defaults are documented and consistent.
- Aggregation grain is clearly defined per Gold model.
