import os
import time

import bcrypt
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.io as pio
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .metrics import metrics_text, record_auth_attempt


# Блок криптографической защиты паролей.
def hash_password(password: str) -> str:
    # bcrypt.gensalt() добавляет соль, поэтому одинаковые пароли получают разные хеши.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    # checkpw сравнивает введенный пароль с сохраненным хешем без раскрытия исходного пароля.
    return bcrypt.checkpw(password.encode(), hashed.encode())


# Блок чтения секретов из окружения контейнера.
# Переменные окружения позволяют не хранить реальные пароли прямо в коде приложения.
admin_pass = os.environ.get("admin_pass", "admin123")
bot_pass = os.environ.get("bot_pass", "bot123")
guest_pass = os.environ.get("guest_pass", "guest123")

# Блок подготовки демонстрационной базы пользователей.
# В памяти сохраняются только хеши паролей, роли, разрешенные IP и расписание доступа.
_admin_hash = hash_password(admin_pass)
_bot_hash = hash_password(bot_pass)
_guest_hash = hash_password(guest_pass)

users_db = {
    "admin": {
        "password_hash": _admin_hash,
        "role": "admin",
        "allowed_ips": ["*"],
        "work_hours": list(range(25)),
        "work_days": [0, 1, 2, 3, 4, 5, 6, 7],
    },
    "support_bot": {
        "password_hash": _bot_hash,
        "role": "robot",
        "allowed_ips": ["172.16.1.100", "127.0.0.1"],
        "work_hours": list(range(24)),
        "work_days": [0, 1, 2, 3, 4, 5, 6],
    },
    "guest": {
        "password_hash": _guest_hash,
        "role": "viewer",
        "allowed_ips": ["192.168.1.50", "192.168.1.51", "127.0.0.1"],
        "work_hours": [10, 11, 12, 13, 14, 15, 16, 17],
        "work_days": [1, 2, 3, 4, 5],
    },
}


# Блок получения текущего времени для политики доступа.
def get_current_hour():
    # time.localtime() берет время контейнера, которое используется для проверки рабочих часов.
    return int(time.strftime("%H", time.localtime()))


def get_current_weekday():
    # %w возвращает номер дня недели; он сравнивается со списком разрешенных дней.
    return int(time.strftime("%w", time.localtime()))


# Блок проверки сетевого ограничения.
def check_ip_allowed(allowed_ips, client_ip):
    if "*" in allowed_ips:
        return True
    # Локальный адрес разрешен для тестирования приложения внутри контейнера и среды разработки.
    if client_ip == "127.0.0.1":
        return True
    # Для внешних клиентов доступ разрешается только при совпадении с белым списком.
    return client_ip in allowed_ips


# Блок проверки временного ограничения.
def check_time_allowed(work_hours, work_days, current_hour, current_day):
    # Пользователь проходит проверку только при одновременном совпадении часа и дня недели.
    return (current_hour in work_hours) and (current_day in work_days)


# Блок аутентификации и авторизации пользователя.
def authenticate_user(username, password, client_ip):
    # Сначала проверяется существование пользователя, чтобы не обращаться к пустой записи.
    if username not in users_db:
        return {"success": False, "reason": "invalid_user"}

    user = users_db[username]

    # Пароль проверяется через bcrypt; открытый пароль в системе не хранится.
    if not verify_password(password, user["password_hash"]):
        return {"success": False, "reason": "wrong_password"}

    # Администратор в этой лабораторной работе допускается с любого IP-адреса.
    if username == "admin":
        ip_allowed = True
    else:
        # IP-адрес клиента сравнивается с разрешенным списком для конкретной учетной записи.
        ip_allowed = check_ip_allowed(user["allowed_ips"], client_ip)

    if not ip_allowed:
        return {"success": False, "reason": "ip_not_allowed"}

    hour = get_current_hour()
    day = get_current_weekday()

    # Последним шагом проверяется расписание доступа.
    if not check_time_allowed(user["work_hours"], user["work_days"], hour, day):
        return {"success": False, "reason": "time_not_allowed"}

    # При успешной проверке возвращается роль, которая определяет дальнейший маршрут.
    return {"success": True, "role": user["role"], "hour": hour, "day": day}


# Блок преобразования данных о ролях в таблицу.
def calculate_role_stats():
    roles = [users_db[u]["role"] for u in users_db]
    role_counts = {}
    for role in roles:
        # Счетчик показывает, сколько пользователей относится к каждой роли.
        role_counts[role] = role_counts.get(role, 0) + 1

    # DataFrame нужен для табличного вывода и построения графиков.
    return pd.DataFrame(list(role_counts.items()), columns=["Роль", "Количество"])


# Блок преобразования данных об IP-ограничениях в таблицу.
def calculate_ip_stats():
    data = []
    for name, info in users_db.items():
        data.append(
            {
                "Пользователь": name,
                "Роль": info["role"],
                "Количество разрешенных IP": len(info["allowed_ips"]),
                "Разрешенные IP": ", ".join(info["allowed_ips"]),
            }
        )

    return pd.DataFrame(data)


# Блок статической визуализации распределения ролей.
def visualize_role_stats_static(df):
    plt.figure(figsize=(6, 6))
    colors = ["lightcoral", "lightblue", "lightgreen"][: len(df)]
    explode = tuple([0.05] * len(df))

    # Круговая диаграмма показывает долю каждой роли среди пользователей.
    plt.pie(
        df["Количество"],
        labels=df["Роль"],
        autopct="%1.1f%%",
        colors=colors,
        startangle=90,
        explode=explode,
    )
    plt.title("Распределение пользователей по ролям")
    plt.tight_layout()

    # График сохраняется в MEDIA_ROOT, чтобы шаблон мог отдать его как медиафайл.
    path = os.path.join(settings.MEDIA_ROOT, "img2.jpeg")
    plt.savefig(path)
    plt.close()
    return "img2.jpeg"


