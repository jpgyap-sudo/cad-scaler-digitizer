"""
FastAPI Middleware — automatically logs all requests, responses,
and decisions to the monitoring database.

Attaches a `monitor` helper to request.state for manual logging
within endpoints (e.g., log_tool_usage(), log_decision()).
"""

import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.monitoring.log_db import log_task, log_tool_usage


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Logs every API request as a task to the monitoring database."""

    async def dispatch(self, request: Request, call_next):
        # Skip monitoring endpoints themselves to avoid recursion
        if request.url.path.startswith("/api/monitor/") or request.url.path == "/health":
            return await call_next(request)

        session_id = request.query_params.get("session_id") or \
                     request.headers.get("X-Session-Id") or \
                     request.cookies.get("session_id") or \
                     str(uuid.uuid4())[:8]

        # Attach monitor helper to request state
        request.state.monitor = _MonitorHelper(session_id)
        request.state.session_id = session_id

        # Extract task type from URL path
        task_type = _path_to_task_type(request.url.path)

        # Minimal input logging — avoid reading body (breaks UploadFile streaming)
        content_type_header = request.headers.get("content-type", "")
        input_params = {"content_type": content_type_header[:60]} if content_type_header else None

        # Time the request
        start_ms = int(time.time() * 1000)

        try:
            response = await call_next(request)
            duration_ms = int(time.time() * 1000) - start_ms

            # Log the task
            log_task(
                session_id=session_id,
                task_type=task_type,
                furniture_type=request.query_params.get("furniture_type") or
                              request.headers.get("X-Furniture-Type"),
                input_params=input_params,
                output_summary={"status_code": response.status_code},
                success=response.status_code < 500,
                duration_ms=duration_ms,
            )

            return response

        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            log_task(
                session_id=session_id,
                task_type=task_type,
                error_message=str(e)[:500],
                success=False,
                duration_ms=duration_ms,
            )
            raise


def _path_to_task_type(path: str) -> str:
    """Map URL path to a task type string."""
    path = path.lower()
    if "/digitize/hybrid" in path:
        return "hybrid_digitize"
    if "/digitize" in path:
        return "digitize"
    if "/chat" in path:
        return "chat"
    if "/adjust" in path:
        return "adjust"
    if "/material/edit" in path:
        return "material_edit"
    if "/corrections/submit" in path:
        return "correction"
    if "/corrections" in path:
        return "correction_query"
    if "/batch" in path:
        return "batch_convert"
    if "/export" in path:
        return "export"
    if "/ml/" in path and "/ml/status" not in path and "/ml/feedback" not in path:
        return "ml_operation"
    if "/ml/feedback" in path:
        return "ml_feedback"
    if "/brain/" in path:
        return "brain_query"
    if "/benchmark" in path:
        return "benchmark"
    if "/presets" in path:
        return "preset_operation"
    if "/learn/" in path:
        return "learning_operation"
    return "api_request"


class _MonitorHelper:
    """Attached to request.state.monitor for manual logging within endpoints."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    def log_tool(self, tool_name: str, input_summary: str = None,
                 output_summary: str = None, duration_ms: int = None,
                 success: bool = True):
        log_tool_usage(self.session_id, tool_name, input_summary,
                       output_summary, duration_ms, success)

    def log_decision(self, decision_type: str, confidence: float = None,
                     rationale: str = None, context: dict = None):
        from app.monitoring.log_db import log_decision
        log_decision(self.session_id, decision_type, confidence,
                     rationale, context=context)

    def log_chat(self, user_message: str, assistant_response: str,
                 extracted_action: str = None, furniture_type: str = None,
                 dimension_changes: dict = None, material_changes: dict = None,
                 backend_used: str = None, response_time_ms: int = None,
                 token_count: int = None):
        from app.monitoring.log_db import log_chat
        log_chat(self.session_id, user_message, assistant_response,
                 extracted_action, furniture_type, dimension_changes,
                 material_changes, backend_used, response_time_ms, token_count)
