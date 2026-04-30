# SmartSync 服务器部署

此部署配置已精简，适用于不包含语音转写功能的服务器环境。

## 包含内容

- `mysql`
- `backend`（后端）
- `frontend`（前端）
- `nginx`

## 排除内容

- 本地 FunASR / FFmpeg 转写运行时
- 基于通义听悟的语音转写工作流
- 旧版 compose 文件中的 Worker 容器

## 必需配置

将项目根目录下的 `.env.server.example` 复制为 `.env`，并设置实际值。

## 启动方式

```bash
docker compose -f docker-compose.server.yml up -d --build
```

如果您的主机仅支持旧版独立命令，请使用：

```bash
docker-compose -f docker-compose.server.yml up -d --build
```

## 注意事项

- 当 `TRANSCRIPTION_ENABLED=false` 时，上传/转写 API 将被有意禁用。
- `/uploads/` 路径通过 Nginx 代理到后端的静态文件端点。
- 全新数据库需要先导入现有的基础业务表。应用程序仅自动创建部分运行时表和列。
