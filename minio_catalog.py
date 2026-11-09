"""MinIO object listing shared by the template scanner and migration tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minio import Minio

TEMPLATE_SUFFIXES = (".cpt", ".frm", ".fvs")


def list_objects(client: Minio, bucket: str, prefix: str):
    return client.list_objects(bucket, prefix=prefix or None, recursive=True)


def scan_catalog(client: Minio, bucket: str, prefix: str):
    directories = set()
    templates = []
    for obj in list_objects(client, bucket, prefix):
        path = obj.object_name[len(prefix):]
        start = 0
        while (slash := path.find("/", start)) != -1:
            directories.add(path[:slash + 1])
            start = slash + 1
        if path.lower().endswith(TEMPLATE_SUFFIXES):
            templates.append(path)
    return {"directories": sorted(directories), "templates": sorted(templates)}
