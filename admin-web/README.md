# 管理后台（阶段 17.1）

Vue 3 + Vite + TypeScript + Element Plus + Axios + Pinia + Vue Router。

## 配置

复制 `.env.example` 为 `.env.local`（或修改 `.env.development`），设置：

- `VITE_API_BASE_URL`：后端根路径，须包含 `/api/v1`。与 **local-beta** 一并使用时推荐 `http://127.0.0.1:8081/api/v1`（先启动 `docker-compose.local-beta`）；若仅跑 `backend/docker-compose` 的 API，则用 `http://127.0.0.1:8000/api/v1`。

## 运行

```bash
cd admin-web
npm install
npm run dev
```

默认开发端口：`5174`（见 `vite.config.ts`）。

## 说明

- 仅 **管理员** 可登录；登录后调用 `GET /users/me` 校验 `role === "admin"`。
- JWT 存于 `localStorage`，Axios 请求头自动附加 `Authorization: Bearer …`；非登录请求的 **401** 会清空会话并跳转登录页。
