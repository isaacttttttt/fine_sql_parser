import json

from app import app
from sql_table_extractor import extract_tables


def test_extract_tables_excludes_ctes_and_deduplicates():
    sql = """
    WITH recent AS (SELECT * FROM warehouse.orders)
    SELECT * FROM recent r
    JOIN warehouse.customers c ON c.id = r.customer_id
    JOIN warehouse.orders o ON o.id = r.id
    """

    assert {table["full_name"] for table in extract_tables(sql)} == {
        "warehouse.orders",
        "warehouse.customers",
    }


def test_extract_tables_supports_multiple_statements():
    tables = extract_tables("SELECT * FROM first_table; SELECT * FROM second_table;")
    assert [table["full_name"] for table in tables] == ["first_table", "second_table"]


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_extract_endpoint():
    client = app.test_client()
    response = client.post(
        "/api/extract",
        data=json.dumps({"sql": "SELECT * FROM analytics.events", "dialect": ""}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.get_json()["tables"][0]["full_name"] == "analytics.events"


def test_extract_endpoint_rejects_empty_sql():
    client = app.test_client()
    response = client.post("/api/extract", json={"sql": ""})
    assert response.status_code == 400
    assert response.get_json()["success"] is False
