---
name: pipeline-bootstrap
description: Creates the base project directory structure and generates all pipeline utility modules if they do not already exist.
---

# Skill: pipeline-bootstrap

**Name:** `pipeline-bootstrap`
**Description:** Creates the base project structure and generates the 5 shared utility modules
required by all ingestion scripts. All operations are idempotent — existing files and directories
are never overwritten.

This skill is invoked by `table-onboarding` agent as the first step of every onboarding run.

---

## Step 1 — Create Directory Structure

Ensure the following directories exist (create if absent, skip if present):

```
pipeline/
pipeline/utils/
pipeline/ingestion/
pipeline/state/
```

Note: `pipeline/transformations/` and `pipeline/validation/` are **not** created here.
Transformations and tests are managed by dbt under `dbt/models/` and `dbt/tests/`.

---

## Step 2 — Create Package Init Files

Create the following empty files if they do not already exist:

- `pipeline/__init__.py` — makes `pipeline` a Python package (required for `importlib.import_module("pipeline.utils.*")`)
- `pipeline/utils/__init__.py` — makes `pipeline.utils` a package

Do not write any content into these files. If they already exist, skip them.

---

## Step 3 — Generate Utility Modules (Verbatim — Do Not Modify)

For each file below: **write the file only if it does not already exist.**
If the file exists, skip it entirely — never overwrite.

Copy the content EXACTLY as shown — character for character. Do not reformat, reorder,
rename functions, or add/remove any lines.

---

### `pipeline/utils/config_loader.py`

```python
"""Helpers for loading pipeline configuration and environment variables."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "pipeline" / "config.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_pipeline_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Load and validate the pipeline configuration file."""
    resolved_config_path = config_path or DEFAULT_CONFIG_PATH

    if not resolved_config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {resolved_config_path}")

    with resolved_config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    required_top_level = ["source", "tables", "target", "ingestion"]
    missing = [key for key in required_top_level if key not in config]
    if missing:
        missing_keys = ", ".join(missing)
        raise ValueError(f"Missing required config sections: {missing_keys}")

    return config


def load_environment(env_path: Path | None = None) -> None:
    """Load environment variables from .env without overriding existing values."""
    resolved_env_path = env_path or DEFAULT_ENV_PATH

    if not resolved_env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {resolved_env_path}")

    load_dotenv(dotenv_path=resolved_env_path, override=False)
```

---

### `pipeline/utils/database_client.py`

```python
"""Database connection helpers for SQL Server and Snowflake."""

from __future__ import annotations

import os
from typing import Any

import pymssql
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection


class ConnectionConfigurationError(ValueError):
    """Raised when required connection configuration is missing."""


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ConnectionConfigurationError(
            f"Missing required environment variable: {var_name}"
        )
    return value


def get_sqlserver_connection(source_config: dict[str, Any]) -> pymssql.Connection:
    """Create a SQL Server connection using config and environment variables."""
    server = source_config.get("server")
    database = source_config.get("database")

    if not server or not database:
        raise ConnectionConfigurationError(
            "Source config must include 'server' and 'database'."
        )

    username = _require_env("AZURE_SQL_USER")
    password = _require_env("AZURE_SQL_PASSWORD")

    return pymssql.connect(
        server=server,
        user=username,
        password=password,
        database=database,
        login_timeout=30,
        timeout=120,
    )


def get_snowflake_connection(target_config: dict[str, Any]) -> SnowflakeConnection:
    """Create a Snowflake connection using config and environment variables."""
    account = target_config.get("account")
    warehouse = target_config.get("warehouse")
    database = target_config.get("database")
    schema = target_config.get("schema")
    role = target_config.get("role")

    missing = [
        key
        for key, value in {
            "account": account,
            "warehouse": warehouse,
            "database": database,
            "schema": schema,
            "role": role,
        }.items()
        if not value
    ]
    if missing:
        raise ConnectionConfigurationError(
            f"Target config missing required keys: {', '.join(missing)}"
        )

    username = _require_env("SNOWFLAKE_USER")
    password = _require_env("SNOWFLAKE_PASSWORD")

    return snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
        login_timeout=30,
    )
```

---

### `pipeline/utils/extractor.py`

