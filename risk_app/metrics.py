import gc
import os
import threading
import time
from collections import defaultdict


# Блок глобального состояния метрик.
# Время старта нужно для uptime, а словари-счетчики накапливают запросы и попытки входа.
APP_STARTED_AT = time.time()

_lock = threading.Lock()
_request_total = defaultdict(int)
_request_duration_sum = defaultdict(float)
_auth_total = defaultdict(int)


# Блок экранирования значений Prometheus label.
def _label_value(value):
    # Экранирование защищает текстовый формат метрик от кавычек, переносов строк и обратных слешей.
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(**labels):
    # При отсутствии label возвращается пустая строка, чтобы метрика была записана без фигурных скобок.
    if not labels:
        return ""
    body = ",".join(f'{key}="{_label_value(value)}"' for key, value in labels.items())
    return "{" + body + "}"


def _metric_line(name, value, **labels):
    # Формирует одну строку в формате: имя_метрики{labels} значение.
    return f"{name}{_labels(**labels)} {value}"


# Блок учета попыток аутентификации.
def record_auth_attempt(result):
    status = "success" if result.get("success") else "failure"
    reason = result.get("reason", "ok")
    role = result.get("role", "none")
    # Lock защищает счетчик от одновременного изменения несколькими запросами.
    with _lock:
        _auth_total[(status, reason, role)] += 1


# Блок middleware для измерения HTTP-запросов.
class PrometheusMetricsMiddleware:
    def __init__(self, get_response):
        # get_response - следующий обработчик в цепочке Django middleware.
        self.get_response = get_response

    def __call__(self, request):
        # perf_counter используется для точного измерения длительности обработки запроса.
        started_at = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - started_at

        path = request.path_info or "/"
        # Сам endpoint /metrics не учитывается, чтобы сбор метрик не искажал статистику приложения.
        if not path.startswith("/metrics"):
            route = "admin_panel" if path.startswith("/admin-panel") else "login"
            labels = (request.method, route, response.status_code)
            with _lock:
                _request_total[labels] += 1
                _request_duration_sum[labels] += duration

        return response


# Блок формирования ответа для Prometheus.
def metrics_text():
    # Данные копируются под lock, а текст собирается уже без удержания блокировки.
    with _lock:
        request_total = dict(_request_total)
        request_duration_sum = dict(_request_duration_sum)
        auth_total = dict(_auth_total)

    # HELP и TYPE описывают назначение и тип каждой метрики для Prometheus.
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

    # Блок вывода счетчика HTTP-запросов по методу, маршруту и статусу.
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
    # Блок вывода суммарного времени обработки запросов.
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
    # Блок вывода статистики успешных и неуспешных попыток входа.
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
            # Технические метрики процесса помогают видеть состояние Python-приложения в контейнере.
            "# HELP auth_app_python_objects Number of objects tracked by Python GC.",
            "# TYPE auth_app_python_objects gauge",
            _metric_line("auth_app_python_objects", len(gc.get_objects())),
            "# HELP auth_app_process_pid Process identifier inside the container.",
            "# TYPE auth_app_process_pid gauge",
            _metric_line("auth_app_process_pid", os.getpid()),
        ]
    )

    return "\n".join(lines) + "\n"
