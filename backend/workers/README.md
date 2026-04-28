# 异步任务（占位）

长耗时或削峰填谷的工作（转码回调处理、批量通知、统计汇总、对账）**不应**放在 API 请求线程内。

## 推荐演进

- 选型：Celery + Redis/RabbitMQ、RQ、ARQ、或云厂商队列。
- 代码位置：新增 `workers/tasks/` 与独立进程入口（如 `worker.py`），与 `app/main.py` 分离部署。
- 与 API 共享：`app/models`、`app.repositories`（只读场景）、`app.infrastructure`；**避免** worker import 过重的 `routes`。

当前 MVP 无队列进程；接入时在 CI/CD 中增加 worker 服务镜像与伸缩策略。
