# SmartSync Server Deployment

This deployment profile is trimmed for server use without speech transcription.

## What is included

- `mysql`
- `backend`
- `frontend`
- `nginx`

## What is excluded

- Local FunASR / FFmpeg transcription runtime
- Tingwu-based speech transcription workflow
- Worker container from the legacy compose file

## Required configuration

Copy `.env.server.example` to `.env` in the project root and set real values.

## Start

```bash
docker compose -f docker-compose.server.yml up -d --build
```

If your host only provides the legacy standalone command, use:

```bash
docker-compose -f docker-compose.server.yml up -d --build
```

## Notes

- The upload/transcription API is intentionally disabled when `TRANSCRIPTION_ENABLED=false`.
- `/uploads/` is proxied through Nginx to the backend static files endpoint.
- A brand-new database still needs the existing base business tables imported first. The app only auto-creates some runtime tables and columns.
