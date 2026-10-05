"""Brief API: the JSON and streaming surface behind the shared front end.

Run: uvicorn server:app --host 127.0.0.1 --port 8501
"""

import logging
from datetime import datetime
from typing import Any, Callable, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import StreamingResponse

import db
import generate
import i18n
import pdf
from authdep import is_admin, require_email
from brief_service import BriefService
from brief_view import to_detail, to_summary
from briefparse import (
    clean_brief,
    clean_company_prefill,
    extract_company_header,
    extract_score,
)
from errors import GENERIC_ERROR, UserFacingError
from settings import Settings, load_settings
from streaming import Work, stream_job

logger = logging.getLogger(__name__)

VALIDATION_ERROR = "Check the company name and language, then try again."
NOT_FOUND = "Brief not found"
# no-transform and X-Accel-Buffering keep proxies from compressing or buffering
# the stream, either of which would deliver every event in one lump at the end.
STREAM_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def ok(data: Any) -> dict:
    return {"success": True, "data": data, "error": None}


def _failure(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": message},
    )


class GenerateRequest(BaseModel):
    company: str
    language: Literal["en", "es"] = "en"

    @field_validator("company")
    @classmethod
    def _clean_company(cls, value: str) -> str:
        # Same rule as the ?company= prefill: flatten control characters and
        # whitespace, refuse anything over the radar's account-name cap.
        name = clean_company_prefill(value)
        if not name:
            raise ValueError("company is empty or too long")
        return name


class RefreshRequest(BaseModel):
    language: Literal["en", "es"] | None = None


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _failure(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _failure(422, VALIDATION_ERROR)

    @app.exception_handler(UserFacingError)
    async def _user_error(_request: Request, exc: UserFacingError) -> JSONResponse:
        return _failure(exc.status_code, str(exc))

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return _failure(500, GENERIC_ERROR)


def _install_brief_routes(app: FastAPI, repo: Any, settings: Settings) -> None:
    @app.get("/api/brief/health")
    def health() -> dict:
        return ok({"status": "ok"})

    @app.get("/api/brief/me")
    def me(email: str = Depends(require_email)) -> dict:
        return ok({"email": email, "isAdmin": is_admin(email, settings.admins_file)})

    @app.get("/api/brief/briefs")
    def list_briefs(email: str = Depends(require_email)) -> dict:
        return ok([to_summary(row) for row in repo.get_user_briefs(email)])

    @app.get("/api/brief/briefs/{brief_id}")
    def get_brief(brief_id: UUID, email: str = Depends(require_email)) -> dict:
        row = repo.get_brief(str(brief_id), email)
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return ok(to_detail(row))

    @app.delete("/api/brief/briefs/{brief_id}")
    def delete_brief(brief_id: UUID, email: str = Depends(require_email)) -> dict:
        if not repo.delete_brief(str(brief_id), email):
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return ok({"deleted": True})


def _install_pdf_route(app: FastAPI, repo: Any) -> None:
    @app.get("/api/brief/briefs/{brief_id}/pdf")
    def brief_pdf(brief_id: UUID, email: str = Depends(require_email)) -> Response:
        row = repo.get_brief(str(brief_id), email)
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        brief_md = clean_brief(row.get("brief_md") or "")
        score, _ = extract_score(brief_md)
        header_company, _ = extract_company_header(brief_md)
        company = header_company or row.get("company") or "Brief"
        language = i18n.detect_language(brief_md)
        now = datetime.now()
        content = pdf.generate_brief_pdf(brief_md, company, score, now, language)
        filename = pdf.build_filename(company, now.strftime("%Y-%m"), language)
        return Response(
            content=bytes(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )


def _install_generation_routes(
    app: FastAPI, service: BriefService, heartbeat_seconds: float
) -> None:
    def _stream(work: Work) -> StreamingResponse:
        return StreamingResponse(
            stream_job(work, heartbeat_seconds),
            media_type="text/event-stream",
            headers=STREAM_HEADERS,
        )

    @app.post("/api/brief/briefs")
    async def generate_route(
        body: GenerateRequest, email: str = Depends(require_email)
    ) -> StreamingResponse:
        work = await run_in_threadpool(
            service.start_generate, email, body.company, body.language
        )
        return _stream(work)

    @app.post("/api/brief/briefs/{brief_id}/refresh")
    async def refresh_route(
        brief_id: UUID, body: RefreshRequest, email: str = Depends(require_email)
    ) -> StreamingResponse:
        work = await run_in_threadpool(
            service.start_refresh, email, str(brief_id), body.language
        )
        return _stream(work)


def create_app(
    repo: Any = db,
    generator: Callable[..., str] = generate.generate_brief,
    settings: Settings | None = None,
    heartbeat_seconds: float = 15.0,
) -> FastAPI:
    settings = settings or load_settings()
    if not settings.anthropic_key or not settings.tavily_key:
        logger.warning("ANTHROPIC_API_KEY or TAVILY_API_KEY missing: generation is disabled.")

    app = FastAPI(title="Alkira Brief API", docs_url=None, redoc_url=None, openapi_url=None)
    service = BriefService(repo, generator, settings)
    app.state.service = service

    _install_error_handlers(app)
    _install_brief_routes(app, repo, settings)
    _install_pdf_route(app, repo)
    _install_generation_routes(app, service, heartbeat_seconds)
    return app


app = create_app()
