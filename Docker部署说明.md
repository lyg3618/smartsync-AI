# SmartSync Docker 部署说明

> 适用版本：2026-07-19  
> 部署入口：`docker-compose.yml`

本指南用于在 Linux 服务器上部署当前 SmartSync 项目。部署包含 MySQL、FastAPI 后端、Vue 前端和 Nginx 网关，并支持阿里云听悟离线/实时转写、Cloudflare R2 原录音存储、AI 会议分析和 SMTP 邮件分发。

## 1. 文件说明

| 文件 | 用途 |
| --- | --- |
| `docker-compose.yml` | 编排 MySQL、后端、前端和网关 |
| `.env.server.example` | 服务器环境变量模板 |
| `backend/Dockerfile` | Python 3.11 后端镜像 |
| `backend/docker-entrypoint.sh` | 启动 FastAPI 服务 |
| `backend/scripts/bootstrap_admin.py` | 根据环境变量创建首个管理员 |
| `backend/docker/init/001-schema.sql` | 空 MySQL 数据卷首次启动时创建完整业务表 |
| `frontend/Dockerfile` | 构建 Vue 应用并由 Nginx 提供静态文件 |
| `nginx/nginx.server.conf` | 统一转发页面、API、录音和 WebSocket |

当前 Compose 不包含 Celery Worker。录音转写通过 FastAPI 进程内后台任务执行，部署升级或重启前应等待正在执行的转写结束。

## 2. 架构和端口

```text
浏览器
  |
  v
gateway :9090
  |-- /          -> frontend:80
  |-- /api/      -> backend:8000
  `-- /uploads/  -> backend:8000/uploads/

backend -> mysql:3306
        -> 阿里云听悟
        -> Cloudflare R2
        -> OpenAI 兼容 LLM
        -> SMTP
```

默认只有网关端口 `9090` 映射到宿主机。MySQL、后端和前端不直接暴露到公网。

## 3. 环境要求

- Linux x86_64 或 ARM64 服务器
- Docker Engine 24 或更高版本
- Docker Compose v2
- 建议至少 2 核 CPU、4 GB 内存
- 足够保存数据库和原录音的磁盘空间
- 能访问 Docker Hub、Python/npm 依赖源、阿里云和 Cloudflare R2
- 实时麦克风功能需要域名和 HTTPS

确认环境：

```bash
docker --version
docker compose version
```

## 4. 首次部署

### 4.1 放置项目

```bash
sudo mkdir -p /opt/smartsync
sudo chown "$USER":"$USER" /opt/smartsync
cd /opt/smartsync
```

将项目代码放到此目录，确认存在 `docker-compose.yml`。

### 4.2 创建环境变量

```bash
cp .env.server.example .env
chmod 600 .env
nano .env
```

以下必填值默认留空，必须填写后才能通过 Compose 校验：

```dotenv
MYSQL_PASSWORD=使用随机数据库用户密码
MYSQL_ROOT_PASSWORD=使用另一组随机root密码
ADMIN_PASSWORD=使用不少于8个字符的管理员密码
SECRET_KEY=使用至少32字节的随机密钥
```

可生成随机密码和 JWT 密钥：

```bash
openssl rand -base64 36
openssl rand -hex 32
```

管理员配置：

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=使用强密码
ADMIN_NAME=系统管理员
ADMIN_EMAIL=admin@example.com
```

初始管理员只在 `ADMIN_USERNAME` 不存在时创建。后续修改 `.env` 中的 `ADMIN_PASSWORD` 不会覆盖数据库密码，请登录系统后修改密码。

### 4.3 配置听悟和 R2

需要转写时设置：

```dotenv
TRANSCRIPTION_ENABLED=true
TINGWU_ENABLED=true
TINGWU_ACCESS_KEY_ID=阿里云听悟AccessKeyID
TINGWU_ACCESS_KEY_SECRET=阿里云听悟AccessKeySecret
TINGWU_APP_KEY=听悟项目AppKey

TINGWU_S3_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
TINGWU_S3_BUCKET=R2_BUCKET_NAME
TINGWU_S3_REGION=auto
TINGWU_S3_PUBLIC_URL_BASE=
TINGWU_S3_URL_EXPIRES_SEC=14400
TINGWU_S3_ACCESS_KEY_ID=R2_ACCESS_KEY_ID
TINGWU_S3_ACCESS_KEY_SECRET=R2_SECRET_ACCESS_KEY
```

注意：

- R2 Endpoint 不包含 Bucket 名称。
- `TINGWU_S3_PUBLIC_URL_BASE` 保持为空，系统会生成 SigV4 预签名下载 URL。
- 听悟 AccessKey 和 R2 Access Key 是两组不同凭据。
- R2 Token 至少需要目标 Bucket 的对象读取和写入权限。
- 凭据曾出现在截图或日志中时，应先撤销并重新创建。

暂时不使用转写时设置：

