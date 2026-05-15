"""FastAPI webhook for one-shot catalog audits.

Run:
    python -m uv run uvicorn webhook:app --host 0.0.0.0 --port 8000

POST /audit
    body: {"url": str, "question": str?, "draft": bool?}
    response: {"product_handle", "score", "gaps", "hitl_id"?, "draft"?}
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from healf_agent.models import Product
from healf_agent.tools import dispatch_tool as _dispatch

app = FastAPI(title="Healf Catalog Audit", version="0.1.0")


class AuditRequest(BaseModel):
    url: HttpUrl
    question: Optional[str] = None
    draft: bool = False


class AuditResponse(BaseModel):
    product_handle: str
    score: float
    gaps: list[str]
    hitl_id: Optional[int] = None
    draft: Optional[str] = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest) -> AuditResponse:
    url_str = str(req.url)
    from urllib.parse import urlparse as _urlparse
    _host = (_urlparse(url_str).hostname or "")
    if _host != "healf.com" and not _host.endswith(".healf.com"):
        raise HTTPException(status_code=400, detail="URL must be on healf.com")

    try:
        fetched = _dispatch(name="fetch_product", arguments={"url": url_str}, product=None)
        product = Product.model_validate(fetched)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch/parse product: {exc}") from exc

    try:
        eval_report = _dispatch(name="evaluate_listing_quality", arguments={}, product=product)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"evaluate_listing_quality failed: {exc}") from exc
    scores = eval_report.get("scores", [])
    avg = sum(s["score"] for s in scores) / len(scores) if scores else 0.0
    gaps = eval_report.get("gaps", [])

    draft_text: Optional[str] = None
    hitl_id: Optional[int] = None
    if req.draft and gaps:
        drafted = _dispatch(name="draft_rewrite", arguments={"gaps": gaps}, product=product)
        draft_text = drafted.get("drafted_description") or None
        if not draft_text:
            raise HTTPException(status_code=502, detail="draft_rewrite returned empty text")
        queued = _dispatch(
            name="enqueue_hitl",
            arguments={
                "drafted_description": draft_text or "",
                "gap_summary": "; ".join(gaps),
            },
            product=product,
        )
        hitl_id = queued.get("entry_id")

    return AuditResponse(
        product_handle=product.handle,
        score=avg,
        gaps=gaps,
        hitl_id=hitl_id,
        draft=draft_text,
    )
