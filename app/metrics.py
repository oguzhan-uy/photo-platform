"""Prometheus metric definitions.

All metrics are defined here so the rest of the codebase imports from one place
and tests can patch at this boundary. The global REGISTRY is the standard
prometheus_client registry; no custom registry is used so that the default
/metrics collector picks everything up automatically.
"""
from prometheus_client import Counter, Histogram
from prometheus_client.core import GaugeMetricFamily

# ---------------------------------------------------------------------------
# HTTP metrics (populated by MetricsMiddleware)
# ---------------------------------------------------------------------------

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method, path template, and status code",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# ---------------------------------------------------------------------------
# Ingest job metrics (populated by worker/jobs/ingest.py)
# ---------------------------------------------------------------------------

job_total = Counter(
    "photo_job_total",
    "Completed ingest jobs by outcome",
    ["job_type", "status"],
)

job_duration_seconds = Histogram(
    "photo_job_duration_seconds",
    "Wall-clock time for a complete ingest job",
    ["job_type"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600],
)

# ---------------------------------------------------------------------------
# R2 storage metrics (populated by app/storage.py)
# ---------------------------------------------------------------------------

r2_operations_total = Counter(
    "photo_r2_operations_total",
    "R2 API calls by operation name",
    ["operation"],
)

# ---------------------------------------------------------------------------
# Queue depth — custom collector so the value is fresh at every scrape
# ---------------------------------------------------------------------------


class _QueueDepthCollector:
    def collect(self):
        try:
            from app.redis_client import task_queue  # lazy: avoids startup Redis dep
            depth = float(len(task_queue))
        except Exception:
            depth = 0.0
        g = GaugeMetricFamily(
            "photo_queue_depth",
            "Number of jobs currently waiting in the RQ queue",
        )
        g.add_metric([], depth)
        yield g


def register_custom_collectors() -> None:
    """Call once at app startup to register collectors that need lazy imports."""
    from prometheus_client import REGISTRY
    REGISTRY.register(_QueueDepthCollector())
