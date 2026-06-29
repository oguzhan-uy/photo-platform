"""ASGI middleware stack for the photo-delivery API.

Two responsibilities, each in its own class:

CorrelationIDMiddleware
  - Reads or generates an X-Request-ID for every request.
  - Stores it in request_id_var so route handlers and log lines pick it up
    automatically, with no explicit passing.
  - Echoes it back in the response header so callers can correlate their own
    logs against the server-side logs.

MetricsMiddleware
  - Records per-request latency and status-code counters in Prometheus.
  - Uses the FastAPI route *template* (e.g. /me/photos/{photo_id}) rather than
    the concrete path, so metric cardinality stays bounded regardless of how
    many UUIDs flow through the system.
  - Skips the /metrics endpoint itself to avoid recording meta-telemetry.
"""
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.context import request_id_var
from app.metrics import http_request_duration_seconds, http_requests_total


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Use the route template so /photos/uuid-a and /photos/uuid-b share a label.
        route = request.scope.get("route")
        path = route.path if route else request.url.path

        if path == "/metrics":
            return response

        http_requests_total.labels(request.method, path, response.status_code).inc()
        http_request_duration_seconds.labels(request.method, path).observe(duration)
        return response