```python
"""Extraction helpers for watermark-based SQL Server ingestion."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

import pandas as pd
import pymssql


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(identifier: str, label: str) -> None:
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Invalid {label}: {identifier}")


def fetch_incremental_dataframe(
    sql_connection: pymssql.Connection,
    table_name: str,
    watermark_column: str,
    last_processed_timestamp: Optional[datetime],
    schema_name: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch source rows using full or watermark-based incremental extraction."""
    _validate_identifier(table_name, "table name")
    _validate_identifier(watermark_column, "watermark column")
    if schema_name:
        _validate_identifier(schema_name, "schema name")

    qualified_table = f"[{schema_name}].[{table_name}]" if schema_name else f"[{table_name}]"

    try:
        if last_processed_timestamp is None:
            query = f"SELECT * FROM {qualified_table}"
            return pd.read_sql_query(query, sql_connection)

        query = (
            f"SELECT * FROM {qualified_table} "
            f"WHERE [{watermark_column}] > %s "
            f"AND [{watermark_column}] IS NOT NULL"
        )
        return pd.read_sql_query(query, sql_connection, params=(last_processed_timestamp,))
    except pymssql.ProgrammingError as error:
        error_text = str(error)
        if "Invalid object name" in error_text:
            object_name = f"{schema_name}.{table_name}" if schema_name else table_name
            raise ValueError(
                "Source table not found in SQL Server: "
                f"{object_name}. Set source.schema in config.yaml (for example 'dbo') "
                "or verify table name casing and permissions."
            ) from error
        raise


def fetch_full_dataframe(
    sql_connection: pymssql.Connection,
    table_name: str,
    schema_name: Optional[str] = None,
) -> pd.DataFrame:
    """Extract all rows from a source table (full refresh — no watermark filter)."""
    _validate_identifier(table_name, "table name")
    if schema_name:
        _validate_identifier(schema_name, "schema name")

    qualified_table = f"[{schema_name}].[{table_name}]" if schema_name else f"[{table_name}]"
    query = f"SELECT * FROM {qualified_table}"
    return pd.read_sql_query(query, sql_connection)
```

---

### `pipeline/utils/snowflake_loader.py`

```python
"""Snowflake load helpers for bronze upserts using write_pandas + MERGE."""

from __future__ import annotations

import datetime
import uuid
from typing import Iterable

import pandas as pd
from snowflake.connector.connection import SnowflakeConnection
from snowflake.connector.pandas_tools import write_pandas


def _coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert object-dtype columns containing Python datetimes to datetime64.

    pymssql returns SQL Server datetime values as Python datetime.datetime objects
    stored in object-dtype columns. write_pandas maps datetime64 -> TIMESTAMP_NTZ;
    object-dtype datetime columns land as VARCHAR or NUMBER(38,0) in Snowflake instead.
    """
    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].dropna()
        if not non_null.empty and isinstance(non_null.iloc[0], datetime.datetime):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _q(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def _build_merge_sql(
    database: str,
    schema: str,
    target_table: str,
    staging_table: str,
    columns: Iterable[str],
    primary_key: str,
) -> str:
    cols = list(columns)
    join_condition = f"t.{_q(primary_key)} = s.{_q(primary_key)}"
    update_assignments = ", ".join([f"t.{_q(col)} = s.{_q(col)}" for col in cols])
    insert_columns = ", ".join([_q(col) for col in cols])
    insert_values = ", ".join([f"s.{_q(col)}" for col in cols])

    return f"""
    MERGE INTO {_q(database)}.{_q(schema)}.{_q(target_table)} t
    USING {_q(database)}.{_q(schema)}.{_q(staging_table)} s
      ON {join_condition}
    WHEN MATCHED THEN UPDATE SET {update_assignments}
    WHEN NOT MATCHED THEN
      INSERT ({insert_columns})
      VALUES ({insert_values})
    """


def upsert_dataframe_to_snowflake(
    sf_connection: SnowflakeConnection,
    dataframe: pd.DataFrame,
    database: str,
    schema: str,
    target_table: str,
    primary_key: str,
) -> int:
    """Upsert a dataframe into Snowflake using a temporary staging table."""
    if dataframe.empty:
        return 0

    target_table = target_table.upper()

    if primary_key not in dataframe.columns:
        raise ValueError(
            f"Primary key '{primary_key}' not found in dataframe columns: "
            f"{list(dataframe.columns)}"
        )

    dataframe = _coerce_datetime_columns(dataframe)
    staging_table = f"TMP_{target_table}_{uuid.uuid4().hex[:8]}".upper()
    total_rows = len(dataframe)

    # use_logical_type=True ensures datetime64 columns are annotated in Parquet
    # so Snowflake creates TIMESTAMP_NTZ instead of NUMBER(38,0).
    success, _, loaded_rows, _ = write_pandas(
        conn=sf_connection,
        df=dataframe,
        table_name=staging_table,
        database=database,
        schema=schema,
        auto_create_table=True,
        overwrite=True,
        use_logical_type=True,
    )

    if not success:
        raise RuntimeError("write_pandas failed while loading staging data.")

    with sf_connection.cursor() as cursor:
        # target_table is unquoted so Snowflake normalises it to UPPERCASE.
        # Unquoted identifiers are always stored as UPPERCASE in Snowflake regardless of
        # what the connector does internally — this is the guaranteed mechanism.
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_q(database)}.{_q(schema)}.{target_table} "
            f"LIKE {_q(database)}.{_q(schema)}.{_q(staging_table)}"
        )

        merge_sql = _build_merge_sql(
            database=database,
            schema=schema,
            target_table=target_table,
            staging_table=staging_table,
            columns=dataframe.columns,
            primary_key=primary_key,
        )
        cursor.execute(merge_sql)
        cursor.execute(
            f"DROP TABLE IF EXISTS {_q(database)}.{_q(schema)}.{_q(staging_table)}"
        )

    return int(loaded_rows if loaded_rows is not None else total_rows)


def truncate_and_insert(
    sf_connection: SnowflakeConnection,
    dataframe: pd.DataFrame,
    database: str,
    schema: str,
    target_table: str,
) -> int:
    """Truncate the target table and insert all rows (full refresh strategy)."""
    if dataframe.empty:
        return 0

    target_table = target_table.upper()

    dataframe = _coerce_datetime_columns(dataframe)
    # Use a staging table so the target is created via hand-written SQL (same pattern as
    # upsert_dataframe_to_snowflake). write_pandas double-quotes the table_name it receives;
    # some connector versions lowercase before quoting, producing "bronze_x" instead of
    # BRONZE_X. By writing to a staging table and creating the target with unquoted SQL we
    # guarantee the target lands as a UPPERCASE identifier in Snowflake.
    staging_table = f"TMP_{target_table}_{uuid.uuid4().hex[:8]}".upper()

    success, _, nrows, _ = write_pandas(
        conn=sf_connection,
        df=dataframe,
        table_name=staging_table,
        database=database,
        schema=schema,
        auto_create_table=True,
        overwrite=True,
        use_logical_type=True,
    )

    if not success:
        raise RuntimeError(f"write_pandas failed for staging table {staging_table}")

    with sf_connection.cursor() as cursor:
        # target_table is unquoted so Snowflake normalises it to UPPERCASE.
        # Unquoted identifiers are always stored as UPPERCASE in Snowflake regardless of
        # what the connector does internally — this is the guaranteed mechanism.
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {_q(database)}.{_q(schema)}.{target_table} "
            f"LIKE {_q(database)}.{_q(schema)}.{_q(staging_table)}"
        )
        cursor.execute(
            f"TRUNCATE TABLE {_q(database)}.{_q(schema)}.{target_table}"
        )
        cursor.execute(
            f"INSERT INTO {_q(database)}.{_q(schema)}.{target_table} "
            f"SELECT * FROM {_q(database)}.{_q(schema)}.{_q(staging_table)}"
        )
        cursor.execute(
            f"DROP TABLE IF EXISTS {_q(database)}.{_q(schema)}.{_q(staging_table)}"
        )

    return int(nrows if nrows is not None else len(dataframe))
```

