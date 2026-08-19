# SmartSync

SmartSync 是一个会议转写与协作系统，包含录音上传、实时记录、逐字稿、AI 摘要、行动项和邮件分发。

## 本地启动

需要 Python 3.11+、Node.js 20+ 和 MySQL 8.0。

### 1. 配置后端

```powershell
Copy-Item .env.example backend/.env
notepad backend/.env
```

至少填写 `MYSQL_HOST`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB` 和 `SECRET_KEY`。转写、LLM、邮件功能按需再填写对应配置。

安装后端依赖：

```powershell
Set-Location backend
python -m pip install -r requirements.txt
Set-Location ..
```

初始化空数据库：

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS smartsync CHARACTER SET utf8mb4;"
mysql -u root -p smartsync -e "source backend/基础表.sql"
```

首次创建管理员：

```powershell
$env:ADMIN_USERNAME = "admin"
$env:ADMIN_PASSWORD = Read-Host "管理员密码"
$env:ADMIN_NAME = "管理员"
Set-Location backend
python -m scripts.bootstrap_admin
Set-Location ..
```

管理员密码至少 8 个字符，项目不提供固定默认密码。

### 2. 启动后端

```powershell
Set-Location backend
python -m uvicorn app.main:app --reload --port 8000
```

健康检查：<http://127.0.0.1:8000/health>

### 3. 启动前端

新开一个终端：

```powershell
Set-Location frontend
npm install
npm run dev
```

浏览器访问终端输出的地址，默认是 <http://127.0.0.1:3333>。

## Docker 部署

服务器部署使用 `docker-compose.yml` 和 `.env.server.example`：

```bash
cp .env.server.example .env
# 填写 MYSQL_PASSWORD、MYSQL_ROOT_PASSWORD、ADMIN_PASSWORD、SECRET_KEY
docker compose up -d --build
curl -fsS http://127.0.0.1:9090/api/health
```

完整的 HTTPS、备份和故障处理说明见 [Docker部署说明.md](Docker部署说明.md)。

## 提交前检查

- 不提交 `.env`、上传文件、数据库备份和日志。
- 所有 Access Key、API Key、数据库密码和管理员密码仅保存于本地环境变量或密钥管理服务。
- 已经在 Git 历史中出现过的凭据必须先在服务商控制台轮换。
