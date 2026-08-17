---
name: sqlserver-connection
description: Connect to Azure SQL Server, execute SELECT queries, and provide reusable pymssql patterns for ingestion pipelines.
---

# SQL Server Connection

## Purpose

Use this skill when generating ingestion code that needs to read data from Azure SQL Server.
This skill focuses on connection setup, secure credential handling, and reusable SELECT execution patterns.

## When To Use

- Source system is Azure SQL Server.
- Pipeline needs table reads or filtered extraction queries.
- Agent must generate Python code with `pymssql`.

## Dependencies

```bash
pip install pymssql pandas
```

## Configuration Pattern

Keep connection properties in `config.yaml` or environment variables.
Do not hardcode credentials in Python files.

```yaml
source:
  type: azure_sql
  server: my-server.database.windows.net
  port: 1433
  database: source_db
    schema: dbo
  user: ${AZURE_SQL_USER}
  password: ${AZURE_SQL_PASSWORD}
```

## Python Pattern: Open Connection And Execute SELECT

```python
import logging
import os
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import pymssql

logger = logging.getLogger(__name__)


def get_sql_connection(source_cfg: Dict[str, Any]) -> pymssql.Connection:
    """Create Azure SQL Server connection using config/env secrets."""
    return pymssql.connect(
        server=source_cfg["server"],
        user=os.getenv("AZURE_SQL_USER", source_cfg.get("user", "")),
        password=os.getenv("AZURE_SQL_PASSWORD", source_cfg.get("password", "")),
        database=source_cfg["database"],
        port=source_cfg.get("port", 1433),
        login_timeout=30,
        timeout=120,
    )


def execute_select(
    query: str,
    source_cfg: Dict[str, Any],
    params: Optional[Iterable[Any]] = None,
) -> pd.DataFrame:
    """Run a SELECT query and return results as a DataFrame."""
    logger.info("Executing source SELECT query")
    try:
        with get_sql_connection(source_cfg) as conn:
            return pd.read_sql(query, conn, params=params)
    except Exception:
        logger.exception("Failed to execute SELECT query against Azure SQL Server")
        raise
```

## SQL Query Template

```sql
SELECT
    *
FROM dbo.<table_name>
WHERE 1 = 1;
```

Use explicit column selection for production tables whenever possible.

## Workflow Guidance

1. Read source connection settings from `config.yaml`.
2. Resolve secrets from environment variables.
3. Open connection with timeout settings.
4. Execute parameterized SELECT statements.
5. Log extracted row counts and elapsed time.
6. Raise exceptions after logging to support retries.
7. Use schema-qualified table references from config (`source.schema.table`) for all source queries.
8. Run preflight checks before extraction: host resolution, connectivity, and a probe query on the source table.

## Common Pitfalls

- Using hardcoded credentials.
- Building SQL with string concatenation instead of parameters.
- Not setting connection/query timeouts.
- Swallowing exceptions without logging context.
- Omitting schema qualification and relying on default schema resolution.
- Treating DNS/network failures as credential issues.
