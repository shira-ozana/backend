"""Gateway לסוכנים (Agents) שרצים כשרתים נפרדים.

הבקאנד לא מריץ את הסוכן בעצמו - הוא מעביר את הבקשה לשרת של הסוכן ומחזיר את התשובה.

    POST /api/agents/init/run              -> POST {INIT_AGENT_URL}/api/init         (runInit)
    POST /api/agents/init/run?wait=true    -> מחכה לסיום הריצה ומחזיר את התוצאה המלאה
    GET  /api/agents/init/runs/{run_id}         -> סטטוס והתקדמות
    GET  /api/agents/init/runs/{run_id}/report  -> דוח INIT.md

להוספת סוכן חדש: מוסיפים רשומה ב-_agents() (וכתובת ב-config/.env).
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, Response

from app.config import get_settings

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _agents() -> dict[str, str]:
    """שם סוכן -> כתובת ה-endpoint שמפעיל אותו בשרת של הסוכן"""
    s = get_settings()
    return {
        "init": f"{s.init_agent_url.rstrip('/')}/api/init",
    }


def _agent_url(agent: str) -> str:
    url = _agents().get(agent)
    if url is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent '{agent}'. Available: {', '.join(sorted(_agents()))}",
        )
    return url


async def _forward(method: str, url: str, *, json: Any = None, params: dict | None = None,
                   timeout: float | None = None) -> Response:
    """שולח את הבקשה לשרת הסוכן ומחזיר את התשובה שלו כמו שהיא (קוד + גוף)"""
    if timeout is None:
        timeout = get_settings().agent_request_timeout
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(method, url, json=json, params=params)
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=503, detail=f"Agent server is not reachable at {url}") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Agent server did not respond in time") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Agent request failed: {type(exc).__name__}") from exc

    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type", "application/json"),
    )


@router.get("")
def list_agents() -> dict[str, list[str]]:
    """רשימת הסוכנים שאפשר להפעיל"""
    return {"agents": sorted(_agents())}


@router.post("/{agent}/run", status_code=202)
async def run_agent(
    agent: str,
    body: dict[str, Any] | None = Body(
        default=None,
        description="גוף הבקשה שעובר לסוכן כמו שהוא. ל-INIT: InitRequest (כל השדות אופציונליים)",
        examples=[{
            "feature_id": "3f1c...",
            "project": {"repo_url": "https://github.com/org/repo"},
            "inputs": {"project_brief": "תיאור קצר של הפרויקט"},
            "dry_run": True,
        }],
    ),
    wait: bool = Query(False, description="true = לחכות לסיום הריצה ולקבל את התוצאה המלאה"),
) -> Response:
    """מפעיל סוכן (למשל runInit). ברירת מחדל: חוזר מיד עם runId"""
    url = _agent_url(agent)
    if wait:
        # ריצה מלאה יכולה לקחת כמה דקות - timeout ארוך יותר
        return await _forward("POST", url, json=body or {}, params={"wait": "true"},
                              timeout=get_settings().agent_wait_timeout)
    return await _forward("POST", url, json=body or {})


@router.get("/{agent}/runs/{run_id}")
async def get_run(agent: str, run_id: str) -> Response:
    """סטטוס של ריצה: running / succeeded / failed, התקדמות לפי שלב, והתוצאה בסוף"""
    return await _forward("GET", f"{_agent_url(agent)}/{run_id}")


@router.get("/{agent}/runs/{run_id}/report")
async def get_run_report(agent: str, run_id: str) -> Response:
    """הדוח שהסוכן כתב (ל-INIT: INIT.md כ-markdown)"""
    return await _forward("GET", f"{_agent_url(agent)}/{run_id}/report")
