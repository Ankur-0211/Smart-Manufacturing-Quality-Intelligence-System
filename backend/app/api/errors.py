"""Stable error codes, the ``ApiError`` exception and FastAPI exception handlers.

Roadmap 9.3.4: codes are enumerated here and mirrored as a TypeScript union in the
frontend. Adding a code is a MINOR contract change, renaming/removing is MAJOR.
"""

from __future__ import annotations

import json
import time
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.contracts.errors import IntelligenceError
from app.core.logging import get_logger
from app.schemas.envelope import Envelope, ErrorBody, ErrorDetail, Meta

log = get_logger(__name__)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PARAM_OUT_OF_RANGE = "PARAM_OUT_OF_RANGE"
    COUPLING_VIOLATION = "COUPLING_VIOLATION"
    UNKNOWN_PARAMETER = "UNKNOWN_PARAMETER"
    PARAMETER_NOT_ACTIONABLE = "PARAMETER_NOT_ACTIONABLE"
    REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    PREDICTION_NOT_FOUND = "PREDICTION_NOT_FOUND"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    RUN_IMMUTABLE = "RUN_IMMUTABLE"
    STAGE_RESULTS_INCOMPLETE = "STAGE_RESULTS_INCOMPLETE"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    MODEL_ARTIFACT_INVALID = "MODEL_ARTIFACT_INVALID"
    FEATURE_SCHEMA_MISMATCH = "FEATURE_SCHEMA_MISMATCH"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    UPSTREAM_CONTEXT_MISSING = "UPSTREAM_CONTEXT_MISSING"
    INVALID_INTELLIGENCE_INPUT = "INVALID_INTELLIGENCE_INPUT"
    REGISTRY_INVALID = "REGISTRY_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHORIZED = "UNAUTHORIZED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Proposed in CCR-001 (additive): transport-level errors for unmatched routes/methods.
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"


DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.PARAM_OUT_OF_RANGE: 422,
    ErrorCode.COUPLING_VIOLATION: 422,
    ErrorCode.UNKNOWN_PARAMETER: 422,
    ErrorCode.PARAMETER_NOT_ACTIONABLE: 422,
    ErrorCode.INVALID_INTELLIGENCE_INPUT: 422,
    ErrorCode.REFERENCE_NOT_FOUND: 404,
    ErrorCode.RUN_NOT_FOUND: 404,
    ErrorCode.PREDICTION_NOT_FOUND: 404,
    ErrorCode.ROUTE_NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.INVALID_STATE_TRANSITION: 409,
    ErrorCode.RUN_IMMUTABLE: 409,
    ErrorCode.STAGE_RESULTS_INCOMPLETE: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.CAPABILITY_UNAVAILABLE: 501,
    ErrorCode.MODEL_NOT_LOADED: 503,
    ErrorCode.MODEL_ARTIFACT_INVALID: 503,
    ErrorCode.REGISTRY_INVALID: 503,
    ErrorCode.FEATURE_SCHEMA_MISMATCH: 500,
    ErrorCode.UPSTREAM_CONTEXT_MISSING: 500,
    ErrorCode.INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    """Raised by routers and services; rendered as the error envelope."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int | None = None,
        field: str | None = None,
        details: list[ErrorDetail] | None = None,
        constraint_version: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code or DEFAULT_STATUS[code]
        self.field = field
        self.details = details
        self.constraint_version = constraint_version
        self.hint = hint

    def to_body(self) -> ErrorBody:
        return ErrorBody(
            code=self.code.value,
            message=self.message,
            field=self.field,
            details=self.details,
            constraint_version=self.constraint_version,
            hint=self.hint,
        )


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def build_meta(request: Request, *, total: int | None = None) -> Meta:
    request_id = getattr(request.state, "request_id", None) or "unknown"
    started = getattr(request.state, "started_at", None)
    latency = round((time.perf_counter() - started) * 1000, 3) if started is not None else None
    return Meta(request_id=request_id, latency_ms=latency, total=total)


def error_response(request: Request, status_code: int, body: ErrorBody) -> JSONResponse:
    envelope: Envelope[None] = Envelope(data=None, error=body, meta=build_meta(request))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(envelope))


# ---------------------------------------------------------------------------
# Pydantic 422 -> envelope mapping (roadmap 9.3.3 tier 1)
# ---------------------------------------------------------------------------

_RANGE_TYPES = {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return None
    return value


def _detail_from_pydantic(err: dict[str, Any]) -> ErrorDetail:
    loc = [str(part) for part in err.get("loc", ()) if part not in ("body", "query", "path")]
    field = ".".join(loc) or None
    err_type = str(err.get("type", ""))
    ctx = err.get("ctx") or {}
    if err_type in _RANGE_TYPES:
        limit = next((ctx[k] for k in ("ge", "gt", "le", "lt") if k in ctx), None)
        code = ErrorCode.PARAM_OUT_OF_RANGE
    elif err_type == "extra_forbidden":
        limit = None
        code = ErrorCode.UNKNOWN_PARAMETER
    else:
        limit = None
        code = ErrorCode.VALIDATION_ERROR
    return ErrorDetail(
        field=field,
        code=code.value,
        message=str(err.get("msg", "invalid value")),
        limit=_json_safe(limit),
        value=_json_safe(err.get("input")),
    )


def validation_error_to_api_error(errors: list[dict[str, Any]]) -> ApiError:
    details = [_detail_from_pydantic(e) for e in errors]
    codes = {d.code for d in details}
    if codes == {ErrorCode.PARAM_OUT_OF_RANGE.value}:
        top = ErrorCode.PARAM_OUT_OF_RANGE
    elif codes == {ErrorCode.UNKNOWN_PARAMETER.value}:
        top = ErrorCode.UNKNOWN_PARAMETER
    else:
        top = ErrorCode.VALIDATION_ERROR
    first = details[0] if details else None
    message = (
        f"{len(details)} invalid field(s)"
        if len(details) != 1 or first is None
        else f"{first.field or 'request'}: {first.message}"
    )
    return ApiError(top, message, field=first.field if first else None, details=details)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    if exc.status_code >= 500:
        log.error("api_error", code=exc.code.value, message=exc.message)
    return error_response(request, exc.status_code, exc.to_body())


async def _handle_intelligence_error(request: Request, exc: Exception) -> JSONResponse:
    """Role 1 failures (roadmap 9.1 error table) -> envelope with the same stable code."""
    assert isinstance(exc, IntelligenceError)
    try:
        code = ErrorCode(exc.code)
    except ValueError:
        code = ErrorCode.INTERNAL_ERROR
    api_error = ApiError(code, exc.message, field=exc.field, hint=exc.hint)
    return await _handle_api_error(request, api_error)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    api_error = validation_error_to_api_error(list(exc.errors()))
    return error_response(request, api_error.status_code, api_error.to_body())


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        code, message = ErrorCode.ROUTE_NOT_FOUND, f"No route for {request.url.path}"
    elif exc.status_code == 405:
        code = ErrorCode.METHOD_NOT_ALLOWED
        message = f"Method {request.method} not allowed on {request.url.path}"
    elif exc.status_code == 401:
        code, message = ErrorCode.UNAUTHORIZED, str(exc.detail)
    elif exc.status_code == 413:
        code, message = ErrorCode.PAYLOAD_TOO_LARGE, str(exc.detail)
    elif exc.status_code == 429:
        code, message = ErrorCode.RATE_LIMITED, str(exc.detail)
    elif 400 <= exc.status_code < 500:
        code, message = ErrorCode.VALIDATION_ERROR, str(exc.detail)
    else:
        code, message = ErrorCode.INTERNAL_ERROR, "Internal server error"
    body = ErrorBody(code=code.value, message=message)
    return error_response(request, exc.status_code, body)


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces to the client; the log line carries request_id.
    log.exception("unhandled_exception", exc_type=type(exc).__name__)
    body = ErrorBody(
        code=ErrorCode.INTERNAL_ERROR.value,
        message="Internal server error",
        hint="Quote the request_id when reporting this problem.",
    )
    return error_response(request, 500, body)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(IntelligenceError, _handle_intelligence_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
