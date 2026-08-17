"""Ingestion pipeline for <<TABLE_NAME>> from Azure SQL to Snowflake Bronze.

NOTE: This file is a template. It is NOT runnable directly.
      The <<TABLE_NAME>> and <<TABLE_NAME_LOWER>> markers are substituted by the
      ingest-script-generator skill to produce ingest_<table>.py files.

      To onboard a new table, use:
        @table-onboarding Onboard table <Name> from <schema> schema, primary key <PK>, watermark <WM>
"""

from __future__ import annotations

import logging
import importlib
import sys
from pathlib import Path

import pandas as pd

# ── critical: do not remove or reorder this block ────────────────────────────
# Python sets sys.path[0] to the script's directory (/pipeline/ingestion/),
# not the repo root. Without this insertion, every importlib.import_module call
# below raises ModuleNotFoundError: No module named 'pipeline'.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ─────────────────────────────────────────────────────────────────────────────

config_loader = importlib.import_module("pipeline.utils.config_loader")
database_client = importlib.import_module("pipeline.utils.database_client")
extractor = importlib.import_module("pipeline.utils.extractor")
snowflake_loader = importlib.import_module("pipeline.utils.snowflake_loader")
local_state = importlib.import_module("pipeline.utils.local_state")

load_environment = config_loader.load_environment
load_pipeline_config = config_loader.load_pipeline_config
ConnectionConfigurationError = database_client.ConnectionConfigurationError
get_snowflake_connection = database_client.get_snowflake_connection
get_sqlserver_connection = database_client.get_sqlserver_connection
fetch_incremental_dataframe = extractor.fetch_incremental_dataframe
fetch_full_dataframe = extractor.fetch_full_dataframe
upsert_dataframe_to_snowflake = snowflake_loader.upsert_dataframe_to_snowflake
truncate_and_insert = snowflake_loader.truncate_and_insert
read_watermark = local_state.read_watermark
write_watermark = local_state.write_watermark


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)


def _get_table_config(config: dict) -> dict:
    # `or []`, not `.get("tables", [])`. An empty `tables:` key parses as None and
    # the default only applies when the key is absent entirely, so `.get(k, [])`
    # returns None here and the loop raises "'NoneType' object is not iterable".
    for table in config.get("tables") or []:
        if table.get("name") == "<<TABLE_NAME>>":
            return table
    raise ValueError("Table configuration for '<<TABLE_NAME>>' not found in config.yaml")


def run() -> None:
    """Execute ingestion for <<TABLE_NAME>>."""
    sql_conn = None
    sf_conn = None

    LOGGER.info("Starting ingestion | table=<<TABLE_NAME>>")

    try:
        load_environment()
        config = load_pipeline_config()

        source_config = config["source"]
        target_config = config["target"]
        table_config = _get_table_config(config)

        source_table = table_config["name"]
        primary_key = table_config.get("primary_key")
        watermark_column = table_config.get("watermark_column")
        strategy = table_config.get("ingestion_strategy", "incremental")
        source_schema = source_config.get("schema")
        source_table_identifier = (
            f"{source_schema}.{source_table}" if source_schema else source_table
        )

        target_database = target_config["database"]
        target_schema = target_config["schema"]
        target_table = f"bronze_{source_table.lower()}"

        LOGGER.info(
            "Config loaded | strategy=%s | source=%s | target=%s.%s",
            strategy,
            source_table_identifier,
            target_schema,
            target_table,
        )

        sql_conn = get_sqlserver_connection(source_config)
        sf_conn = get_snowflake_connection(target_config)

        if strategy == "full_refresh":
            LOGGER.info("Full refresh: loading all rows from source")
            source_df = fetch_full_dataframe(
                sql_connection=sql_conn,
                table_name=source_table,
                schema_name=source_schema,
            )
        else:
            last_processed = read_watermark("<<TABLE_NAME_LOWER>>")
            if last_processed is None:
                LOGGER.info("No prior watermark found — running full initial load")
            else:
                LOGGER.info("Incremental load | watermark > %s", last_processed)
            source_df = fetch_incremental_dataframe(
                sql_connection=sql_conn,
                table_name=source_table,
                watermark_column=watermark_column,
                last_processed_timestamp=last_processed,
                schema_name=source_schema,
            )

        source_count = len(source_df)
        LOGGER.info("Extracted %s rows from %s", source_count, source_table_identifier)

        if source_count == 0:
            LOGGER.info("No rows to load — ingestion complete")
            return

        if strategy == "full_refresh":
            loaded_count = truncate_and_insert(
                sf_connection=sf_conn,
                dataframe=source_df,
                database=target_database,
                schema=target_schema,
                target_table=target_table,
            )
        else:
            loaded_count = upsert_dataframe_to_snowflake(
                sf_connection=sf_conn,
                dataframe=source_df,
                database=target_database,
                schema=target_schema,
                target_table=target_table,
                primary_key=primary_key,
            )

        status = "OK" if loaded_count == source_count else "MISMATCH"
        LOGGER.info(
            "INGESTION SUMMARY | table=%s | strategy=%s | extracted=%s | loaded=%s | status=%s",
            source_table_identifier,
            strategy,
            source_count,
            loaded_count,
            status,
        )

        if strategy == "incremental":
            non_null = source_df[watermark_column].dropna()
            if not non_null.empty:
                new_watermark = non_null.max()
                write_watermark("<<TABLE_NAME_LOWER>>", new_watermark)
                LOGGER.info(
                    "Watermark updated | column=%s | value=%s", watermark_column, new_watermark
                )
            else:
                LOGGER.info("No non-null watermark values found — checkpoint unchanged")

        LOGGER.info("Ingestion complete | table=<<TABLE_NAME>>")

    except ConnectionConfigurationError as error:
        LOGGER.exception("Connection configuration error: %s", error)
        raise
    except Exception as error:  # pylint: disable=broad-exception-caught
        LOGGER.exception("Ingestion failed: %s", error)
        raise
    finally:
        if sql_conn is not None:
            sql_conn.close()
            LOGGER.info("Closed SQL Server connection")
        if sf_conn is not None:
            sf_conn.close()
            LOGGER.info("Closed Snowflake connection")


if __name__ == "__main__":
    run()
