# 阿里云 OSS / VOD 对接 Runbook

面向：在 **第一版仅用 `video_url` / `cover_url` 外链** 上线后，将媒资逐步迁到 **阿里云 OSS** 与可选 **视频点播 VOD** 的团队。本页为运维与后端协作清单，**非阿里云官方文档替代品**；开通与 API 细节以控制台与 [阿里云文档中心](https://help.aliyun.com/) 为准。

---

## 1. 前置与账号

| 项 | 说明 |
|----|------|
| 主账号 / RAM | 使用 **RAM 子用户** + **最小权限策略**（仅 OSS、VOD 所需 Action），禁止把主账号 AK 写入应用。 |
| 地域 | OSS Bucket、VOD（若开）、ECS/K8s、RDS 尽量 **同地域**，降低延迟与跨域流量费。 |
| 凭证注入 | **AccessKey** 仅通过环境变量 / K8s Secret / 密钥管家注入；**禁止**提交到 Git。生产优先 **RAM 角色 + ECS/SA 绑定** 或 **OIDC**，避免长期 AK。 |

---

## 2. 第一版（当前模型）：外链不变

- API 已支持 **`videos.video_url`**、**`cover_url`** 存 HTTPS URL。
- 运维侧：在 OSS 控制台上传对象 → 绑定 **自定义域名 + CDN** → 将 **可公网访问的 URL**（或带签名的短期 URL）写入业务库或经管理端录入即可。
- **无需**本阶段改应用代码；仅需在 **`architecture.md`** 与产品侧约定「谁生成 URL、有效期多长」。

---

## 3. OSS：对象存储与访问形态

### 3.1 Bucket 与权限

1. 创建 Bucket：**私有读写**（推荐）或 **公共读 + 仅写鉴权**（按合规评估）。
2. 对外播放/封面：通过 **CDN 回源 OSS** 或 **应用签发签名 URL**（`Expires` 短时效），避免长期暴露永久直链。
3. RAM 策略示例方向：`oss:GetObject`（限定 `arn:...:bucket/your-bucket/*`）、`oss:PutObject`（若服务端上传）。

### 3.2 与本仓库的衔接方式（演进）

| 方式 | 适用 | 后端改动量级 |
|------|------|----------------|
| A. 仅 **`video_url` 存最终 URL** | 上传在控制台/单独工具完成 | 无或仅管理端表单 |
| B. 服务端 **直传 / 分片上传** 到 OSS | 用户上传视频 | 新增 `app.infrastructure` OSS 客户端 + 上传接口；落库仍写 `video_url` |
| C. 存 **`oss_object_key` + 动态签名** | 强私有、短链 | 新增列 + 读时生成 URL 的 service |

建议在 **Alembic 迁移** 中增加可选列（示例）：`oss_bucket`、`oss_object_key`、`cover_oss_object_key`；与 `video_url` **并存过渡期** 内由读路径优先解析新列，再下线纯外链。

---

## 4. VOD（视频点播）：可选增强

在需要 **转多码率、加密播放、播放统计** 时再启用 VOD。

1. **控制台**：开通视频点播 → 存储设置关联 OSS（或 VOD 托管存储）→ 配置 **分类/工作流模板**（转码、截图封面）。
2. **上传**：服务端或客户端拿 **上传凭证**（STS 或 VOD UploadAuth）→ 上传后得到 **VideoId / MediaId**。
3. **播放**：前端用 **阿里云播放器 SDK** + 服务端下发的 **PlayAuth**（或私有加密方案）；**勿**把永久播放 URL 写死进公开 API 响应（除非已走 CDN 鉴权）。
4. **回调**：配置 **HTTP(S) 回调**（转码完成、截图完成）→ FastAPI 增加 **仅内网可达** 的回调路由，校验 **签名 / 来源 IP**，再更新库内状态与 `cover_url` / `video_url`（或专用播放信息字段）。

---

## 5. 网络与安全

- **回调 URL**：仅对阿里云出口 IP 或 **固定反代 + mTLS** 开放；路径不可猜测，建议随机前缀 + 服务端校验。
- **CORS**：若浏览器直传 OSS，在 **OSS CORS 规则** 与 **`CORS_ORIGINS`** 中显式列出前端 Origin；生产禁止 `*`。
- **TLS**：对外仍由 **Nginx / SLB** 终止 TLS，与 **`DEPLOYMENT.md`** 一致。

---

## 6. 发版与迁移顺序（建议）

1. **备份** PostgreSQL；在低峰执行 **Alembic** 增加可选列与索引。
2. **先发版** 兼容读写（新列可为空，读逻辑仍 fallback `video_url`）。
3. **回填** 历史数据：脚本将外链解析为 `oss_object_key`（若可映射）或保持 `video_url`。
4. **切换**：新上传走 OSS/VOD；监控错误率后再收紧旧路径。
5. **回滚预案**：保留 `video_url` 直至全量验证完成；迁移脚本可逆或前向修复。

更细的迁移节奏见同目录 **[`migrations.md`](migrations.md)**。

---

## 7. 验证清单（上线前勾）

- [ ] RAM 权限最小化；生产无长期 AK 落盘。
- [ ] Bucket 私有 + CDN/签名策略符合合规。
- [ ] `video_url` / 新列在 **仅已发布** 视频上对匿名/普通用户暴露范围与产品一致。
- [ ] VOD 回调（若有）带签名校验、超时与幂等。
- [ ] 监控：OSS 4xx/5xx、VOD 转码失败、回调延迟。

---

## 8. 参考链接（外链）

- [对象存储 OSS 文档](https://help.aliyun.com/product/31815.html)
- [视频点播 VOD 文档](https://help.aliyun.com/product/29932.html)
- [RAM 访问控制](https://help.aliyun.com/product/28625.html)

架构总览与「第一版外链 → 后续 VOD/OSS」边界见 **[`../architecture.md`](../architecture.md)** 中「视频与媒体」一节。

---

## 9. 阶段 11.1：上传凭证 API 烟测（后端）

前提：`backend/.env` 已配置 **`ALIYUN_ACCESS_KEY_ID`**、**`ALIYUN_ACCESS_KEY_SECRET`**、**`ALIYUN_VOD_REGION`**（如 `cn-shanghai`），且已 `pip install -r requirements.txt`（含 **`alibabacloud-vod20170321`**）。栈已起、用户已注册登录。

1. 取 Token：`POST /api/v1/auth/login`（OAuth2 表单，`username` / `password`）。
2. 调用：**`POST /api/v1/uploads/vod/create-upload-video`**  
   JSON 示例：`{"title":"测试","filename":"demo.mp4","description":"可选","cover_url":"可选HTTPS"}`  
3. 期望 **HTTP 200**，体中含 **`video_id_from_vod`**、**`upload_address`**、**`upload_auth`**、**`request_id`**；**不应**出现 AccessKey 明文。
4. 未配置阿里云变量时，接口返回 **503**，`code` 为 **`VOD_CONFIG_INCOMPLETE`**（单测已覆盖）。
5. 自动化：`cd backend && pytest tests/test_vod_upload_phase111.py -q`（Mock SDK，不消耗阿里云配额）。
