import json
import logging
from datetime import datetime
from xml.sax.saxutils import escape

import httpx


SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_SEND_SERVICE_NS = "http://localhost/services/ServiceMessageCustom"
SOAP_ALTER_SERVICE_NS = "http://webservice.message.ecology.weaver.com"
logger = logging.getLogger(__name__)


def _log_prefix() -> str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def build_message_body(
    *,
    title: str,
    meeting_name: str,
    summary: str,
    decisions: list[str],
    tasks: list[str],
) -> str:
    clean_tasks = [str(item).strip() for item in tasks if str(item).strip()]
    clean_decisions = [str(item).strip() for item in decisions if str(item).strip()]
    summary_text = (summary or "").strip()

    lines = [title, f"会议：{meeting_name}"]
    if clean_tasks:
        lines.append(f"事项：{clean_tasks[0]}")
        if len(clean_tasks) > 1:
            lines.append(f"其余 {len(clean_tasks) - 1} 项请查看系统")
    else:
        lines.append("事项：待补充")

    if summary_text:
        lines.append(f"摘要：{summary_text}")
    if clean_decisions:
        lines.append(f"决议：{clean_decisions[0]}")

    return "\n".join(lines)


def build_task_deadline_text(content: str, due_date: str | None) -> str:
    return f"{content} (截止: {due_date or '待定'})"


async def send_collaboration_message(
    *,
    api_url: str,
    code: str,
    creator: str,
    title: str,
    context: str,
    login_id_list: list[str],
    target_id: str,
    link_url: str = "",
    link_mobile_url: str = "",
    biz_state: str = "0",
) -> str:
    payload = {
        "code": str(code).strip(),
        "title": str(title).strip(),
        "context": str(context).strip(),
        "linkUrl": str(link_url or "").strip(),
        "linkMobileUrl": str(link_mobile_url or "").strip(),
        "loginIdList": [str(item).strip() for item in login_id_list if str(item).strip()],
        "creater": str(creator).strip(),
        "bizState": str(biz_state).strip() or "0",
        "targetId": str(target_id).strip(),
    }

    if not payload["loginIdList"]:
        raise ValueError("缺少协同接收人")
    if not payload["code"]:
        raise ValueError("缺少协同消息来源编码")
    if not payload["creater"]:
        raise ValueError("缺少协同消息创建人")
    if not payload["targetId"]:
        raise ValueError("缺少协同消息 targetId")

    payload_json = escape(json.dumps(payload, ensure_ascii=False))
    soap_payload = (
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:ser="{SOAP_SEND_SERVICE_NS}">'
        "<soapenv:Header />"
        "<soapenv:Body>"
        "<ser:sendCustomMessageSingle>"
        f"<ser:in0>{payload_json}</ser:in0>"
        "</ser:sendCustomMessageSingle>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.post(
            api_url,
            content=soap_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml;charset=utf-8"},
        )
        response.raise_for_status()
        text = response.text

    lowered = text.lower()
    if "status" not in lowered or "true" not in lowered:
        raise RuntimeError(f"协同消息接口返回异常: {text[:300]}")
    return text


async def alter_collaboration_message_status(
    *,
    api_url: str,
    code: str,
    target_id: str,
    login_id_list: list[str],
    biz_state: str = "1",
) -> str:
    payload = {
        "targetId": str(target_id).strip(),
        "bizState": str(biz_state).strip() or "1",
        "loginIdList": [str(item).strip() for item in login_id_list if str(item).strip()],
        "code": str(code).strip(),
    }

    if not payload["loginIdList"]:
        raise ValueError("缺少协同接收人")
    if not payload["targetId"]:
        raise ValueError("缺少协同消息 targetId")
    if not payload["code"]:
        raise ValueError("缺少协同消息来源编码")

    payload_json = escape(json.dumps(payload, ensure_ascii=False))
    soap_payload = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:web="{SOAP_ALTER_SERVICE_NS}">'
        "<soapenv:Header/>"
        "<soapenv:Body>"
        "<web:alterCustomMessageSingle>"
        f"<in0>{payload_json}</in0>"
        "</web:alterCustomMessageSingle>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )

    print(
        f"{_log_prefix()} alterCustomMessageSingle request "
        f"targetId={payload['targetId']} "
        f"bizState={payload['bizState']} "
        f"loginIdList={payload['loginIdList']} "
        f"code={payload['code']}",
        flush=True,
    )

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.post(
            api_url,
            content=soap_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml;charset=utf-8"},
        )
        response.raise_for_status()
        text = response.text

    print(f"{_log_prefix()} alterCustomMessageSingle response: {text}", flush=True)

    lowered = text.lower()
    if "<ns1:out>true</ns1:out>" not in lowered and ">true<" not in lowered:
        raise RuntimeError(f"协同消息修改接口返回异常: {text[:300]}")
    return text


async def refresh_collaboration_message_list(
    *,
    api_url: str,
    login_id_list: list[str],
) -> str:
    payload = {
        "loginIdList": [str(item).strip() for item in login_id_list if str(item).strip()],
    }

    if not payload["loginIdList"]:
        raise ValueError("缺少协同接收人")

    payload_json = escape(json.dumps(payload, ensure_ascii=False))
    soap_payload = (
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:ser="{SOAP_SEND_SERVICE_NS}">'
        "<soapenv:Header />"
        "<soapenv:Body>"
        "<ser:deleteCustomMessageSingle>"
        f"<ser:in0>{payload_json}</ser:in0>"
        "</ser:deleteCustomMessageSingle>"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )

    print(
        f"{_log_prefix()} refreshCollaborationMessageList request "
        f"soapAction=deleteCustomMessageSingle "
        f"loginIdList={payload['loginIdList']}",
        flush=True,
    )

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.post(
            api_url,
            content=soap_payload.encode("utf-8"),
            headers={"Content-Type": "text/xml;charset=utf-8"},
        )
        response.raise_for_status()
        text = response.text

    print(
        f"{_log_prefix()} refreshCollaborationMessageList response "
        f"soapAction=deleteCustomMessageSingle body={text}",
        flush=True,
    )

    lowered = text.lower()
    if "<ns1:out>true</ns1:out>" not in lowered and ">true<" not in lowered:
        raise RuntimeError(f"协同消息刷新接口返回异常: {text[:300]}")
    return text
