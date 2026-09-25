"""ASGI spans record route templates, never URLs, queries, cookies or bodies."""

from opentelemetry.trace import Status, StatusCode
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from planner.observability.runtime import span, use


class TelemetryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        telemetry = scope["app"].state.telemetry
        method = scope.get("method", "OTHER")
        if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            method = "OTHER"
        sent = False
        status_class = "5xx"
        with use(telemetry), span("api.request", http_method=method) as current:
            trace_id = format(current.get_span_context().trace_id, "032x")
            scope.setdefault("state", {})["correlation_id"] = trace_id

            async def measured_send(message):
                nonlocal sent, status_class
                if message["type"] == "http.response.start":
                    sent = True
                    status_class = str(message["status"] // 100) + "xx"
                    current.set_attribute("http.status_code", message["status"])
                    if message["status"] >= 500:
                        current.set_status(Status(StatusCode.ERROR))
                    headers = list(message.get("headers", []))
                    existing = next(
                        (v for k, v in headers if k.lower() == b"x-correlation-id"), None
                    )
                    if existing:
                        current.set_attribute(
                            "operation.id", existing.decode("ascii", errors="ignore")[:64]
                        )
                    else:
                        headers.append((b"x-correlation-id", trace_id.encode()))
                    message = {**message, "headers": headers}
                await send(message)

            try:
                await self.app(scope, receive, measured_send)
            except Exception as error:
                current.set_attribute("error.type", type(error).__name__)
                current.set_status(Status(StatusCode.ERROR))
                if sent:
                    raise RuntimeError("STREAM_INTERRUPTED") from None
                unavailable = isinstance(error, SQLAlchemyError)
                response = JSONResponse(
                    {
                        "code": "DEPENDENCY_UNAVAILABLE" if unavailable else "INTERNAL_ERROR",
                        "message": "The service could not finish this request. Try again shortly.",
                        "field_ids": [],
                        "related_ids": [],
                        "retryable": unavailable,
                        "correlation_id": trace_id,
                    },
                    status_code=503 if unavailable else 500,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, measured_send)
            finally:
                route = getattr(scope.get("route"), "path", "unmatched")
                current.set_attribute("http.route", route)
                telemetry.measure(
                    "planner.api.requests", 1, route=route, method=method, status=status_class
                )
