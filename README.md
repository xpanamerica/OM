# 恒频OM

视频知识平台（后端 API + 编排配置）。**业务代码与文档主体在 `backend/` 目录。**

## 新人从这里开始

1. 打开并阅读：**[`backend/README.md`](backend/README.md)**（含 **「4.5 启动前检查」**与 **`/home/xixiang2025/OM` 实际路径说明**；项目简介、技术栈、目录、环境变量、本地启动、迁移、测试、常见问题）。克隆目录名建议 **`OM`**（本文档已使用实际路径 **`/home/xixiang2025/OM`**）；界面品牌文案仍为 **「恒频OM」**。
2. 部署与运维：**[`backend/docs/DEPLOYMENT.md`](backend/docs/DEPLOYMENT.md)**。
3. 接口速览：**[`backend/docs/API_OVERVIEW.md`](backend/docs/API_OVERVIEW.md)**。
4. 上线检查：**[`backend/docs/RELEASE_CHECKLIST.md`](backend/docs/RELEASE_CHECKLIST.md)**（含 Compose 烟测命令；CI 与 `make verify-compose-smoke` 同源）。

## 仓库根目录说明

| 路径 | 说明 |
|------|------|
| `backend/` | FastAPI 应用、`docker-compose.yml`、`alembic/`、`tests/`、`.env.example` |
| `backend/docs/` | 架构与 Runbook（含本阶段新增部署/API/清单文档） |
| `.vscode/` | 工作区解释器与终端配置（见 `backend/README.md` 中 Cursor 说明） |
| `.gitignore`（根目录） | 忽略根级 `.env` 等；`backend/.gitignore` 覆盖后端目录 |
| `AGENTS.md` | 给 Agent 的终端/conda 约定 |
| `scripts/dev-admin-web.sh`、`scripts/dev-user-web.sh` | 在正确目录启动前端并自动校验 `.env.local`（勿在 `backend/` 下执行 `npm`） |
