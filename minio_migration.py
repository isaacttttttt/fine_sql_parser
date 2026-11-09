"""Local Flask tool for copying report templates between MinIO nodes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
from posixpath import splitext
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, render_template, request
from minio import Minio
from minio.error import MinioException
from urllib3.exceptions import HTTPError

from minio_catalog import list_objects, scan_catalog

BEIJING = timezone(timedelta(hours=8))
STORAGE_ERRORS = (MinioException, HTTPError, OSError)
COPY_HEADERS = {"cache-control", "content-encoding", "content-disposition", "content-language"}


@dataclass(frozen=True)
class Node:
    endpoint: str
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    bucket: str
    prefix: str = ""
    secure: bool = True

    def __post_init__(self):
        if self.prefix and not self.prefix.endswith("/"):
            raise ValueError("节点 prefix 必须以 / 结尾")

    def connect(self) -> Minio:
        return Minio(self.endpoint, self.access_key, self.secret_key, secure=self.secure)


app = Flask(__name__)
hosted = bool(os.environ.get("RAILWAY_ENVIRONMENT_ID"))
trusted_hosts = ["localhost", "127.0.0.1"]
if hosted:
    app.config["MINIO_NODES"] = json.loads(os.environ.get("MINIO_NODES_JSON", "{}"))
    trusted_hosts.append("healthcheck.railway.app")
    if domain := os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        trusted_hosts.append(domain)
else:
    app.config.from_pyfile("minio_nodes.local.py", silent=True)
app.config.update(
    MINIO_NODES={key: Node(**value) for key, value in app.config.get("MINIO_NODES", {}).items()},
    MINIO_CATALOG_DIR=Path(app.instance_path) / "minio-catalog",
    MINIO_MIGRATION_HOSTED=hosted,
    MINIO_MIGRATION_TOKEN=os.environ.get("MINIO_MIGRATION_TOKEN"),
    MAX_CONTENT_LENGTH=1_000_000,
    TRUSTED_HOSTS=trusted_hosts,
)
if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", key) for key in app.config["MINIO_NODES"]):
    raise ValueError("节点 ID 只允许字母、数字、连字符和下划线，并以字母或数字开头")


def read_catalog(node_id: str):
    path = app.config["MINIO_CATALOG_DIR"] / f"{node_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


@app.before_request
def authorize_hosted_requests():
    if not app.config["MINIO_MIGRATION_HOSTED"] or request.endpoint == "health":
        return

    token = app.config["MINIO_MIGRATION_TOKEN"]
    if not token:
        if request.endpoint == "index":
            return render_template("minio_migration.html", nodes=[], hosted=True)
        return jsonify(error="请先配置迁移访问令牌"), 503

    auth = request.authorization
    if (auth is None or auth.type != "basic" or auth.username != "operator" or auth.password is None
            or not compare_digest(auth.password.encode(), token.encode())):
        return "请登录迁移工具", 401, {"WWW-Authenticate": 'Basic realm="MinIO migration", charset="UTF-8"'}

    origin = request.headers.get("Origin")
    if request.method == "POST" and origin and origin != f"https://{request.host}":
        return jsonify(error="请从迁移工具页面发起操作"), 403


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/")
def index():
    return render_template("minio_migration.html", nodes=list(app.config["MINIO_NODES"]),
                           hosted=app.config["MINIO_MIGRATION_HOSTED"])


@app.route("/api/catalogs/<node_id>", methods=["GET", "POST"])
def catalog(node_id: str):
    node = app.config["MINIO_NODES"].get(node_id)
    if node is None:
        return jsonify(error="未知节点"), 404
    if request.method == "GET":
        return jsonify(catalog=read_catalog(node_id))

    snapshot = scan_catalog(node.connect(), node.bucket, node.prefix)
    snapshot.update(node=node_id, refreshed_at=datetime.now(BEIJING).isoformat(timespec="seconds"))
    directory = app.config["MINIO_CATALOG_DIR"]
    directory.mkdir(parents=True, exist_ok=True)
    # Keep the previous snapshot available if listing or writing fails.
    output = NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False)
    temporary = Path(output.name)
    try:
        with output:
            json.dump(snapshot, output, ensure_ascii=False, indent=2)
        temporary.replace(directory / f"{node_id}.json")
    finally:
        temporary.unlink(missing_ok=True)
    return jsonify(catalog=snapshot)


def migration_paths(paths: list[str], suffix: str) -> list[tuple[str, str]]:
    result = []
    for path in dict.fromkeys(paths):
        name = path.rstrip("/").rsplit("/", 1)[-1]
        if path.endswith("/"):
            result.append((path, f"{name}{suffix}/"))
        else:
            stem, extension = splitext(name)
            result.append((path, f"{stem}{suffix}{extension}"))
    return result


def copy_object(source: Minio, source_bucket: str, source_key: str,
                target: Minio, target_bucket: str, target_key: str):
    response = source.get_object(source_bucket, source_key)
    try:
        # Keep the stored bytes when the object has a Content-Encoding header.
        response.decode_content = False
        metadata = {key: value for key, value in response.headers.items()
                    if key.lower().startswith("x-amz-meta-") or key.lower() in COPY_HEADERS}
        target.put_object(
            target_bucket, target_key, response, length=int(response.headers["Content-Length"]),
            content_type=response.headers.get("Content-Type", "application/octet-stream"),
            metadata=metadata,
        )
    finally:
        response.close()
        response.release_conn()


def copy_item(source_node: Node, source: Minio, target_node: Node, target: Minio,
              source_path: str, destination: str):
    source_key = source_node.prefix + source_path
    target_key = target_node.prefix + destination
    keys = (source_key,)
    if source_path.endswith("/"):
        keys = (obj.object_name for obj in list_objects(source, source_node.bucket, source_key))
    result = {"source": source_path, "destination": destination, "copied": 0}
    current_key = source_key
    try:
        for current_key in keys:
            copy_object(source, source_node.bucket, current_key, target, target_node.bucket,
                        target_key + current_key[len(source_key):])
            result["copied"] += 1
    except STORAGE_ERRORS as error:
        app.logger.warning("MinIO copy failed: %s", getattr(error, "code", type(error).__name__))
        result.update(error="对象复制失败", failed_path=current_key[len(source_node.prefix):])
    else:
        if result["copied"] == 0:
            result["error"] = "来源目录已不存在，请刷新目录"
    return result


@app.post("/api/migrations")
def migrate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="请求体必须是 JSON 对象"), 400
    source_id, target_id, destination = (payload.get(key) for key in ("source", "target", "destination"))
    paths = payload.get("paths")
    if (not all(isinstance(value, str) for value in (source_id, target_id, destination))
            or not isinstance(paths, list) or not paths or not all(isinstance(path, str) for path in paths)):
        return jsonify(error="请选择来源节点、目标节点、目标目录和迁移条目"), 400

    nodes = app.config["MINIO_NODES"]
    if source_id not in nodes or target_id not in nodes or source_id == target_id:
        return jsonify(error="请选择两个不同的节点"), 400
    source_catalog, target_catalog = read_catalog(source_id), read_catalog(target_id)
    if source_catalog is None or target_catalog is None:
        return jsonify(error="请先刷新来源和目标节点的目录"), 409
    allowed = set(source_catalog["directories"]) | set(source_catalog["templates"])
    if not allowed.issuperset(paths) or (destination and destination not in target_catalog["directories"]):
        return jsonify(error="所选条目不在节点目录中，请刷新后重试"), 400

    source_node, target_node = nodes[source_id], nodes[target_id]
    suffix = f"_{source_id}_{datetime.now(BEIJING):%Y%m%d}"
    plan = migration_paths(paths, suffix)
    target = target_node.connect()
    target_prefix = target_node.prefix + destination
    occupied = {obj.object_name for obj in target.list_objects(target_node.bucket, prefix=target_prefix or None)}
    if destination and not occupied:
        return jsonify(error="目标目录已不存在，请刷新目录"), 409
    planned = set()
    for _, name in plan:
        key = target_prefix + name
        if key in occupied or key in planned:
            return jsonify(error="目标名称冲突，未写入任何对象", conflict=destination + name), 409
        planned.add(key)

    source = source_node.connect()
    results = [copy_item(source_node, source, target_node, target, path, destination + name)
               for path, name in plan]
    return jsonify(results=results, copied=sum(item["copied"] for item in results))


@app.errorhandler(MinioException)
@app.errorhandler(HTTPError)
@app.errorhandler(OSError)
def storage_error(error):
    app.logger.warning("Migration storage error: %s", getattr(error, "code", type(error).__name__))
    return jsonify(error="无法读取或写入节点目录，请检查后端连接和权限"), 502


if __name__ == "__main__":
    # ponytail: run serially on localhost. Move large batches to a worker if they block other operators.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8766")), threaded=False)
