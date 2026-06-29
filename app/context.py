"""Process-local context propagated via Python contextvars.

request_id_var carries the correlation ID from HTTP middleware → route handlers
→ enqueued RQ jobs → worker log lines, giving end-to-end traceability without
any shared state.
"""
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
