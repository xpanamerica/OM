# 数据库迁移 Runbook

## 开发环境

```bash
docker compose exec api alembic upgrade head
```

## 生产注意

1. **先备份** PostgreSQL（快照或 `pg_dump`）。
2. 在维护窗口或低峰执行 `alembic upgrade`；大表变更需评估锁时间与 `CONCURRENTLY` 索引策略。
3. 迁移与发版顺序：通常 **先迁移后发版**（向后兼容的 DDL）；若需先发版后迁移，必须保证新旧代码兼容同一 schema 过渡期。
4. 回滚：优先使用 **前向修复迁移**；`alembic downgrade` 仅在开发/预发验证，生产慎用。

## 新增迁移

```bash
docker compose exec api alembic revision --autogenerate -m "描述"
```

生成后务必人工检查 `upgrade()`，避免误删列/索引。
