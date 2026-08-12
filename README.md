# SQL Table Extractor

一个基于 [sqlglot](https://github.com/tobymao/sqlglot) 的公开 Web 服务，用于从 SQL 中提取引用的物理表名。

## API

```http
POST /api/extract
Content-Type: application/json

{
  "sql": "SELECT * FROM analytics.events",
  "dialect": "mysql"
}
```

`dialect` 可以留空。服务也提供 `GET /health` 健康检查。

## 本地运行

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
python sql_table_server.py
```

打开 <http://localhost:8765>。

## 部署到 Railway

1. 在 Railway 新建项目并选择 **Deploy from GitHub repo**。
2. 选择此仓库并开始部署。Railway 会自动读取 `railway.json` 和 `Dockerfile`。
3. 在服务的 **Settings > Networking** 中点击 **Generate Domain**。

服务自动监听 Railway 提供的 `PORT`，不需要添加环境变量。
