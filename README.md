# SmartSync

SmartSync 是一个会议转写与协作系统，支持录音上传、实时记录、逐字稿、AI 摘要、行动项和邮件分发。

## 快速部署

```bash
cp .env.server.example .env
# 填写数据库、管理员和 JWT 必填项
docker compose up -d --build
```

访问 `http://localhost:9090`，健康检查地址为 `http://localhost:9090/api/health`。

本地开发步骤见 [系统功能与本地部署说明.md](系统功能与本地部署说明.md)，服务器 HTTPS、备份和故障处理见 [Docker部署说明.md](Docker部署说明.md)。

