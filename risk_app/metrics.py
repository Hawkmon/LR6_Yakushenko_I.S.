import gc
import os
import threading
import time
from collections import defaultdict


APP_STARTED_AT = time.time()

_lock = threading.Lock()
_request_total = defaultdict(int)
_request_duration_sum = defaultdict(float)
_auth_total = defaultdict(int)


def _label_value(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**labels):
    if not labels:
        return ""
    body = ",".join(f'{key}="{_label_value(value)}"' for key, value in labels.items())
    return "{" + body + "}"


def _metric_line(name, value, **labels):
    return f"{name}{_labels(**labels)} {value}"


def record_auth_attempt(result):
    status = "success" if result.get("success") else "failure"
    reason = result.get("reason", "ok")
    role = result.get("role", "none")
    with _lock:
        _auth_total[(status, reason, role)] += 1


class PrometheusMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - started_at

        path = request.path_info or "/"
        if not path.startswith("/metrics"):
            route = "admin_panel" if path.startswith("/admin-panel") else "login"
            labels = (request.method, route, response.status_code)
            with _lock:
                _request_total[labels] += 1
                _request_duration_sum[labels] += duration

        return response


def metrics_text():
    with _lock:
        request_total = dict(_request_total)
        request_duration_sum = dict(_request_duration_sum)
        auth_total = dict(_auth_total)

    lines = [
        "# HELP auth_app_up Application availability flag.",
        "# TYPE auth_app_up gauge",
        _metric_line("auth_app_up", 1),
        "# HELP auth_app_uptime_seconds Application uptime in seconds.",
        "# TYPE auth_app_uptime_seconds gauge",
        _metric_line("auth_app_uptime_seconds", f"{time.time() - APP_STARTED_AT:.3f}"),
        "# HELP auth_app_users_total Number of configured users in the access-control model.",
        "# TYPE auth_app_users_total gauge",
        _metric_line("auth_app_users_total", 3),
        "# HELP auth_app_request_total Total HTTP requests by method, route and status.",
        "# TYPE auth_app_request_total counter",
    ]

    for (method, route, status), value in sorted(request_total.items()):
        lines.append(
            _metric_line(
                "auth_app_request_total",
                value,
                method=method,
                route=route,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP auth_app_request_duration_seconds_sum Total request duration by method, route and status.",
            "# TYPE auth_app_request_duration_seconds_sum counter",
        ]
    )
    for (method, route, status), value in sorted(request_duration_sum.items()):
        lines.append(
            _metric_line(
                "auth_app_request_duration_seconds_sum",
                f"{value:.6f}",
                method=method,
                route=route,
                status=status,
            )
        )

    lines.extend(
        [
            "# HELP auth_app_login_attempts_total Total authentication attempts by result.",
            "# TYPE auth_app_login_attempts_total counter",
        ]
    )
    for (status, reason, role), value in sorted(auth_total.items()):
        lines.append(
            _metric_line(
                "auth_app_login_attempts_total",
                value,
                status=status,
                reason=reason,
                role=role,
            )
        )

    lines.extend(
        [
            "# HELP auth_app_python_objects Number of objects tracked by Python GC.",
            "# TYPE auth_app_python_objects gauge",
            _metric_line("auth_app_python_objects", len(gc.get_objects())),
            "# HELP auth_app_process_pid Process identifier inside the container.",
            "# TYPE auth_app_process_pid gauge",
            _metric_line("auth_app_process_pid", os.getpid()),
        ]
    )

    return "\n".join(lines) + "\n"
