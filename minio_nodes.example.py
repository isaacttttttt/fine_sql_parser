MINIO_NODES = {
    "uat": {
        "endpoint": "uat.example.invalid:9000",
        "access_key": "填写来源节点的 Access Key",
        "secret_key": "填写来源节点的 Secret Key",
        "bucket": "finereport",
        "prefix": "reportlets/",
        "secure": True,
    },
    "prod": {
        "endpoint": "prod.example.invalid:9000",
        "access_key": "填写目标节点的 Access Key",
        "secret_key": "填写目标节点的 Secret Key",
        "bucket": "finereport",
        "prefix": "reportlets/",
        "secure": True,
    },
}