```dotenv
TRANSCRIPTION_ENABLED=false
TINGWU_ENABLED=false
```

### 4.4 配置 AI 和 SMTP

AI 配置可以写入 `.env`，也可以登录后在系统设置中创建连接：

```dotenv
LLM_BASE_URL=https://llm.example.com/v1
LLM_MODEL=your-model
LLM_API_KEY=your-key
```

邮件分发配置：

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=account@example.com
SMTP_PASS=your-smtp-password
SMTP_FROM=SmartSync <noreply@example.com>
```

### 4.5 可选依赖镜像和代理

默认使用官方源：

```dotenv
PIP_INDEX_URL=https://pypi.org/simple
NPM_REGISTRY=https://registry.npmjs.org
HTTP_PROXY=
HTTPS_PROXY=
```

服务器需要国内镜像时可以改为：

```dotenv
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
NPM_REGISTRY=https://registry.npmmirror.com
```

代理只在确实需要时填写，不要把包含用户名和密码的代理地址提交到 Git。

### 4.6 检查并启动

先检查 Compose 渲染结果：

```bash
docker compose config --quiet
```

构建并启动：

```bash
docker compose up -d --build
docker compose ps
```

首次启动流程：

1. MySQL 创建数据库和应用账号。
2. MySQL 对空数据卷执行 `001-schema.sql`。
3. 一次性 `admin-bootstrap` 容器根据 `ADMIN_*` 创建首个管理员并退出。
4. 管理员初始化成功后启动后端。
5. 后端通过健康检查后启动前端和网关。

查看启动日志：

```bash
docker compose logs --tail=200 mysql
docker compose logs --tail=200 backend
docker compose logs --tail=100 gateway
```

### 4.7 验证

```bash
curl -fsS http://127.0.0.1:9090/api/health
```

正常返回：

```json
{"status":"ok"}
```

浏览器访问：

```text
http://SERVER_IP:9090
```

使用 `.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 登录，并立即在系统设置中修改初始密码。

## 5. 使用已有数据库

MySQL 初始化目录只会在 `mysql_data` 为空时执行。已有数据迁移建议使用下面的流程。

### 5.1 从旧环境导出

```bash
mysqldump \
  --single-transaction \
  --routines \
  --triggers \
  --default-character-set=utf8mb4 \
  -h OLD_DB_HOST -u OLD_DB_USER -p \
  smartsync > smartsync-backup.sql
```

### 5.2 首次启动 MySQL

```bash
docker compose up -d mysql
docker compose ps
```

等待 MySQL 为 `healthy`。

如果要完整恢复旧库，应在导入前确保目标库为空。对已经写入数据的目标库不要直接覆盖，先做好备份并确认迁移方案。

### 5.3 导入备份

```bash
docker compose exec -T mysql \
  sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < smartsync-backup.sql
```

然后启动其他服务：

```bash
docker compose up -d --build
```

后端启动时会为旧库补充部分运行时字段和表，但这不能替代完整的旧版本数据库迁移。导入前应保留原数据库备份。

## 6. HTTPS 和实时录音

浏览器只允许在 HTTPS 或 `localhost` 安全上下文中采集麦克风。服务器上的 `http://IP:9090` 可以用于离线上传测试，但实时记录通常无法获取麦克风权限。

推荐让宿主机 Nginx、Caddy、Traefik 或云负载均衡终止 TLS，再代理到 `127.0.0.1:9090`。

宿主机 Nginx 示例：

```nginx
server {
    listen 80;
    server_name meeting.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name meeting.example.com;

    ssl_certificate /etc/letsencrypt/live/meeting.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/meeting.example.com/privkey.pem;

    client_max_body_size 210m;

    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
}
```

如果宿主机已经有其他网关，建议在 `.env` 中限制 Docker 网关只监听本机：

```dotenv
APP_BIND_ADDRESS=127.0.0.1
APP_PORT=9090
```

验证 HTTPS 后应检查：

- 浏览器允许麦克风权限。
- `POST /api/realtime/ticket` 返回 200。
- `/api/realtime/ws` WebSocket 返回 101 Switching Protocols。
- 结束实时记录后能播放 `/uploads/realtime_*.wav`。

## 7. 日常运维

### 7.1 查看状态和日志

```bash
docker compose ps
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=100 gateway
```

Compose 已限制容器 JSON 日志文件大小，但仍应监控宿主机磁盘空间。

### 7.2 停止和启动

```bash
docker compose stop
docker compose start
```

删除容器但保留数据库和录音：

```bash
docker compose down
```

不要在生产环境执行 `docker compose down -v`，该命令会删除 MySQL 和录音数据卷。

### 7.3 更新应用

更新前先备份，且等待正在转写的任务完成：

```bash
git pull
docker compose build --pull
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:9090/api/health
```

仅修改 `.env` 后可执行：

```bash
docker compose up -d --force-recreate backend gateway
```

