# 阶段 20.2：Capacitor 将用户端 H5 封装为 iOS / Android App（最小壳）

目标：不重写 Vue 前端业务代码、不改后端；仅增加原生工程壳与构建链路。

---

## 1. 已在本仓库完成的内容

| 项 | 说明 |
|----|------|
| 依赖 | `@capacitor/core`、`@capacitor/cli`、`@capacitor/ios`、`@capacitor/android`（Capacitor 6.x） |
| 配置 | 根目录 `capacitor.config.ts`：`appId: com.ommedia.user`（拉丁路径标识 **OM_Media**），`appName: 恒频OM`，`webDir: dist` |
| Web 构建 | `npm run build:cap` → `vite build --base ./`（**嵌入 WebView 时必须相对 base**，否则静态资源路径错误） |
| 平台 | 已执行 `cap add android`、`cap add ios`，生成 `android/`、`ios/` |
| API 环境 | `.env.capacitor.example` 说明 `VITE_API_BASE_URL` 须为**绝对 HTTPS URL**（推荐） |
| 明文 HTTP（仅开发） | `capacitor.config.ts` 中 `server.cleartext: true`；Android 另附 `usesCleartextTraffic`；iOS：`NSAllowsLocalNetworking` |
| 同步 | `npm run cap:sync`（将 `dist` 拷贝进原生工程） |

---

## 2. 环境要求

### 通用

- Node.js 20+（与现有 Vite 工程一致）
- 在 **`user-web` 目录**下执行所有 `npm` / `cap` 命令

### Android

- Android Studio（含 Android SDK、JDK 17）
- 首次打开 `android/` 后按提示安装 Gradle / SDK

### iOS（仅 macOS）

- Xcode + **CocoaPods**（`sudo gem install cocoapods` 或使用 brew）
- 本仓库在 Linux 上执行 `cap add ios` 时若未安装 CocoaPods，会提示跳过 `pod install`；请在 **Mac** 上进入 `ios/App` 执行 `pod install` 后再用 Xcode 打开。

---

## 2.1 打开原生工程（把「可打开」稳定到 10/10）

### Android Studio（必做）

1. **打开目录**：用 Android Studio 打开 **`user-web/android`**（该文件夹根，不要只打开 `app` 子目录）。  
2. **SDK 路径**：若 Sync 报找不到 SDK：复制 `android/local.properties.example` → `android/local.properties`，将 `sdk.dir=` 改为本机 SDK 绝对路径；或让 Android Studio 自动生成 `local.properties`。  
3. **自检脚本**（可选）：在 `user-web` 执行 `npm run android:check-sdk`，确认 `sdk.dir` 已配置。  
4. **Gradle**：已加大 Daemon 内存并开启并行与缓存（`android/gradle.properties`），降低首次索引/Sync OOM 概率。

### Xcode（必做）

1. **先装 Pods**（macOS，在 `user-web` 目录）：`npm run ios:pods`  
   （等价于执行 `bash scripts/ios-pod-install.sh`，内部为 `cd ios/App && pod install`）  
2. **打开工作区**：必须用 Xcode 打开 **`ios/App/App.xcworkspace`**。  
   **不要**只打开 `App.xcodeproj`，否则 Pods 未链接，表现为编译错误或白屏，易被误判为「项目打不开」。  
3. 若 `pod install` 失败，先执行 `pod repo update` 或检查 Ruby / Xcode Command Line Tools。

---

## 3. 配置 `VITE_API_BASE_URL`（API_BASE_URL）

前端代码使用环境变量 **`VITE_API_BASE_URL`**（见 `src/api/http.ts`），在 **构建 `dist` 时** 写入产物。

1. 复制示例：  
   `cp .env.capacitor.example .env.production`  
   （或在 CI 中注入同名变量）
2. 编辑 `.env.production`，将 `VITE_API_BASE_URL` 设为**完整绝对地址**，例如：  
   `https://api.example.com/api/v1`  
   **不要用** 仅路径形式 `/api`（WebView 内无法解析主机）。
3. 执行：`npm run build:cap && npm run cap:sync`

---

## 4. App 内网络请求说明（不重写前端、不改后端）

- 仍使用现有 **axios**；请求发往 `VITE_API_BASE_URL` 指向的服务器。
- **HTTPS**：生产环境强烈建议 API 为 HTTPS，避免 ATS / 证书问题。
- **HTTP 仅本机调试**：已放宽 **Android 明文** 与 **iOS 本地网络 HTTP**；访问公网 HTTP 仍可能被系统拦截，请改用 HTTPS。
- **CORS / 允许来源**：浏览器与 WebView 会带 `Origin`。若后端校验 CORS，请在部署配置里为 **`CORS_ORIGINS`**（或等价配置）增加 WebView 使用的来源。常见需尝试的值包括（按实际抓包为准）：
  - `capacitor://localhost`
  - `ionic://localhost`
  - `http://localhost`
  - 若出现字面量 **`null`** Origin，需在网关或后端策略中单独评估（最小壳阶段建议优先使用 **HTTPS + 明确域名** 以减少异常 Origin）。

> 不改后端代码 ≠ 不改后端**配置**：仅通过环境变量 / 反向代理增加允许的 Origin 即可。

---

## 5. 安全域名 / HTTPS 要点

| 平台 | 建议 |
|------|------|
| **生产** | API 与静态资源均使用 **HTTPS**；上架前移除 Android `usesCleartextTraffic`（若不再需要 HTTP）。 |
| **iOS ATS** | 生产依赖有效证书；仅调试本地 API 时使用已添加的 `NSAllowsLocalNetworking`。 |
| **证书** | 自签名证书需在系统或网络库中信任，否则 axios 会失败；上架请使用公信 CA。 |

---

## 6. 日常命令（复制即用）

在仓库根下先进入用户端：

```bash
cd "/home/xixiang2025/OM/user-web"
```

### 安装依赖（首次）

```bash
npm install
```

### 构建 Web 并同步到原生工程

```bash
npm run build:cap
npm run cap:sync
```

### 打开原生 IDE

```bash
npm run cap:open:android   # Android Studio
npm run cap:open:ios       # Xcode（仅 macOS）
```

### 命令行运行（需本机 SDK / 模拟器）

```bash
npm run cap:run:android
npm run cap:run:ios
```

### 仅 Web 发布（非 App，仍用绝对 base）

```bash
npm run build
```

---

## 7. 修改 `appId` / `appName`

编辑根目录 `capacitor.config.ts` 中 `appId`、`appName`，然后：

```bash
npm run cap:sync
```

iOS 若已生成工程，可能还需在 Xcode 中调整 **Bundle Identifier** 与显示名以保持一致。

---

## 8. 故障排查简表

| 现象 | 检查 |
|------|------|
| 白屏 / 静态 404 | 是否使用 `npm run build:cap`（`--base ./`），并已 `cap sync` |
| 接口连不上 | `VITE_API_BASE_URL` 是否为绝对 URL；真机是否访问得到该主机（不能用仅电脑可访问的 `127.0.0.1`，除非 USB 调试代理） |
| CORS 报错 | 后端允许的 Origin 是否包含 WebView 实际 Origin（抓包或 Chrome `remote debugging`） |
| Android 明文失败 | `usesCleartextTraffic` 是否仍存在；是否应改为 HTTPS |
| iOS 编译失败 | Mac 上 `cd ios/App && pod install`；Xcode 版本与 Capacitor 6 是否匹配 |

---

## 9. 真机访问本机 API（可选）

默认 `http://127.0.0.1:8000` 在**手机**上指向手机自身。调试请改为：

- 电脑局域网 IP，例如 `http://192.168.1.10:8000/api/v1`，或  
- 使用 `adb reverse`（Android）等端口转发方案。

并在后端 `CORS_ORIGINS` 中允许对应来源或使用 HTTPS 隧道。

---

## 10. 版本与升级

当前锁定 Capacitor **6.x**。升级大版本前请阅读官方迁移指南并重新执行 `npm run cap:sync`。

---

## 11. 发布前终审清单（勾选版）

> 仓库根目录执行 `bash scripts/verify-all.sh` 已包含：`user-web` 的 `build` +（若存在 `android/`）`build:cap` 与 `cap sync`。

- [ ] `npm run build`（Web 部署用，`base` 为 `/`）成功  
- [ ] `npm run build:cap && npm run cap:sync`（App 嵌入用，`base` 为 `./`）成功  
- [ ] Android Studio 可打开 `user-web/android`，`local.properties` 中 `sdk.dir` 已配置（或 IDE 已生成）  
- [ ] Xcode 已打开 **`App.xcworkspace`**，且已执行 `npm run ios:pods`（或等价 `pod install`）  
- [ ] **真机**：可登录（Token / 跳转正常）  
- [ ] **真机**：可播放（PlayAuth、Aliplayer 加载、弱网重试可接受）  
- [ ] **真机**：可评论、点赞、收藏（含未登录→登录回流）  
- [ ] 生产 API 为 **HTTPS**；计划上架则评估是否移除 `usesCleartextTraffic` / 收紧 `cleartext`  
- [ ] 后端 **`CORS_ORIGINS`**（或网关）已包含 App WebView 实际 `Origin`  

---

## 12. 「满分」把关说明（工程诚实）

- **不存在**脱离标尺的绝对满分；上表全勾选 + 生产 HTTPS + 上架审核通过，即可视为**本阶段 Capacitor 壳与链路的工程满分**。  
- 未在本节列出的项（如渗透测试、无障碍审计、全机型矩阵）属于**扩展标尺**，需另立项。
