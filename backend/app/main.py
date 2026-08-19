from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import get_pool, close_pool, ensure_runtime_tables


def _log_prefix() -> str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

def _safe_print(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", errors="replace").decode("ascii"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    await ensure_runtime_tables()
    yield
    await close_pool()

app = FastAPI(title="AI会议助手 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3333", "http://127.0.0.1:3333", "http://localhost:5173", "http://localhost", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Never log query strings or bodies: they may contain passwords, API
        # keys, access tokens, meeting text, or short-lived realtime tickets.
        _safe_print(f"{_log_prefix()} REQUEST: {request.method} {request.url.path}")
        response = await call_next(request)
        _safe_print(f"{_log_prefix()} RESPONSE: {request.method} {request.url.path} {response.status_code}")
        return response

app.add_middleware(LoggingMiddleware)

uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

from app.routers import auth, upload, tasks, meetings, contacts, todos, templates, llm_configs, ai, search, notifications, settings, realtime
app.include_router(auth.router,     prefix="/auth",     tags=["auth"])
app.include_router(upload.router,                       tags=["upload"])
app.include_router(tasks.router,                        tags=["tasks"])
app.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
app.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
app.include_router(todos.router,    prefix="/todos",    tags=["todos"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
app.include_router(llm_configs.router, prefix="/llm-configs", tags=["llm-configs"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(realtime.router, prefix="/realtime", tags=["realtime"])

@app.get("/health")
async def health():
    return {"status": "ok"}