# Блок статической визуализации IP-ограничений.
def visualize_ip_stats_static(df):
    plt.figure(figsize=(7, 4))
    bars = plt.bar(
        df["Пользователь"],
        df["Количество разрешенных IP"],
        color="skyblue",
        edgecolor="black",
    )
    plt.title("Количество разрешенных IP по пользователям")
    plt.xlabel("Пользователь")
    plt.ylabel("Количество IP")

    # Подписи на столбцах помогают быстро увидеть точное число разрешенных адресов.
    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height / 2,
            str(int(height)),
            ha="center",
            va="center",
            fontweight="bold",
            color="white",
            fontsize=11,
        )

    plt.tight_layout()
    path = os.path.join(settings.MEDIA_ROOT, "img1.jpeg")
    plt.savefig(path)
    plt.close()
    return "img1.jpeg"


# Блок интерактивной визуализации ролей.
def get_interactive_role_chart(df):
    # Plotly формирует HTML-фрагмент диаграммы для встраивания в dashboard.html.
    fig = px.pie(df, values="Количество", names="Роль", title="Распределение по ролям")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return pio.to_html(fig, full_html=False, include_plotlyjs="cdn")


# Блок интерактивной визуализации IP-ограничений.
def get_interactive_ip_chart(df):
    fig = px.bar(
        df,
        x="Пользователь",
        y="Количество разрешенных IP",
        title="Разрешенные IP",
        color="Роль",
    )
    fig.update_layout(xaxis_title="Пользователь", yaxis_title="Количество IP")
    return pio.to_html(fig, full_html=False, include_plotlyjs="cdn")


# Блок обработки входа пользователя.
def login_view(request):
    context = {}

    if request.method == "POST":
        # Данные формы и IP клиента извлекаются из HTTP-запроса.
        username = request.POST.get("username")
        password = request.POST.get("password")
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        real_ip = request.META.get("HTTP_X_REAL_IP")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else real_ip or request.META.get("REMOTE_ADDR", "127.0.0.1")
        )

        # authenticate_user возвращает результат всех проверок безопасности.
        result = authenticate_user(username, password, client_ip)
        record_auth_attempt(result)

        if result["success"]:
            # Администратор перенаправляется в отдельную панель управления доступом.
            if result["role"] == "admin":
                return redirect("admin_dashboard")

            df_roles = calculate_role_stats()
            df_ips = calculate_ip_stats()
            visualize_role_stats_static(df_roles)
            visualize_ip_stats_static(df_ips)
            role_chart_html = get_interactive_role_chart(df_roles)
            ip_chart_html = get_interactive_ip_chart(df_ips)

            # Контекст передает в шаблон таблицы, графики, роль, IP и время входа.
            context = {
                "success": True,
                "user_role": result["role"],
                "role_table": df_roles.to_html(
                    classes="table table-striped table-bordered", index=False
                ),
                "ip_table": df_ips.to_html(
                    classes="table table-striped table-bordered", index=False
                ),
                "img_role_url": f"{settings.MEDIA_URL}img2.jpeg",
                "img_ip_url": f"{settings.MEDIA_URL}img1.jpeg",
                "role_chart_html": role_chart_html,
                "ip_chart_html": ip_chart_html,
                "login_time": time.strftime("%H:%M:%S"),
                "client_ip": client_ip,
            }
            return render(request, "risk_app/dashboard.html", context)

        # При отказе причина выводится пользователю и фиксируется в метриках.
        context["error"] = f"Доступ запрещен: {result['reason']}"
        context["form_data"] = request.POST

    return render(request, "risk_app/login.html", context)


# Блок администрирования правил доступа.
def admin_dashboard(request):
    if request.method == "POST":
        # Администратор выбирает пользователя и задает новый список IP и рабочие часы.
        user_to_edit = request.POST.get("edit_user")
        new_ips = request.POST.get("new_ips")
        new_hours_start = request.POST.get("new_hours_start")
        new_hours_end = request.POST.get("new_hours_end")

        if user_to_edit in users_db:
            # Строка с IP разбивается по запятым и сохраняется как список разрешенных адресов.
            users_db[user_to_edit]["allowed_ips"] = [ip.strip() for ip in new_ips.split(",")]

            try:
                start = int(new_hours_start)
                end = int(new_hours_end)
                if start < end:
                    # Диапазон часов преобразуется в список значений для проверки расписания.
                    users_db[user_to_edit]["work_hours"] = list(range(start, end))
            except ValueError:
                pass

            messages.success(request, f"Настройки для {user_to_edit} обновлены!")

    df_roles = calculate_role_stats()
    df_ips = calculate_ip_stats()
    visualize_role_stats_static(df_roles)
    visualize_ip_stats_static(df_ips)
    role_chart_html = get_interactive_role_chart(df_roles)
    ip_chart_html = get_interactive_ip_chart(df_ips)

    context = {
        "users": users_db,
        "role_table": df_roles.to_html(
            classes="table table-striped table-bordered", index=False
        ),
        "ip_table": df_ips.to_html(classes="table table-striped table-bordered", index=False),
        "img_role_url": f"{settings.MEDIA_URL}img2.jpeg",
        "img_ip_url": f"{settings.MEDIA_URL}img1.jpeg",
        "role_chart_html": role_chart_html,
        "ip_chart_html": ip_chart_html,
    }
    return render(request, "risk_app/admin_dashboard.html", context)


# Блок выдачи метрик мониторинга.
def metrics_view(request):
    # Endpoint /metrics возвращает текстовый формат Prometheus для сбора показателей.
    return HttpResponse(
        metrics_text(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )
