# 新手一步一步：本机当服务器，让外面的用户注册并登录

---

## 本文档怎么用（可编辑、可复制）

你可以把本文件当成**本地备忘模板**，随意改、随意另存，不影响仓库里其它代码。

| 你想做的事 | 怎么做 |
|------------|--------|
| **整篇复制到别处编辑** | 在 VS Code / Cursor：**右键编辑器标签 → Copy Path**，或「文件 → 另存为」保存到桌面，改名为例如 `我的外测步骤.md`；或用记事本打开本 `.md` 后**全选 → 复制**到 Word / 飞书文档均可。 |
| **只复制终端命令** | 下面凡是 **` ```bash `** 代码块里的内容，在预览或源码视图里**只选中代码块内部**再复制，不要把表格里的竖线 `|` 复制进去。 |
| **全文查找替换路径** | 本指南已填写本机实际项目根目录 **`/home/xixiang2025/OM`**，可直接复制命令执行。 |

文中 **`/home/xixiang2025/OM`**：本机**仓库根目录的完整路径**（该目录下应有 `docker-compose.local-beta.yml`）。本机可直接复制执行；若换到另一台机器，再改成那台机器的实际克隆路径。

**请勿**把填写了真实数据库密码、隧道 **token** 的文档上传到公开网盘或提交到 Git。

---

### 我的填写区（建议先填这里，再往下做）

把下面这一段**复制到你的备忘录或本文档顶部**，用于记录本机路径和外测账号信息。

```
/home/xixiang2025/OM        = 本机实际项目根目录
【数据库密码备忘】    = （与 .env 里 POSTGRES_PASSWORD / DATABASE_URL 一致，勿含复杂符号则可免 URL 编码）
【管理员邮箱】        = （FIRST_SUPERUSER_EMAIL）
【管理员登录密码备忘】= （FIRST_SUPERUSER_PASSWORD，至少 8 位）
【ngrok Authtoken】   = （仅在终端执行 ngrok config 时用，勿写入要公开的文档）
【Cloudflare 隧道】   = （每次 cloudflared 启动后终端里出现的 https://….trycloudflare.com，每次可能不同）
```

---

本文面向**没有技术背景**的操作者，配合本仓库 **`deploy/local-beta/README.md`** 使用。你只要按顺序做，不要跳步。

---

## 先理解四件事（不用记英文）

1. **项目根目录**：就是你电脑里本仓库所在的文件夹，里面能看到 `docker-compose.local-beta.yml`、`backend`、`user-web` 等；本机实际完整路径为 **`/home/xixiang2025/OM`**。
2. **Docker**：在电脑上装好的「容器环境」，用来一键启动数据库、网站后台程序，你不用自己装 PostgreSQL。
3. **本机先能打开**：先在**你自己的电脑浏览器**里用 `http://127.0.0.1:8080` 打开用户网站，确认注册、登录正常。
4. **外面的用户怎么进来**：你家里的路由器一般**不会**把网站直接暴露给互联网。要让朋友用手机访问，需要再装一个**隧道工具**（下文用 **Cloudflare Tunnel** 或 **ngrok**），它会给你一个 **`https://……` 的链接**，把这个链接发给朋友即可。  
   - **注意**：只发这个 **https 链接**，不要把数据库密码、后台管理链接随便公开。  
   - **ngrok**：在控制台复制你自己的 **Authtoken**，终端执行 `ngrok config add-authtoken 3CwDh1opQYONyOrGQ3OgV7Se1NP_4nyXjdMskQJVjEYJn9Nue'`（只需配置一次；**勿**把真实 token 写进要公开的文档、截图或 Git），再执行 `ngrok http http://127.0.0.1:8080`；详见下文 **「方案 B：ngrok」**。

【整个更新栈指令】在仓库根执行（下面 `cd` 已使用本机实际路径 **`/home/xixiang2025/OM`**；若未初始化 Git，不要用 `git rev-parse`，直接 `cd` 到含 `docker-compose.local-beta.yml` 的文件夹）：

```bash
cd "/home/xixiang2025/OM"
chmod +x deploy/local-beta/build-and-up.sh
./deploy/local-beta/build-and-up.sh
```

【后台打开指令】（仍在仓库根）

```bash
chmod +x scripts/dev-admin-web.sh
./scripts/dev-admin-web.sh
```

【Cloudflare 固定域名打开指令】用户站 `https://app.omhengpin.com`，管理端 `https://admin.omhengpin.com`：

```bash
cd /home/xixiang2025/OM
set -a
. ./deploy/cloudflare-tunnel/.env
set +a

docker compose \
  --profile user-tunnel \
  --env-file ./backend/.env.local-beta \
  -f docker-compose.local-beta.yml \
  -f docker-compose.cloudflare-tunnel.yml \
  up -d --build
```

【Cloudflare 固定域名关闭指令】只关闭公网隧道，本机 `127.0.0.1:8080/8081` 仍可访问：

```bash
cd /home/xixiang2025/OM
set -a
. ./deploy/cloudflare-tunnel/.env
set +a

docker compose \
  --profile user-tunnel \
  --env-file ./backend/.env.local-beta \
  -f docker-compose.local-beta.yml \
  -f docker-compose.cloudflare-tunnel.yml \
  stop cloudflared cloudflared_user
```

验证固定域名：

```bash
cd /home/xixiang2025/OM
APP_URL=https://app.omhengpin.com \
ADMIN_URL=https://admin.omhengpin.com \
bash deploy/cloudflare-tunnel/verify_cloudflare_tunnel.sh
```



---

## 第一步：准备软件（只做一次）

在 **Linux** 或 **macOS** 上建议如下；若你是 **Windows**，请安装 **WSL2** 或 **Docker Desktop**，并在「终端」里操作（本指南中的路径已填写为 **`/home/xixiang2025/OM`**）。

1. **安装 Docker**（能运行 `docker compose`）  
   - 装好后，打开终端输入：`docker --version`  
   - 若能看到版本号，说明大致可用。

2. **安装 Node.js**（建议 18 或 20 版本）  
   - 终端输入：`node --version`  
   - 能看到版本号即可。

3. **准备一个文本编辑器**  
   - 用来改配置文件，例如 VS Code、gedit、记事本（Windows）均可。

---

## 第二步：找到项目根目录

1. 在文件管理器里进入**本仓库根目录**（里面应有 `docker-compose.local-beta.yml`）。
2. 在终端里进入该目录（已填写本机实际路径）：

```bash
cd "/home/xixiang2025/OM"
```

不确定路径时：在文件管理器中打开该文件夹，在空白处右键「在终端中打开」，一般就已经在正确目录了。

---

## 第三步：创建后端配置文件（最重要）

1. 在**项目根目录**（`/home/xixiang2025/OM`）下，进入文件夹 **`backend`**。
2. 找到文件 **` .env.local-beta.example `**（示例文件）。
3. **复制一份**，改名为 **` .env.local-beta `**（没有 `.example` 后缀）。  
   - Linux/macOS 终端（在 **`/home/xixiang2025/OM`** 下执行）：

```bash
cp backend/.env.local-beta.example backend/.env.local-beta
```

4. 用文本编辑器打开 **`backend/.env.local-beta`**，按下面说明修改（**每一处都要改**）：

| 要改的地方 | 你要做什么 |
|------------|------------|
| `POSTGRES_PASSWORD=` | 改成**你自己想的一个强密码**（英文字母+数字，建议 16 位以上），**记下来**。 |
| `DATABASE_URL=` 里 `postgres:` 后面的那一段密码 | 必须和上一行的 **`POSTGRES_PASSWORD` 完全一致**（这是数据库连接串）。若密码里有 `@`、`#` 等特殊符号，需要查资料做「URL 编码」，**新手建议密码只用字母和数字**，避免麻烦。 |
| `SECRET_KEY=` | 改成一长串随机字符（至少 32 个字符）。在终端执行下面命令，**复制输出的一整行**贴到 `SECRET_KEY=` 后面： |

```bash
openssl rand -hex 32
```

| `FIRST_SUPERUSER_EMAIL` / `USERNAME` / `PASSWORD` | 这是**第一个管理员**账号，用于登录 **管理后台**（端口 8081）。密码至少 8 位，**记下来**。 |
| 阿里云 VOD 相关 | **可留空**。视频会存到**本机服务器**（见示例里的 `LOCAL_VIDEO_STORAGE_DIR`），不必配阿里云也能上传与播放；若以后要用点播云端再按 `backend/.env.local-beta.example` 填写。 |

5. 保存文件。

---

## 第四步：构建用户网站和管理后台（各执行一遍）

在终端里执行（路径已使用本机实际根目录 **`/home/xixiang2025/OM`**，**整段复制粘贴**即可）：

### 4.1 用户网站（给普通用户注册、登录用）

```bash
cd "/home/xixiang2025/OM/user-web"
cp .env.production.example .env.production
npm ci
npm run build
```

等待结束，没有大量红色报错即可。

**若你用手机上的本应用 App（Android / iOS 壳）而不是浏览器**：请在 **`user-web`** 目录再执行一次 `npm run cap:copy`，否则 App 里仍是旧版创作页，会误走阿里云上传并报「VOD 未配置」。

### 4.2 管理后台（给管理员用，可选但建议）

```bash
cd "/home/xixiang2025/OM/admin-web"
cp .env.production.example .env.production
npm ci
npm run build
```

---

## 第五步：用 Docker 启动「本机服务器」

**先进入项目根目录** `/home/xixiang2025/OM`（该目录里要有 `docker-compose.local-beta.yml`；若你在 `user-web` 里，请先 `cd ..` 回到上一级）。

在终端执行：

```bash
cd "/home/xixiang2025/OM"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml up -d --build
```

（可选）一键构建两个前端并启动：仍在**根目录**执行 `./deploy/local-beta/build-and-up.sh`；若终端在 **`user-web`** 子目录，可执行 `npm run local-beta:up`。

第一次会下载镜像，可能较慢。完成后检查：

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml ps
```

四个服务 **`db`、`redis`、`api`、`nginx`** 都应是 **running** 或 **healthy**。

**若这里有 `Created` 或 `Exited`、没有 `running`**：说明没启动成功，**不要**直接去浏览器试 8080。请在同一目录再执行一次（看终端有没有红色报错）：

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml up -d
```

仍失败时，把下面两条命令的**完整输出**保存下来发给技术人员：

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml ps -a
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml logs nginx --tail=50
```

**说明**：本仓库的 Beta 方案默认把数据库、Redis 映射到本机 **`127.0.0.1:15432` 和 `127.0.0.1:16379`**，避免与你电脑上另一套开发环境（常见占用 **5432、6379**）冲突；**不影响**你在浏览器里访问 **`http://127.0.0.1:8080`**。

---

## 第六步：在你自己电脑上验证「注册 + 登录」

1. 打开浏览器（Chrome、Edge、Firefox 等）。
2. 地址栏输入：**`http://127.0.0.1:8080`** 回车。  
   - 应出现**用户端**网站。

**若 Firefox 提示「无法连接到 127.0.0.1:8080」**：先确认上一步四个容器都是 **running/healthy**，且你已执行过 **`npm run build`**（`user-web` 下要有 `dist` 文件夹）。然后在终端执行（能返回 `200` 即服务正常，再回浏览器刷新）：

```bash
curl -sS -o /dev/null -w "用户站健康检查 HTTP %{http_code}\n" http://127.0.0.1:8080/health
```

3. 找到 **「登录」或「注册」** 页面（本项目里一般在同一页的「注册」标签）。
4. **注册**：填邮箱、用户名、密码（按页面要求），提交。  
5. **登录**：用刚注册的账号登录。  
6. 若成功，说明**本机当服务器**已经通了。

#### 上传视频、附件，审核通过后出现在列表里

1. 在用户站进入 **「创作」**，填写**标题**，可选 **视频文件**（写入本机，**不要求**阿里云）、可多选 **附件**（图片、PDF 等），保存。  
2. 自动打开**详情页**后，点 **「提交审核」**。  
3. 用**管理员**打开 **`http://127.0.0.1:8081`** → **「视频审核」** → 对该稿点 **「通过」**。  
4. 回到用户站 **「视频」或首页**，即可看到这条**已发布**稿件。若当时上传失败，可在**同一详情页**补传本站视频或附件，再提交审核。

管理后台（管理员）：浏览器打开 **`http://127.0.0.1:8081`**，用第三步里 **`FIRST_SUPERUSER_*`** 设的账号登录。

---

## 第七步：让「外面的用户」也能打开（隧道）

**只有完成第六步后**再做本节。

### 方案 A：Cloudflare Tunnel（免费试用链接，较简单）

#### A1. 安装 `cloudflared`（不要用 `apt install cloudflared`，多数系统里没有这个包）

若出现 **`E: 无法定位软件包 cloudflared`**，请用下面**官方二进制**方式（任选一种 CPU 架构命令）。

先在终端看 CPU 架构：

```bash
uname -m
```

- 显示 **`x86_64`**：用 **amd64** 那条。  
- 显示 **`aarch64`** 或 **`arm64`**：用 **arm64** 那条。

**安装到当前用户目录（不需要 sudo，推荐）：**

```bash
mkdir -p "$HOME/.local/bin"
# x86_64 电脑用下面三行（amd64）：
curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o "$HOME/.local/bin/cloudflared"
# 若是 ARM 苹果本 / ARM Linux，请删掉上一行，改用下面这一行（arm64）：
# curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64" -o "$HOME/.local/bin/cloudflared"
chmod +x "$HOME/.local/bin/cloudflared"
```

把 `~/.local/bin` 加入 PATH（若从未加过，执行一次即可）：

```bash
grep -q '\.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
export PATH="$HOME/.local/bin:$PATH"
```

验证：

```bash
cloudflared --version
```

能输出版本号即安装成功。

**可选：系统级安装（需要 sudo）：**

```bash
sudo curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" -o /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared
cloudflared --version
```

（ARM 机器把 URL 里的 `amd64` 改成 `arm64`。）

#### A2. 启动隧道

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

终端里会出现一行 **`https://xxxx.trycloudflare.com`**（具体名字每次可能不同）。  
**复制这个 https 链接**发给朋友；对方在手机浏览器打开即可注册、登录。

**注意**：  
- 你**关掉终端**或**关机**后，链接会失效，需要重新运行 `cloudflared` 再发新链接。  
- **不要**把本机数据库端口（默认 **`15432` / `16379`**）或数据库密码发给任何人。

### 方案 B：ngrok

#### B0. 若你曾用旧教程里的 `bin.equinox.io` 下载却出现 **`curl: (22) 404`**

- 网上很多 **Equinox 直链已失效**，或包名写错：Linux ARM 机器应使用 **`linux-arm64`**，**没有** `linux-aarch64` 这种包名（写 `aarch64` 容易 404）。
- **你已能执行 `ngrok version`（例如 3.38.0）**：说明本机已有 ngrok，**不必再下载**；请直接从 **B2** 配置 token 后使用。

#### B1. 安装 ngrok（Debian / Ubuntu：用官方 apt 源，推荐）

在 [ngrok 控制台](https://dashboard.ngrok.com/) 注册账号。终端执行（整段可复制；来自 ngrok 官方 Linux 安装说明）：

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update \
  && sudo apt install -y ngrok
```

若 `apt install ngrok` 仍报错，请打开浏览器进入 **`https://ngrok.com/download`**，选 **Linux** 与你的 CPU（**ARM64** 或 **AMD64**），下载 **zip/tgz** 后解压，把其中的 `ngrok` 可执行文件放到 `~/.local/bin` 或 `/usr/local/bin` 并 `chmod +x`。

#### B2. 配置 authtoken（只需一次）

在 ngrok 控制台的 **Your Authtoken** 复制令牌，执行（把引号里换成你的 token）：

```bash
ngrok config add-authtoken '你的_NGROK_AUTHTOKEN'
```

#### B3. 启动隧道（用户站）

```bash
ngrok http http://127.0.0.1:8080
```

终端里会显示 **`Forwarding https://……ngrok-free……`**（或类似域名）；也可本机浏览器打开 **`http://127.0.0.1:4040`** 查看公网 URL。把 **https** 链接发给朋友即可。

管理端（可选，另开终端）：

```bash
ngrok http http://127.0.0.1:8081
```

---

## 第八步：常见问题（看一眼即可）

| 现象 | 可能原因 |
|------|----------|
| 浏览器打不开 8080 | ① 第五步是否四个服务都是 **running**；② 是否已 **`npm run build`** 生成 `user-web/dist`；③ 本机 **8080** 是否被别的程序占用（可请技术人员改 `BETA_USER_WEB_PORT`）。 |
| 注册没反应 / 一直转圈 | 看 API 日志：`docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml logs api --tail=100` |
| 隧道链接打开是空白或 502 | 本机 8080 先确认能打开；隧道命令里的端口必须是 **8080**（用户站）。 |
| 朋友打不开，只有我能打开 | 没用隧道，或路由器没做端口映射；**新手请只用隧道链接**，不要折腾路由器。 |
| `apt` 提示无法定位软件包 `cloudflared` | 正常现象；按上文 **A1** 用 GitHub 官方二进制安装，勿依赖 `apt install cloudflared`。 |
| `curl` 下载 ngrok 出现 **404** | 勿用失效的 `bin.equinox.io` 旧链接；勿用错误的 **`linux-aarch64`** 包名；按 **B1** 用 ngrok 官方 apt，或从 **https://ngrok.com/download** 手动下载。 |
| 管理后台提示**用户名或密码错误** | ① 地址必须是 **`http://127.0.0.1:8081`**（管理端），不是 8080 用户站。② 用 **`FIRST_SUPERUSER_EMAIL` 或 `FIRST_SUPERUSER_USERNAME`** + 密码。③ **只改 `.env` 里的密码不会改数据库**：在仓库根执行 **`chmod +x deploy/local-beta/scripts/reset_admin_password_in_db.sh`** 后运行 **`ADMIN_RESET_PASSWORD=你的新密码 ./deploy/local-beta/scripts/reset_admin_password_in_db.sh`**（默认 `admin2026`），再登录。④ 或 **`docker compose ... down -v`** 后 `up` 重建库（**会删库**）。⑤ 看日志：`docker compose ... logs api --tail=80`。 |

---

## 第九步：不用时怎么关掉

在 **`/home/xixiang2025/OM`** 下打开终端：

```bash
cd "/home/xixiang2025/OM"
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml down
```

数据默认会保留；若要**清空数据库**（慎用）：

```bash
docker compose --env-file ./backend/.env.local-beta -f docker-compose.local-beta.yml down -v
```

---

## 和官方文档的对应关系

| 你想深入看的 | 打开这个文件 |
|--------------|----------------|
| 完整命令、迁移、备份、验收清单 | **`deploy/local-beta/README.md`** |
| 后端环境每一项含义 | **`backend/.env.local-beta.example`** |
| 后端通用说明 | **`backend/README.md`** |

按本文从**第一步做到第七步**，即可实现：**本机当服务器 + 外网用户通过 https 链接注册并登录**。
