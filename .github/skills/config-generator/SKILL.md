---
name: config-generator
description: Generates ingestion configuration and environment variable templates for SQL to Snowflake pipelines.
---

# Skill: config-generator

## Purpose

Generate ingestion configuration and environment variable templates
required for SQL to Snowflake data ingestion pipelines.

This skill is invoked by the **ingestion-planner agent** and the **table-onboarding agent**.

------------------------------------------------------------------------

# Files Generated

The skill must create or update the following files:

pipeline/config.yaml\
.env.example

------------------------------------------------------------------------

# File 1 --- pipeline/config.yaml

This file defines ingestion configuration used by ingestion pipelines.

If user information is available, populate fields accordingly.

If information is missing, use placeholders.

Example configuration:

``` yaml
# Ingestion configuration for SQL → Snowflake pipelines

source:
  type: sql
  server: <SQL_SERVER>
  database: <SQL_DATABASE>
  schema: <SCHEMA>

tables:
  - name: <TABLE_NAME>
    primary_key: <PRIMARY_KEY>
    watermark_column: <WATERMARK_COLUMN>   # omit for full_refresh tables
    ingestion_strategy: incremental        # incremental | full_refresh

target:
  type: snowflake
  account: <SNOWFLAKE_ACCOUNT>
  database: <SNOWFLAKE_DATABASE>
  schema: BRONZE
  warehouse: <SNOWFLAKE_WAREHOUSE>

ingestion:
  strategy: incremental
```

Guidelines:

-   Always include the `tables` section
-   `watermark_column` is required for incremental ingestion — insist on its presence
-   `ingestion_strategy` must be `incremental` or `full_refresh`
-   For `full_refresh` tables: omit `watermark_column`, omit `primary_key` if not needed
-   Configuration must remain environment independent

------------------------------------------------------------------------

# APPEND MODE — Adding a New Table to an Existing config.yaml

When `pipeline/config.yaml` already exists and a new table is being added:

**DO NOT** regenerate the entire file.\
**DO NOT** modify `source`, `target`, or `ingestion` sections.\
**ONLY** append a new entry to the existing `tables:` list.

**Before** (existing file):
```yaml
tables:
  - name: FactPickupEvent
    primary_key: PickupId
    watermark_column: UpdatedAt
    ingestion_strategy: incremental
```

**After** (new table appended):
```yaml
tables:
  - name: FactPickupEvent
    primary_key: PickupId
    watermark_column: UpdatedAt
    ingestion_strategy: incremental
  - name: Orders
    primary_key: OrderId
    watermark_column: UpdatedAt
    ingestion_strategy: incremental
```

**Full refresh table example** (no watermark needed):
```yaml
  - name: DimProduct
    primary_key: ProductId
    ingestion_strategy: full_refresh
```

APPEND MODE rules:
1. Read the existing file first.
2. Check `tables:` for a duplicate name (case-insensitive). If found — stop and report the duplicate. Do not append.
3. Append the new entry to the END of the `tables:` list.
4. Preserve all existing indentation and YAML formatting exactly.
5. Do not modify `source`, `target`, or `ingestion` sections under any circumstance.

------------------------------------------------------------------------

# NEVER LEAVE `tables:` EMPTY

An empty `tables:` key is not the same as a missing one. YAML parses this:

```yaml
tables:
ingestion:
  strategy: incremental
```

as `tables = None`, **not** as an empty list. Any ingestion script that then runs
fails with `TypeError: 'NoneType' object is not iterable`, which points at the
script rather than at the real problem in this file.

This state is easy to create by accident: a fresh template has no `tables:`
section at all, so adding the header and the first entry as two separate edits
leaves the file broken in between. If a pipeline runs during that window — or if
the second edit is never made — the failure looks like a bug in the generated
Python.

Rules:

1. **Write the header and the first entry in a single edit.** When `tables:` is
   absent, insert the key and at least one complete table entry together. Never
   write a bare `tables:` line on its own.
2. **Never delete the last entry** and leave the header behind. If every table is
   removed, write `tables: []` explicitly — an empty list is valid and loads
   cleanly.
3. **Re-read the file after writing** and confirm `tables:` contains at least one
   entry with `name`, and that `source`, `target` and `ingestion` are all still
   present and non-empty. Report the table count in your completion summary.
4. The same applies to `ingestion:` — it must always have `strategy` under it.

------------------------------------------------------------------------

# File 2 --- .env.example

Example file:

```
AZURE_SQL_USER=
AZURE_SQL_PASSWORD=

SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
```

------------------------------------------------------------------------

# Skill Behavior Rules

1.  Never store credentials in config.yaml
2.  Always use `.env.example` for secrets
3.  If config.yaml exists and a new table is being added, use APPEND MODE (see above).
    Never overwrite existing `tables:` list entries.
4.  Maintain clean YAML formatting
5.  Always include `ingestion_strategy` in every table entry
