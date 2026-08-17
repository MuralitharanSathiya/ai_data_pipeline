---
name: ingest-script-generator
description: Generates pipeline/ingestion/ingest_<table>.py by substituting <<TABLE_NAME>> and <<TABLE_NAME_LOWER>> markers in ingest_template.py.
---

# Skill: ingest-script-generator

## Purpose

Generate a complete, runnable ingestion script for a new source table by substituting
placeholder markers in the canonical template `pipeline/ingestion/ingest_template.py`.

This skill is invoked by **ingestion-agent** and **table-onboarding** agent.

------------------------------------------------------------------------

## Inputs Required

The invoking agent must supply:

| Input | Description | Required |
|---|---|---|
| `TABLE_NAME` | Exact source table name as it appears in SQL Server (e.g. `Orders`) | Yes |
| `TABLE_NAME_LOWER` | Lowercase version of the table name (e.g. `orders`) | Yes |

------------------------------------------------------------------------

## Output

Creates one file:

```
pipeline/ingestion/ingest_<TABLE_NAME_LOWER>.py
```

Example: for table `Orders`, create `pipeline/ingestion/ingest_orders.py`.

------------------------------------------------------------------------

## How to Generate

1. **Ensure `pipeline/__init__.py` exists.** Check whether the file exists; if it does not,
   create it as an empty file. This makes `pipeline` a Python package so that
   `importlib.import_module("pipeline.utils.*")` works at runtime. Without it, the generated
   script fails with `ModuleNotFoundError: No module named 'pipeline'` even though the
   sys.path block is correct.
2. Read `pipeline/ingestion/ingest_template.py` in full.
3. Replace every occurrence of `<<TABLE_NAME>>` with the exact table name (e.g. `Orders`).
4. Replace every occurrence of `<<TABLE_NAME_LOWER>>` with the lowercase name (e.g. `orders`).
5. Write the result to `pipeline/ingestion/ingest_<TABLE_NAME_LOWER>.py`.

**That is the complete procedure.** Do not change any other lines.
Do not add logic, imports, or comments beyond what the template provides.

After writing the file, verify the output contains these two lines unchanged:
```
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```
If either line is missing, re-read the template and regenerate — do not proceed.

------------------------------------------------------------------------

## Substitution Reference

| Marker | Replace With | Example |
|---|---|---|
| `<<TABLE_NAME>>` | Exact table name | `Orders` |
| `<<TABLE_NAME_LOWER>>` | Lowercase table name | `orders` |

Occurrences in the template (for reference — do not hardcode, always read the live template):
- Module docstring: `"""Ingestion pipeline for <<TABLE_NAME>> from Azure SQL...`
- `_get_table_config`: `if table.get("name") == "<<TABLE_NAME>>":"`
- `_get_table_config` error: `"Table configuration for '<<TABLE_NAME>>' not found..."`
- `run()` docstring: `"""Execute ingestion for <<TABLE_NAME>>."""`
- `LOGGER.info` start: `"Starting ingestion | table=<<TABLE_NAME>>"`
- `read_watermark` call: `read_watermark("<<TABLE_NAME_LOWER>>")`
- `write_watermark` call: `write_watermark("<<TABLE_NAME_LOWER>>", new_watermark)`
- `LOGGER.info` complete: `"Ingestion complete | table=<<TABLE_NAME>>"`

------------------------------------------------------------------------

## Skill Rules

1. Always read `pipeline/ingestion/ingest_template.py` as the source — never hardcode the template content.
2. Make substitutions only — never add, remove, or reorder any logic.
3. Output filename must be lowercase: `ingest_orders.py` not `ingest_Orders.py`.
4. Do not modify the NOTE comment block at the top of the template file — it is documentation.
5. The generated script supports both `incremental` and `full_refresh` strategies automatically
   (the template already contains both branches — substitution activates the correct path via config).
6. Never hardcode connection strings or credentials in the generated file.
7. **Never remove, reorder, or rewrite the `sys.path` bootstrap block** — the five lines between
   `# ── critical: do not remove or reorder this block ──` and the closing `# ──` separator.
   Removing them causes `ModuleNotFoundError: No module named 'pipeline'` at runtime regardless
   of the working directory. This block must appear verbatim in every generated script.
8. **Always ensure `pipeline/__init__.py` exists** (step 1 above). Python requires this file for
   `pipeline` to be treated as a package. If it is missing, all `pipeline.utils.*` imports fail
   at runtime even when sys.path is correct. Create it as an empty file if absent.
