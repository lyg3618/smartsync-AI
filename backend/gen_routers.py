# -*- coding: utf-8 -*-
import os

def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK:", path)

# meetings.py
w("app/routers/meetings.py", """
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

MEETINGS = {
    "1": {
        "id": "1", "name": "2026\u5e74Q1\u4ea7\u54c1\u89c4\u5212\u4f1a\u8bae", "date": "2026-03-01",
        "duration_sec": 3600, "task_count": 5, "status": "ready_for_review", "audio_url": None,
        "transcript": [
            {"id": 1, "start_ms": 0,     "end_ms": 12000,  "text": "\u5927\u5bb6\u597d\uff0c\u4eca\u5929\u4e3b\u8981\u8bae\u9898\u662fQ1\u4ea7\u54c1\u8def\u7ebf\u56fe\uff0c\u91cd\u70b9\u5173\u6ce8\u7528\u6237\u589e\u957f\u548c\u529f\u80fd\u8fed\u4ee3\u3002"},
            {"id": 2, "start_ms": 12000, "end_ms": 28000,  "text": "\u5f20\u4f1f\uff1a\u6839\u636e\u4e0a\u5b63\u5ea6\u6570\u636e\uff0cDAU\u8fbe50\u4e07\uff0c\u4f46\u7b2c7\u5929\u7559\u5b58\u7387\u52604035%\uff0c\u51fa\u73b0\u660e\u663e\u4e0b\u6ed1\u3002"},
            {"id": 3, "start_ms": 28000, "end_ms": 45000,  "text": "\u674e\u5a1c\uff1a\u4e3b\u8981\u539f\u56e0\u662f\u65b0\u7528\u6237\u5f15\u5bfc\u6d41\u7a0b\u592a\u590d\u6742\uff0c\u5efa\u8bae\u4ece7\u6b65\u7b80\u5316\u4e3a3\u6b65\u3002"},
            {"id": 4, "start_ms": 45000, "end_ms": 62000,  "text": "\u738b\u82b3\uff1a\u7528\u6237\u53cd\u9988\u901a\u77e5\u592a\u591a\uff0c\u6211\u6765\u8d1f\u8d23\u68b3\u7406\u901a\u77e5\u7b56\u7565\uff0c\u672c\u6708\u5e95\u5b8c\u6210\u65b9\u6848\u3002"},
            {"id": 5, "start_ms": 62000, "end_ms": 85000,  "text": "\u5218\u6d0b\uff1a\u641c\u7d22\u6a21\u5757\u54cd\u5e94\u65f6\u95f42.3\u79d2\uff0c\u76ee\u6807\u4f18\u5316\u81f3800ms\u4ee5\u5185\uff0c\u7ea6\u4e24\u5468\u5de5\u4f5c\u91cf\u3002"},
            {"id": 6, "start_ms": 85000, "end_ms": 100000, "text": "\u51b3\u8bae\uff1a\u4e09\u9879\u884c\u52a8\u9879\u5df2\u660e\u786e\uff0c\u5404\u8d1f\u8d23\u4eba\u987b\u5728\u89c4\u5b9a\u65f6\u95f4\u5185\u5b8c\u6210\u5e76\u6c47\u62a5\u8fdb\u5c55\u3002"},
        ],
        "summary": "\u672c\u6b21Q1\u89c4\u5212\u4f1a\u8bae\u56f4\u7ed5\u7528\u6237\u589e\u957f\u5c55\u5f00\u3002DAU\u8fbe50\u4e07\u4f46\u7b2c7\u5929\u7559\u5b5850%\u4e3b\u56e0\u4e3a\u5f15\u5bfc\u6d41\u7a0b\u590d\u6742\u53ca\u901a\u77e5\u8fc7\u5ea6\u3002\u4f1a\u8bae\u786e\u5b9a\u4e09\u9879\u6539\u8fdb\u63aa\u65bd\u3002",
        "decisions": ["\u7b80\u5316\u65b0\u7528\u6237\u5f15\u5bfc\u6d41\u7a0b\uff0c\u76ee\u6807\u63d0\u5347\u7b2c7\u5929\u7559\u5b58\u81f350%", "\u68b3\u7406\u4f18\u5316App\u5185\u901a\u77e5\u63a8\u9001\u7b56\u7565", "\u641c\u7d22\u6a21\u5757\u54cd\u5e94\u65f6\u95f4\u4f18\u5316\u81f3800ms\u4ee5\u5185"],
        "action_items": [
            {"id": 1, "owner_id": "3", "owner_name": "\u738b\u82b3", "content": "\u91cd\u65b0\u8bbe\u8ba1App\u901a\u77e5\u63a8\u9001\u7b56\u7565\uff0c\u65e5\u5747\u901a\u77e5\u63a7\u5236\u57283\u6761\u4ee5\u5185", "due_date": "2026-03-31", "status": "pending"},
            {"id": 2, "owner_id": "4", "owner_name": "\u5218\u6d0b", "content": "\u5b8c\u6210\u641c\u7d22\u6a21\u5757\u67b6\u6784\u91cd\u6784\uff0cP50\u54cd\u5e94\u65f6\u95f4\u4f18\u5316\u81f3800ms", "due_date": "2026-03-20", "status": "pending"},
            {"id": 3, "owner_id": "2", "owner_name": "\u674e\u5a1c", "content": "\u91cd\u65b0\u8bbe\u8ba1\u65b0\u7528\u6237\u6ce8\u518c\u5f15\u5bfc\u6d41\u7a0b\uff0c\u5b8c\u6210A/B\u6d4b\u8bd5\u65b9\u6848", "due_date": "2026-03-15", "status": "pending"},
            {"id": 4, "owner_id": "1", "owner_name": "\u5f20\u4f1f", "content": "\u8f93\u51fa\u7b2c7\u5929\u7559\u5b58\u7387\u4f18\u5316\u4e13\u9879\u62a5\u544a", "due_date": "2026-03-10", "status": "pending"},
        ],
    },
    "2": {"id": "2", "name": "\u6280\u672f\u67b6\u6784\u8bc4\u5ba1\u4f1a", "date": "2026-02-28", "duration_sec": 5400, "task_count": 8, "status": "dispatched", "audio_url": None, "transcript": [], "summary": "\u8bc4\u5ba1\u4e86\u5fae\u670d\u52a1\u62c6\u5206\u65b9\u6848\u548c\u6570\u636e\u5e93\u5206\u5e93\u5206\u8868\u7b56\u7565\u3002", "decisions": [], "action_items": []},
    "3": {"id": "3", "name": "\u5ba2\u6237\u9700\u6c42\u5bf9\u63a5\u4f1a", "date": "2026-02-27", "duration_sec": 2700, "task_count": 3, "status": "processing", "audio_url": None, "transcript": [], "summary": "AI\u5904\u7406\u4e2d...", "decisions": [], "action_items": []},
    "4": {"id": "4", "name": "\u5168\u5458\u6668\u4f1a - \u72b6\u6001\u540c\u6b65", "date": "2026-02-26", "duration_sec": 1200, "task_count": 2, "status": "dispatched", "audio_url": None, "transcript": [], "summary": "\u5404\u7ec4\u72b6\u6001\u540c\u6b65\u5b8c\u6210\u3002", "decisions": [], "action_items": []},
    "5": {"id": "5", "name": "\u98ce\u9669\u8bc4\u4f30\u4e0e\u5408\u89c4\u8ba8\u8bba", "date": "2026-02-25", "duration_sec": 4200, "task_count": 6, "status": "ready_for_review", "audio_url": None, "transcript": [], "summary": "\u5b8c\u6210\u4e09\u5b63\u5ea6\u5408\u89c4\u98ce\u9669\u8bc4\u4f30\u3002", "decisions": [], "action_items": []},
}

class ConfirmPayload(BaseModel):
    summary: Optional[str] = None
    action_items: Optional[List[dict]] = None

@router.get("")
async def list_meetings(page: int = 1, size: int = 10):
    items = list(MEETINGS.values())
    return {"items": items[(page-1)*size:page*size], "total": len(items), "page": page}

@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    m = MEETINGS.get(meeting_id)
    if not m: raise HTTPException(404, "\u4f1a\u8bae\u4e0d\u5b58\u5728")
    return m

@router.post("/{meeting_id}/confirm")
async def confirm_meeting(meeting_id: str, payload: ConfirmPayload):
    m = MEETINGS.get(meeting_id)
    if not m: raise HTTPException(404, "\u4f1a\u8bae\u4e0d\u5b58\u5728")
    if payload.summary: m["summary"] = payload.summary
    if payload.action_items is not None: m["action_items"] = payload.action_items
    return {"ok": True}

@router.post("/{meeting_id}/dispatch")
async def dispatch_meeting(meeting_id: str):
    m = MEETINGS.get(meeting_id)
    if not m: raise HTTPException(404, "\u4f1a\u8bae\u4e0d\u5b58\u5728")
    m["status"] = "dispatched"
    return {"ok": True, "dispatched_count": len(m.get("action_items", []))}
""")

