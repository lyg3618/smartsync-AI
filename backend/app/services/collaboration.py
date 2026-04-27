import json
from xml.sax.saxutils import escape

import httpx


SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SOAP_SERVICE_NS = "http://localhost/services/ServiceMessageCustom"


def build_message_body(
    *,
    title: str,
    meeting_name: str,
    summary: str,
    decisions: list[str],
    tasks: list[str],
) -> str:
    decision_lines = "\n".join([f"- {item}" for item in decisions if str(item).strip()]) or "- 无"
    task_lines = "\n".join([f"- {item}" for item in tasks if str(item).strip()]) or "- 无"
    summary_text = (summary or "").strip() or "无"
    return (
        f"{title}\n"
        f"会议：{meeting_name}\n\n"
        f"待办任务：\n{task_lines}\n\n"
        f"会议摘要：\n{summary_text}\n\n"
        f"核心决议：\n{decision_lines}"
    )


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
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV_NS}" xmlns:ser="{SOAP_SERVICE_NS}">'
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
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        response.raise_for_status()
        text = response.text

    lowered = text.lower()
    if "status" not in lowered or "true" not in lowered:
        raise RuntimeError(f"协同消息接口返回异常: {text[:300]}")
    return text


async def delete_collaboration_message(
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
    delete_biz_state: str = "27",
) -> str:
    return await send_collaboration_message(
        api_url=api_url,
        code=code,
        creator=creator,
        title=title,
        context=context,
        login_id_list=login_id_list,
        target_id=target_id,
        link_url=link_url,
        link_mobile_url=link_mobile_url,
        biz_state=delete_biz_state,
    )