前端 `VITE_*` 配置在构建阶段写入，修改后必须重新构建前端。

## 8. 备份和恢复

### 8.1 备份 MySQL

```bash
mkdir -p backups
docker compose exec -T mysql \
  sh -c 'mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' \
  > "backups/smartsync-$(date +%F-%H%M%S).sql"
```

### 8.2 备份原录音卷

```bash
docker run --rm \
  -v smartsync_uploads_data:/data:ro \
  -v "$PWD/backups:/backup" \
  alpine sh -c 'tar czf /backup/uploads-$(date +%F-%H%M%S).tar.gz -C /data .'
```

Compose 项目名改变时，实际卷名会改变。先用下面的命令确认：

```bash
docker volume ls | grep smartsync
```

Cloudflare R2 中也保留了离线上传对象，应单独配置生命周期、版本控制或外部备份策略。

### 8.3 恢复数据库

恢复是有状态操作，必须先停止后端并确认目标数据库：

```bash
docker compose stop backend gateway
docker compose exec -T mysql \
  sh -c 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < backups/smartsync-backup.sql
docker compose start backend gateway
```

## 9. 常见故障

### 9.1 Compose 提示必填变量为空

如果看到 `Set MYSQL_PASSWORD in .env`、`Set ADMIN_PASSWORD in .env` 等错误，说明还没有创建 `.env` 或必填变量为空。

```bash
cp .env.server.example .env
nano .env
docker compose config --quiet
```

### 9.2 后端反复重启

```bash
docker compose logs --tail=200 backend
docker compose logs --tail=200 mysql
```

常见原因：

- 数据库密码和 MySQL 容器首次初始化时使用的密码不一致。
- 使用了旧数据卷，但其中没有 SmartSync 业务表。
- `ADMIN_PASSWORD` 少于 8 个字符。
- Python 依赖或外部网络不可用。

注意：修改 `.env` 中的 MySQL 初始化密码不会自动修改已有 MySQL 数据卷中的账号密码。

### 9.3 镜像构建无法下载依赖

- 检查服务器 DNS 和出口网络。
- 设置可用的 `PIP_INDEX_URL` 和 `NPM_REGISTRY`。
- 必要时设置 `HTTP_PROXY`/`HTTPS_PROXY`。
- 不要关闭 TLS 证书校验。

### 9.4 R2 返回 401 或 403

- Endpoint 只填写账户级地址，不带 Bucket。
- 使用 R2 S3 API Access Key，不是 Cloudflare API Token 字符串本身。
- Token 对目标 Bucket 有对象读写权限。
- `TINGWU_S3_REGION=auto`。
- 修改 `.env` 后重新创建后端容器。

### 9.5 听悟返回 Audio file link invalid

- 保持 `TINGWU_S3_PUBLIC_URL_BASE=` 为空。
- 不要提交 `r2.dev` 公共 URL。
- 开启服务器 NTP 时间同步。
- 保持预签名 URL 有效期为 14400 秒。
- 查看后端日志中的听悟 `ErrorCode` 和 `ErrorMessage`。

### 9.6 上传返回 413

Docker 网关为 200 MB 文件预留了 multipart 请求开销。若仍出现 413，需要同时调整最外层宿主机 Nginx、CDN 或负载均衡的上传限制。

### 9.7 实时转写连接失败

- 确认使用 HTTPS。
- 确认听悟实时记录权限和 AppKey。
- 确认后端镜像已安装 `nls 1.1.0`。
- 检查外层代理是否保留 WebSocket Upgrade 请求头。
- 查看 `docker compose logs backend`。

## 10. 安全要求

- 不提交 `.env`，文件权限保持 `600`。
- 轮换所有曾在截图、日志或聊天记录中出现的凭据。
- 使用最小权限的阿里云 RAM 用户和 R2 Bucket Token。
- 不向公网映射 MySQL 3306 或后端 8000。
- 首次登录后立即修改管理员密码。
- 仅通过 HTTPS 对外提供服务。
- 定期备份数据库、录音卷和 R2 对象，并实际演练恢复。
- 限制后端日志访问。当前请求日志可能包含业务数据和短期实时票据。

## 11. 验收清单

- [ ] `docker compose config --quiet` 通过
- [ ] MySQL、后端、前端和网关处于运行或健康状态，`admin-bootstrap` 正常退出（状态为 0）
- [ ] `/api/health` 返回 `{"status":"ok"}`
- [ ] 初始管理员可以登录并修改密码
- [ ] 上传录音后 R2 出现对象并完成离线转写
- [ ] 逐字稿包含发言人和时间轴
- [ ] HTTPS 页面可以授权麦克风并完成实时转写
- [ ] 实时 WAV 原录音可以播放
- [ ] AI 摘要、决议和行动项生成正常
- [ ] SMTP 行动项邮件可以送达
- [ ] MySQL 和录音卷备份已经配置