# contacts.py
w("app/routers/contacts.py", """
from fastapi import APIRouter
router = APIRouter()
CONTACTS = [
    {"id": "1", "name": "\u5f20\u4f1f", "email": "zhang.wei@company.com"},
    {"id": "2", "name": "\u674e\u5a1c", "email": "li.na@company.com"},
    {"id": "3", "name": "\u738b\u82b3", "email": "wang.fang@company.com"},
    {"id": "4", "name": "\u5218\u6d0b", "email": "liu.yang@company.com"},
    {"id": "5", "name": "\u9648\u9759", "email": "chen.jing@company.com"},
]

@router.get("")
async def list_contacts():
    return CONTACTS
""")

# upload.py
w("app/routers/upload.py", """
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import uuid, os, asyncio, aiofiles

router = APIRouter()
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
tasks: dict = {}

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
):
    task_id = str(uuid.uuid4())
    meeting_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"status": "uploading", "meeting_id": meeting_id, "progress": 10}
    if file:
        path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
        async with aiofiles.open(path, "wb") as f2:
            await f2.write(await file.read())
        tasks[task_id]["status"] = "processing"
        background_tasks.add_task(simulate_processing, task_id, meeting_id, name or file.filename)
    elif url:
        background_tasks.add_task(simulate_processing, task_id, meeting_id, name or "online")
    return {"task_id": task_id, "meeting_id": meeting_id}

async def simulate_processing(task_id: str, meeting_id: str, name: str):
    await asyncio.sleep(5)
    tasks[task_id] = {"status": "ready_for_review", "meeting_id": meeting_id, "progress": 100}
""")

# tasks.py
w("app/routers/tasks.py", """
from fastapi import APIRouter
from app.routers.upload import tasks
router = APIRouter()

@router.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found", "progress": 0})
""")

# dispatch.py stub
w("app/routers/dispatch.py", """
from fastapi import APIRouter
router = APIRouter()
""")

print("All routers written OK")