"""Content generation router.

Endpoints:
  POST /api/content/generate        – generate FAQ / article / howto content
  POST /api/content/schema          – generate schema.org markup
  POST /api/content/decay           – detect content decay
  POST /api/content/aio-optimize    – enrich content for AIO/GEO
"""

from __future__ import annotations

import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/content", tags=["content"])


class GenerateRequest(BaseModel):
    content_type: Literal["faq", "article", "howto"] = "article"
    topic: str
    keywords: list[str] = []
    tone: str = "professional"
    word_count: int = 800
    locale: str = "en"
    stream: bool = False


class SchemaRequest(BaseModel):
    url: str
    content_type: Literal["article", "faq", "howto", "product", "local_business"] = "article"
    metadata: dict[str, Any] = {}


class ContentDecayRequest(BaseModel):
    url: str
    published_date: Optional[str] = None
    content: Optional[str] = None


class AIOEnrichRequest(BaseModel):
    content: str
    target_keywords: list[str] = []
    enhance_eeat: bool = True
    generate_llm_txt: bool = False


@router.post("/generate")
async def generate_content(request: GenerateRequest) -> dict[str, Any]:
    """Generate SEO-optimized content (FAQ / Article / HowTo)."""
    from ..skills import ContentGeneratorSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = ContentGeneratorSkill()
        inp = SkillInput(
            url="",
            params={
                "content_type": request.content_type,
                "topic": request.topic,
                "keywords": request.keywords,
                "tone": request.tone,
                "word_count": request.word_count,
                "locale": request.locale,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "content_type": request.content_type,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/schema")
async def generate_schema(request: SchemaRequest) -> dict[str, Any]:
    """Generate schema.org JSON-LD markup for a URL."""
    from ..skills import SchemaBuilderSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = SchemaBuilderSkill()
        inp = SkillInput(
            url=request.url,
            params={"content_type": request.content_type, **request.metadata},
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/decay")
async def detect_content_decay(request: ContentDecayRequest) -> dict[str, Any]:
    """Detect content decay and suggest refresh opportunities."""
    from ..skills import ContentDecayDetectorSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = ContentDecayDetectorSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "published_date": request.published_date,
                "content": request.content,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/aio-optimize")
async def aio_optimize_content(request: AIOEnrichRequest) -> dict[str, Any]:
    """Enrich existing content for AIO/GEO visibility."""
    from ..skills import EEATEnhancerSkill, LLMTxtGeneratorSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        results: dict[str, Any] = {}

        if request.enhance_eeat:
            skill = EEATEnhancerSkill()
            inp = SkillInput(url="", params={"content": request.content, "keywords": request.target_keywords})
            r = await skill.execute(inp)
            results["eeat"] = r.data if hasattr(r, "data") else r

        if request.generate_llm_txt:
            skill2 = LLMTxtGeneratorSkill()
            inp2 = SkillInput(url="", params={"content": request.content})
            r2 = await skill2.execute(inp2)
            results["llm_txt"] = r2.data if hasattr(r2, "data") else r2

        return {
            "status": "success",
            "elapsed_sec": round(time.time() - start, 2),
            "result": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
