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

## MinIO 模板迁移

在能访问各 MinIO 节点的电脑上运行迁移工具。它使用独立的本地入口 `http://127.0.0.1:8766`。

1. 运行 `python -m pip install -r requirements-migration.txt`。
2. 将 `minio_nodes.example.py` 复制为 `minio_nodes.local.py`，在副本里填入至少两个真实节点的地址、凭证和桶名。节点 ID 会写进迁移后缀，例如 `uat`。`prefix` 留空表示整个桶，填写时以 `/` 结尾，例如 `reportlets/`。私有配置和目录快照已从 Git 和 Docker 构建上下文排除。
3. 运行 `python minio_migration.py`。在页面选择来源、目标节点和目标目录，将所需目录或模板加入待迁移清单，再点击「开始迁移」。首次选择节点时会生成 `instance/minio-catalog/<节点 ID>.json`。节点内容变化后，点击「刷新全部节点目录」。

| 选择的来源条目 | 复制到目标目录后的路径 |
| --- | --- |
| `财务/` | `财务_uat_20261109/`，目录内的路径和文件名照原样复制 |
| `销售/日报.cpt` | `日报_uat_20261109.cpt` |

日期按北京时间取 `YYYYMMDD`。可单独选中 `.cpt`、`.frm` 和 `.fvs` 模板。复制时保留来源对象。目标同名时整批在写入前停止。若复制途中有对象失败，页面会显示该条目已复制的数量和失败路径，已写入的对象会留在目标节点。
