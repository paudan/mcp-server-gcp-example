"""Tracing and audit records. Spans go to Cloud Trace on Cloud Run (K_SERVICE is
set there) and nowhere else; each audit record is one JSON line, which Cloud
Logging parses into a structured entry."""

from __future__ import annotations

import json
import logging
import os

from opentelemetry import trace

_audit_log = logging.getLogger("catalog_mcp.audit")
tracer = trace.get_tracer("catalog-mcp")


def setup_tracing() -> None:
    if not os.environ.get("K_SERVICE"):
        return
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(provider)


def audit(tool: str, principal: str, role: str, allowed: bool, duration_ms: float,
          error: str = "") -> None:
    record = {
        "severity": "INFO" if allowed and not error else "WARNING",
        "message": "tool_call" if allowed else "tool_call_denied",
        "tool": tool,
        "caller": principal,
        "role": role,
        "allowed": allowed,
        "duration_ms": round(duration_ms, 1),
    }
    if error:
        record["error"] = error
    _audit_log.info(json.dumps(record))
