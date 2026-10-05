"""Brief API: the JSON and streaming surface behind the shared front end.

Run: uvicorn server:app --host 127.0.0.1 --port 8501
"""

import logging

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import db
import generate
from authdep import is_admin, require_email
from errors import GENERIC_ERROR, UserFacingError
from settings import Settings, load_settings

logger = logging.getLogger(__name__)

VALIDATION_ERROR = "Check the company name and language, then try again."


def ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


def _failure(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": message},
    )


def create_app(
    repo=db,
    generator=generate.generate_brief,
    settings: Settings | None = None,
    heartbeat_seconds: float = 15.0,
) -> FastAPI:
    settings = settings or load_settings()
    if not settings.anthropic_key or not settings.tavily_key:
        logger.warning("ANTHROPIC_API_KEY or TAVILY_API_KEY missing: generation is disabled.")

    app = FastAPI(title="Alkira Brief API", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request, exc):
        return _failure(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request, _exc):
        return _failure(422, VALIDATION_ERROR)

    @app.exception_handler(UserFacingError)
    async def _user_error(_request, exc):
        return _failure(exc.status_code, str(exc))

    @app.exception_handler(Exception)
    async def _unexpected(_request, exc):
        logger.exception("Unhandled error: %s", exc)
        return _failure(500, GENERIC_ERROR)

    @app.get("/api/brief/health")
    def health():
        return ok({"status": "ok"})

    @app.get("/api/brief/me")
    def me(email: str = Depends(require_email)):
        return ok({"email": email, "isAdmin": is_admin(email, settings.admins_file)})

    return app


app = create_app()