---

### `pipeline/utils/local_state.py`

```python
"""Local file-based watermark state for incremental ingestion pipelines."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

STATE_DIR = Path(__file__).resolve().parents[1] / "state"
LOGGER = logging.getLogger(__name__)


def read_watermark(table_name: str) -> Optional[datetime]:
    """Return the last processed timestamp for a table, or None if no state exists."""
    state_file = STATE_DIR / f"{table_name}_watermark.json"
    if not state_file.exists():
        return None
    data = json.loads(state_file.read_text())
    return datetime.fromisoformat(data["last_processed"])


def write_watermark(table_name: str, timestamp: datetime) -> None:
    """Persist the last processed timestamp for a table to a local JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / f"{table_name}_watermark.json"
    state_file.write_text(
        json.dumps(
            {
                "table": table_name,
                "last_processed": (
                    timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp)
                ),
            },
            indent=2,
        )
    )
    LOGGER.debug("Watermark written | file=%s", state_file)
```

---

## Step 4 — Create `requirements.txt` (if not present)

Create `requirements.txt` at repo root only if it does not already exist. Use this standardized format with section comments:

```
# Configuration & environment
pyyaml>=6.0
python-dotenv>=1.0.1

# Data processing
pandas>=2.2.0

# Source connector: Azure SQL Server
pymssql>=2.3.0

# Target connector: Snowflake (ingestion)
snowflake-connector-python[pandas]>=3.12.0

# Transformations: dbt with Snowflake adapter
dbt-snowflake>=1.8.0
```

If `requirements.txt` already exists, skip it — never overwrite.

---

## Skill Rules

1. **Idempotent** — check for existence before creating anything. Never overwrite files or directories.
2. **Verbatim only** — copy utility module code exactly as shown. Do not reformat, rename, or modify any line.
3. **Dirs first** — create directory structure (Step 1) before writing any files.
4. **Init files** — always ensure `pipeline/__init__.py` and `pipeline/utils/__init__.py` exist (Step 2).
5. **No implementation changes** — this skill scaffolds infrastructure only. It does not generate ingestion scripts, dbt models, or validation tests.
