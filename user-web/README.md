# 用户端 Web（阶段 17.2）

Vue 3 + Vite + TypeScript + Element Plus + Axios + Pinia + Vue Router。

## 环境变量

复制 `.env.example` 为 `.env.local`，设置：

- `VITE_API_BASE_URL`：后端根路径（含 `/api/v1`）。
  - 本地只跑 **`backend/docker-compose.yml`**（API 映射本机 **8000**）：例如 `http://127.0.0.1:8000/api/v1`。
  - **`deploy/local-beta` + Nginx**（用户站 **8080**、管理端 **8081** 同源反代）：开发调试可用 `http://127.0.0.1:8080/api/v1`；生产构建静态资源时常用 **`/api/v1`**（与页面同源，见 `.env.production.example`）。

## 运行

```bash
cd user-web
npm install
npm run dev
```

默认端口 `5173`。请在后端 `CORS_ORIGINS` 中允许该来源。

## 功能说明

- JWT 存 `localStorage`（`user_access_token`），请求自动带 `Authorization`。
- 视频详情：评论 CRUD、点赞/收藏、**调用 `GET /videos/{id}/play`** 后使用 PrismPlayer（CDN）播放；定时 **上报 `POST .../view-record`** 进度。
- 收藏列表依赖后端 **`GET /users/me/favorite-videos`**；概念详情依赖 **`GET /concepts/{id}`**；概念下视频列表为 **`GET /concepts/{id}/videos`**，响应体为 **`ConceptLinkedVideoOut`**（`VideoListItem` + 片段时间字段）；互动状态依赖 **`GET /videos/{id}/my-interactions`**。
