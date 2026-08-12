"""Public web API for the SQL table extractor."""

from __future__ import annotations

import os

import sqlglot
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from sql_table_extractor import extract_tables

MAX_SQL_LENGTH = 500_000

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/api/extract")
def extract():
    try:
        payload = request.get_json()
    except BadRequest:
        return jsonify(success=False, error="请求体必须是有效的 JSON", tables=[], count=0), 400

    if not isinstance(payload, dict):
        return jsonify(success=False, error="请求体必须是 JSON 对象", tables=[], count=0), 400

    sql = payload.get("sql")
    dialect = payload.get("dialect") or None
    if not isinstance(sql, str) or not sql.strip():
        return jsonify(success=False, error="请提供非空 SQL", tables=[], count=0), 400
    if len(sql) > MAX_SQL_LENGTH:
        return jsonify(success=False, error="SQL 内容不能超过 500,000 个字符", tables=[], count=0), 413
    if dialect is not None and not isinstance(dialect, str):
        return jsonify(success=False, error="dialect 必须是字符串", tables=[], count=0), 400

    try:
        tables = extract_tables(sql, dialect)
    except (ValueError, sqlglot.errors.ParseError) as error:
        return jsonify(success=False, error=str(error), tables=[], count=0), 400

    return jsonify(success=True, tables=tables, count=len(tables))


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_error):
    return jsonify(success=False, error="请求体不能超过 1 MB", tables=[], count=0), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8765")))
