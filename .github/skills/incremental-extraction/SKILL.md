---
name: incremental-extraction
description: Implement watermark-based incremental extraction using <watermarkcolumn> and last_processed_timestamp patterns.
---

# Incremental Extraction

## Purpose

Use this skill to implement incremental ingestion from source systems with a watermark column.
Primary strategy is the watermark column defind in the config.yaml should be > last_processed_timestamp.


## When To Use

- Source tables should include `<watermarkcolumn>` (or compatible watermark).
- Pipeline runs repeatedly and should extract only new/changed records.
- Ingestion must be idempotent and restart-safe.

## Core Pattern

- Watermark column: `<watermarkcolumn>`
- State value: `last_processed_timestamp`
- Query filter: strict greater-than (`>`) to avoid duplicate boundary rows

## SQL Template

```sql
SELECT *
FROM <schema>.<table>
WHERE <watermarkcolumn> > %(last_processed_timestamp)s
ORDER BY <watermarkcolumn> ASC;
```

## Python Pattern: Incremental Query Builder

```python
from datetime import datetime
from typing import Any, Dict, Tuple


def build_incremental_query(
    table_name: str,
    last_processed_timestamp: datetime,
    watermark_column: str = "<watermarkcolumn>",
) -> Tuple[str, Dict[str, Any]]:
    query = f"""
        SELECT *
        FROM {table_name}
        WHERE {watermark_column} > %(last_processed_timestamp)s
        ORDER BY {watermark_column} ASC
    """
    params = {"last_processed_timestamp": last_processed_timestamp}
    return query, params
```

## State Management Pattern

State is stored in local JSON files in `pipeline/state/`.
Use `pipeline/utils/local_state.py` functions — no classes, no Snowflake dependency.

```python
# Read last watermark (returns None on first run):
from pipeline.utils.local_state import read_watermark, write_watermark

last_processed = read_watermark(table_name_lower)
# Returns: datetime | None

# After successful Bronze load, persist watermark:
non_null = source_df[watermark_column].dropna()
if not non_null.empty:
    write_watermark(table_name_lower, non_null.max())
```

State file location: `pipeline/state/<table_lower>_watermark.json`

Example state file:
```json
{
  "table": "orders",
  "last_processed": "2024-03-18T14:30:00"
}
```

**Rule:** Always write watermark AFTER a successful Bronze load. If load fails, the
watermark must not advance so the next run re-processes the same batch safely.

**Production alternative:** For multi-machine or distributed deployments, consider
using the Snowflake-based `state_store.py` (INGESTION_WATERMARKS table) which
provides atomic updates and is accessible from any node.

## Initial Load Strategy

- If `read_watermark()` returns `None` (no state file exists), the generated
  `fetch_incremental_dataframe()` call will perform a full initial load automatically.
- No explicit default timestamp is needed — the None check is handled inside the extractor.

## Workflow Guidance

1. Read `watermark_column` from config.
2. Call `read_watermark(table_name_lower)` — returns `None` on first run.
3. Execute `fetch_incremental_dataframe()` (handles None → full load internally).
4. Load results to Bronze using `upsert_dataframe_to_snowflake()`.
5. Call `write_watermark(table_name_lower, max_watermark)` after successful load.
6. Never advance watermark if load step fails.

## Reliability Addendum

- Read `source.schema` from config and always query as `<schema>.<table>` when provided.
- Use a schema-qualified source identifier for watermark state keys (for example `rs.FactPickupEvent`) to avoid cross-schema collisions.
- Add a lightweight source preflight query (`SELECT TOP 1 1 FROM <schema>.<table>`) before extraction for fast-fail diagnostics.

## Operational Notes

- Keep timestamps in UTC to avoid timezone drift.
- Use deterministic ordering by watermark for repeatability.
- For very large tables, combine watermark with chunking.
- Retries must not advance watermark unless load completes.
