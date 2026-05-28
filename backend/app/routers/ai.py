import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_pool
from app.routers.auth import get_current_user

router = APIRouter()


class TemplateMinutesPayload(BaseModel):
    meeting_id: str
    template_content: str


class AnalyzeMeetingPayload(BaseModel):
    meeting_id: str


class TestLlmPayload(BaseModel):
    model: str
    base_url: str
    api_key: str = ""


async def _fetch_active_llm_config(user_id: str) -> dict[str, str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT model, base_url, api_key
                FROM llm_connection_configs
                WHERE user_id=%s AND is_active=1
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            if row and row[0] and row[1]:
                return {"model": row[0], "base_url": row[1], "api_key": row[2] or ""}

            await cur.execute(
                """
                SELECT username
                FROM contacts
                WHERE role='admin' AND username IS NOT NULL AND username <> ''
                ORDER BY id ASC
                LIMIT 1
                """
            )
            admin_user_row = await cur.fetchone()
            if admin_user_row and admin_user_row[0]:
                await cur.execute(
                    """
                    SELECT model, base_url, api_key
                    FROM llm_connection_configs
                    WHERE user_id=%s AND is_active=1
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (admin_user_row[0],),
                )
                admin_row = await cur.fetchone()
                if admin_row and admin_row[0] and admin_row[1]:
                    return {"model": admin_row[0], "base_url": admin_row[1], "api_key": admin_row[2] or ""}

    if not settings.llm_base_url or not settings.llm_model:
        raise HTTPException(400, "未配置可用的大模型连接")

    return {
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "api_key": settings.llm_api_key or "",
    }


async def _fetch_meeting_context(meeting_id: str, user_id: str) -> dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, name, date, duration_sec, summary, decisions
                FROM meetings
                WHERE id=%s AND user_id=%s AND is_deleted=0
                LIMIT 1
                """,
                (meeting_id, user_id),
            )
            meeting_row = await cur.fetchone()
            if not meeting_row:
                raise HTTPException(404, "会议不存在")

            await cur.execute(
                "SELECT start_ms, end_ms, text FROM transcripts WHERE meeting_id=%s ORDER BY start_ms",
                (meeting_id,),
            )
            transcript_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT owner_name, content, due_date, status
                FROM action_items
                WHERE meeting_id=%s
                ORDER BY id
                """,
                (meeting_id,),
            )
            action_rows = await cur.fetchall()

    decisions = []
    if meeting_row[5]:
        try:
            decisions = json.loads(meeting_row[5])
        except Exception:
            decisions = []

    return {
        "id": meeting_row[0],
        "name": meeting_row[1],
        "date": str(meeting_row[2] or ""),
        "duration_sec": int(meeting_row[3] or 0),
        "summary": meeting_row[4] or "",
        "decisions": decisions,
        "transcript": [
            {"start_ms": row[0], "end_ms": row[1], "text": row[2] or ""}
            for row in transcript_rows
        ],
        "action_items": [
            {
                "owner_name": row[0] or "",
                "content": row[1] or "",
                "due_date": str(row[2] or ""),
                "status": row[3] or "pending",
            }
            for row in action_rows
        ],
    }


def _format_duration(sec: int) -> str:
    if not sec:
        return "--"
    hour = sec // 3600
    minute = (sec % 3600) // 60
    if hour > 0:
        return f"{hour}小时 {minute}分钟"
    return f"{minute} 分钟"


def _preview_text(value: str, limit: int = 1000) -> str:
    text = (value or "").strip()
    if not text:
        return "空内容"
    if len(text) <= limit:
        return text
    return text[:limit] + f"...（已截断，原始长度 {len(text)} 字符）"


def _json_error_context(value: str, error: json.JSONDecodeError, radius: int = 120) -> str:
    start = max(error.pos - radius, 0)
    end = min(error.pos + radius, len(value))
    snippet = value[start:end]
    pointer = " " * max(error.pos - start, 0) + "^"
    return f"位置 {error.pos} 附近内容：\n{snippet}\n{pointer}"


def _extract_first_json_object(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return text

    start = text.find("{")
    if start < 0:
        return text

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return text


async def _chat_completion(
    user_id: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
) -> str:
    llm_config = await _fetch_active_llm_config(user_id)
    headers = {"Content-Type": "application/json"}
    if llm_config["api_key"]:
        headers["Authorization"] = f"Bearer {llm_config['api_key']}"

    url = f"{llm_config['base_url'].rstrip('/')}/chat/completions"
    request_payload: dict[str, Any] = {
        "model": llm_config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if response_format:
        request_payload["response_format"] = response_format

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                json=request_payload,
                headers=headers,
            )
    except httpx.RequestError as exc:
        raise HTTPException(502, f"模型服务连接失败：{exc}") from exc

    if response.status_code >= 400:
        detail = (response.text or "").strip()
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or payload.get("message") or detail
        except Exception:
            pass
        if not detail:
            detail = f"上游模型服务返回 HTTP {response.status_code}，但响应体为空。URL={url}, model={llm_config['model']}"
        raise HTTPException(response.status_code, f"模型调用失败：{detail}")

    try:
        payload = response.json()
    except Exception as exc:
        text_preview = (response.text or "").strip()
        if len(text_preview) > 300:
            text_preview = text_preview[:300] + "..."
        raise HTTPException(502, f"模型返回了非 JSON 响应：{text_preview or '空响应体'}") from exc

    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not content:
        raise HTTPException(502, "模型未返回有效内容")
    return content


@router.post("/template-minutes")
async def generate_template_minutes(payload: TemplateMinutesPayload, current_user: dict = Depends(get_current_user)):
    if not payload.template_content.strip():
        raise HTTPException(400, "模板内容不能为空")

    meeting = await _fetch_meeting_context(payload.meeting_id, current_user["sub"])
    transcript_text = "\n".join(item["text"] for item in meeting["transcript"]) or "暂无逐字稿"
    actions_text = (
        "\n".join(
            f"{index + 1}. {item['owner_name'] or '待分配'}：{item['content'] or '待补充'}；截止：{item['due_date'] or '待定'}"
            for index, item in enumerate(meeting["action_items"])
        )
        if meeting["action_items"]
        else "暂无行动项"
    )
    decisions_text = (
        "\n".join(f"{index + 1}. {item}" for index, item in enumerate(meeting["decisions"]))
        if meeting["decisions"]
        else "暂无决议"
    )

    prompt = (
        "你是一名企业会议纪要助手。请严格按照用户提供的模板结构输出正式会议纪要。\n"
        "要求：\n"
        "1. 保留模板中的标题、层级、段落顺序与风格。\n"
        "2. 根据会议内容填充，不确定的信息写“待补充”。\n"
        "3. 不要解释过程，不要输出模板说明，只输出最终纪要正文。\n"
        "4. 输出语言为中文。\n\n"
        f"【用户模板】\n{payload.template_content}\n\n"
        f"【会议基础信息】\n会议名称：{meeting['name']}\n会议日期：{meeting['date']}\n会议时长：{_format_duration(meeting['duration_sec'])}\n\n"
        f"【会议摘要】\n{meeting['summary'] or '待补充'}\n\n"
        f"【核心决议】\n{decisions_text}\n\n"
        f"【行动项】\n{actions_text}\n\n"
        f"【会议逐字稿】\n{transcript_text}"
    )

    content = await _chat_completion(current_user["sub"], prompt, temperature=0.2)
    return {"content": content}


@router.post("/analyze-meeting")
async def analyze_meeting(payload: AnalyzeMeetingPayload, current_user: dict = Depends(get_current_user)):
    meeting = await _fetch_meeting_context(payload.meeting_id, current_user["sub"])
    transcript_text = "\n".join(item["text"] for item in meeting["transcript"]) or "暂无逐字稿"
    prompt = (
        "你是一名会议分析助手，请从逐字稿中提取会议摘要、核心决议和可执行行动项。\n"
        "输出必须是严格 JSON，不要添加代码块。字段格式如下："
        '{"summary":"会议摘要（100字以内）","decisions":["决议1","决议2"],"action_items":[{"owner_name":"负责人姓名","content":"具体可执行任务","due_date":"YYYY-MM-DD","priority":"high/medium/low"}]}'
        "如果负责人或日期不确定，可填写“待确认”和空字符串。\n"
        "禁止输出思考过程、分析步骤、说明文字、Markdown 标记或代码块，响应必须以 { 开始并以 } 结束。\n\n"
        f"会议名称：{meeting['name']}\n会议日期：{meeting['date']}\n\n逐字稿：\n{transcript_text}"
    )
    content = await _chat_completion(
        current_user["sub"],
        prompt,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    normalized_content = _extract_first_json_object(content)
    try:
        data = json.loads(normalized_content)
    except json.JSONDecodeError as exc:
        detail = (
            f"模型返回内容不是有效 JSON：{exc.msg}；line={exc.lineno}, column={exc.colno}, pos={exc.pos}\n"
            f"{_json_error_context(normalized_content, exc)}\n"
            f"模型原始返回预览：\n{_preview_text(content)}"
        )
        raise HTTPException(502, detail) from exc

    return data


@router.post("/test-connection")
async def test_llm_connection(payload: TestLlmPayload, current_user: dict = Depends(get_current_user)):
    headers = {"Content-Type": "application/json"}
    if payload.api_key:
        headers["Authorization"] = f"Bearer {payload.api_key}"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{payload.base_url.rstrip('/')}/chat/completions",
            json={
                "model": payload.model,
                "messages": [{"role": "user", "content": "hello"}],
                "max_tokens": 5,
            },
            headers=headers,
        )

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("error", {}).get("message") or response.text
        except Exception:
            pass
        raise HTTPException(response.status_code, f"连接失败：{detail}")

    return {"ok": True}
