---
name: snowflake-loader
description: Load pandas DataFrames into Snowflake Bronze tables using snowflake-connector-python, write_pandas, and MERGE upsert patterns.
---

# Snowflake Loader

## Purpose

Use this skill when generating load code from pandas DataFrames into Snowflake.
It includes Bronze table bootstrap, bulk load with `write_pandas`, and incremental MERGE templates.

## When To Use

- Ingestion output is a pandas DataFrame.
- Target platform is Snowflake.
- Pipelines need append or upsert behavior.

## Dependencies

```bash
pip install "snowflake-connector-python[pandas]" pandas
```

`write_pandas` also requires connector optional dependencies (notably `pyarrow`) which are included via `[pandas]` extras.

## Connection Pattern

```python
import snowflake.connector
from typing import Any, Dict


def get_snowflake_connection(target_cfg: Dict[str, Any]):
    return snowflake.connector.connect(
        account=target_cfg["account"],
        user=target_cfg["user"],
        password=target_cfg["password"],
        warehouse=target_cfg["warehouse"],
        database=target_cfg["database"],
        schema=target_cfg["schema"],
        role=target_cfg.get("role"),
    )
```

## Bronze Table Bootstrap Pattern

```sql
CREATE SCHEMA IF NOT EXISTS BRONZE;

-- Use unquoted identifiers — Snowflake normalises them to UPPERCASE (e.g. BRONZE.BRONZE_ORDERS)
CREATE TABLE IF NOT EXISTS BRONZE.BRONZE_<TABLE_NAME> (
    <COLUMN_NAME> <snowflake_type>,
    <WATERMARK_COLUMN> TIMESTAMP_NTZ
);
```

## Python Pattern: Bulk Load With write_pandas

```python
import logging
from typing import Any, Dict

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

logger = logging.getLogger(__name__)


def load_dataframe_to_bronze(df: pd.DataFrame, table_name: str, target_cfg: Dict[str, Any]) -> None:
    with get_snowflake_connection(target_cfg) as conn:
        success, nchunks, nrows, _ = write_pandas(
            conn=conn,
            df=df,
            table_name=table_name,
            schema="BRONZE",
            auto_create_table=False,
            overwrite=False,
        )
        if not success:
            raise RuntimeError(f"write_pandas failed for {table_name}")
        logger.info("Loaded %s rows in %s chunk(s) to BRONZE.%s", nrows, nchunks, table_name)
```

## MERGE Upsert Template

```sql
-- Use unquoted identifiers — Snowflake normalises them to UPPERCASE (e.g. BRONZE.BRONZE_ORDERS)
MERGE INTO BRONZE.BRONZE_<TABLE_NAME> AS tgt
USING BRONZE.STG_<TABLE_NAME> AS src
ON tgt.<business_key> = src.<business_key>
WHEN MATCHED THEN UPDATE SET
    tgt.<col1> = src.<col1>,
    tgt.<col2> = src.<col2>,
    tgt.<watermarkcolumn> = src.<watermarkcolumn>
WHEN NOT MATCHED THEN INSERT (
    <business_key>,
    <col1>,
    <col2>,
    <watermarkcolumn>
) VALUES (
    src.<business_key>,
    src.<col1>,
    src.<col2>,
    src.<watermarkcolumn>
);
```

## Workflow Guidance

1. Ensure BRONZE schema and target tables exist.
2. Standardize DataFrame column names before load.
3. Use `write_pandas` for efficient bulk ingestion.
4. Use MERGE for incremental upserts when keys are defined.
5. Log row counts, chunk counts, and table names.
6. Fail fast on load errors so orchestration can retry safely.

## Common Pitfalls

- Loading without matching DataFrame and table column names.
- Forgetting schema/table existence checks.
- MERGE statements without stable business keys.
- Silent partial loads without metric logging.
- Binding pandas/numpy timestamp-like objects directly in connector parameters. Normalize to connector-safe values (native datetime or ISO string cast in SQL).
