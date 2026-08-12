"""Extract physical table names from SQL statements."""

from __future__ import annotations

import argparse
import json
import sys

import sqlglot
from sqlglot import expressions as exp


def extract_tables(sql: str, dialect: str | None = None) -> list[dict[str, str]]:
    """Return unique physical tables referenced by one or more SQL statements."""
    if not isinstance(sql, str) or not sql.strip():
        return []

    statements = sqlglot.parse(sql, read=dialect or None)
    tables: list[dict[str, str]] = []
    seen: set[str] = set()

    for statement in statements:
        if statement is None:
            continue

        cte_names = {
            cte.alias.lower()
            for cte in statement.find_all(exp.CTE)
            if cte.alias
        }

        for node in statement.find_all(exp.Table):
            database = node.catalog or ""
            schema = node.db or ""
            table = node.name or ""
            if not table or table.lower() in cte_names:
                continue

            full_name = ".".join(part for part in (database, schema, table) if part)
            normalized_name = full_name.lower()
            if normalized_name in seen:
                continue

            seen.add(normalized_name)
            tables.append(
                {
                    "database": database,
                    "schema": schema,
                    "table": table,
                    "full_name": full_name,
                }
            )

    return tables


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract physical table names from SQL")
    parser.add_argument("file", nargs="?", help="SQL file; reads stdin when omitted")
    parser.add_argument("--dialect", help="sqlglot dialect, such as mysql or postgres")
    args = parser.parse_args()

    try:
        if args.file:
            with open(args.file, encoding="utf-8") as sql_file:
                sql = sql_file.read()
        else:
            sql = sys.stdin.read()
        print(json.dumps(extract_tables(sql, args.dialect), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlglot.errors.ParseError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
