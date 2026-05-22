import os
import time
import bcrypt
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.io as pio
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from .metrics import metrics_text, record_auth_attempt

# хэширование пароля
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# проверка пароля
def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# переменные окружения (пароли)
admin_pass = os.environ.get('admin_pass', 'admin123')
bot_pass = os.environ.get('bot_pass', 'bot123')
guest_pass = os.environ.get('guest_pass', 'guest123')

# хэши паролей
_admin_hash = hash_password(admin_pass)
_bot_hash = hash_password(bot_pass)
_guest_hash = hash_password(guest_pass)

# база пользователей
users_db = {
    "admin": {
        "password_hash": _admin_hash,
        "role": "admin",
        "allowed_ips": ["10.0.0.1", "10.0.0.2", "127.0.0.1"],
        "work_hours": list(range(25)),
        "work_days": [0, 1, 2, 3, 4, 5, 6, 7]
    },
    "support_bot": {
        "password_hash": _bot_hash,
        "role": "robot",
        "allowed_ips": ["172.16.1.100", "127.0.0.1"],
        "work_hours": list(range(24)),
        "work_days": [0, 1, 2, 3, 4, 5, 6]
    },
    "guest": {
        "password_hash": _guest_hash,
        "role": "viewer",
        "allowed_ips": ["192.168.1.50", "192.168.1.51", "127.0.0.1"],
        "work_hours": [10, 11, 12, 13, 14, 15, 16, 17],
        "work_days": [1, 2, 3, 4, 5]
    }
}

# текущий час
def get_current_hour():
    return int(time.strftime('%H', time.localtime()))

# текущий день недели
def get_current_weekday():
    return int(time.strftime('%w', time.localtime()))

# проверка IP
def check_ip_allowed(allowed_ips, client_ip):
    if client_ip == '127.0.0.1':
        return True
    return client_ip in allowed_ips

# проверка времени
def check_time_allowed(work_hours, work_days, current_hour, current_day):
    return (current_hour in work_hours) and (current_day in work_days)

# основная аутентификация
def authenticate_user(username, password, client_ip):
    if username not in users_db:
        return {"success": False, "reason": "invalid_user"}
    user = users_db[username]
    if not verify_password(password, user["password_hash"]):
        return {"success": False, "reason": "wrong_password"}
    if not check_ip_allowed(user["allowed_ips"], client_ip):
        return {"success": False, "reason": "ip_not_allowed"}
    hour = get_current_hour()
    day = get_current_weekday()
    if not check_time_allowed(user["work_hours"], user["work_days"], hour, day):
        return {"success": False, "reason": "time_not_allowed"}
    return {"success": True, "role": user["role"], "hour": hour, "day": day}

# статистика по ролям
def calculate_role_stats():
    roles = [users_db[u]["role"] for u in users_db]
    role_counts = {}
    for r in roles:
        role_counts[r] = role_counts.get(r, 0) + 1
    df = pd.DataFrame(list(role_counts.items()), columns=["Роль", "Количество"])
    return df

# статистика по IP
def calculate_ip_stats():
    data = []
    for name, info in users_db.items():
        data.append({
            "Пользователь": name,
            "Роль": info["role"],
            "Количество разрешённых IP": len(info["allowed_ips"]),
            "Разрешённые IP": ", ".join(info["allowed_ips"])
        })
    df = pd.DataFrame(data)
    return df

# статический график ролей
def visualize_role_stats_static(df):
    plt.figure(figsize=(6, 6))
    colors = ["lightcoral", "lightblue", "lightgreen"][:len(df)]
    explode = tuple([0.05] * len(df))
    plt.pie(df["Количество"], labels=df["Роль"], autopct="%1.1f%%",
            colors=colors, startangle=90, explode=explode)
    plt.title("Распределение пользователей по ролям")
    plt.tight_layout()
    path = os.path.join(settings.MEDIA_ROOT, 'img2.jpeg')
    plt.savefig(path)
    plt.close()
    return 'img2.jpeg'

# статический график IP
def visualize_ip_stats_static(df):
    plt.figure(figsize=(7, 4))
    bars = plt.bar(df["Пользователь"], df["Количество разрешённых IP"],
                   color="skyblue", edgecolor="black")
    plt.title("Количество разрешённых IP по пользователям")
    plt.xlabel("Пользователь")
    plt.ylabel("Количество IP")
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, height / 2,
                 str(int(height)), ha="center", va="center",
                 fontweight="bold", color="white", fontsize=11)
    plt.tight_layout()
    path = os.path.join(settings.MEDIA_ROOT, 'img1.jpeg')
    plt.savefig(path)
    plt.close()
    return 'img1.jpeg'

# интерактивный график ролей
def get_interactive_role_chart(df):
    fig = px.pie(df, values='Количество', names='Роль', title='Распределение по ролям')
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

# интерактивный график IP
def get_interactive_ip_chart(df):
    fig = px.bar(df, x='Пользователь', y='Количество разрешённых IP',
                 title='Разрешенные IP', color='Роль')
    fig.update_layout(xaxis_title="Пользователь", yaxis_title="Количество IP")
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

# страница входа
def login_view(request):
    context = {}
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        result = authenticate_user(username, password, client_ip)
        record_auth_attempt(result)
        if result['success']:
            if result['role'] == 'admin':
                return redirect('admin_dashboard')
            df_roles = calculate_role_stats()
            df_ips = calculate_ip_stats()
            visualize_role_stats_static(df_roles)
            visualize_ip_stats_static(df_ips)
            role_chart_html = get_interactive_role_chart(df_roles)
            ip_chart_html = get_interactive_ip_chart(df_ips)
            context = {
                'success': True,
                'user_role': result['role'],
                'role_table': df_roles.to_html(classes='table table-striped table-bordered', index=False),
                'ip_table': df_ips.to_html(classes='table table-striped table-bordered', index=False),
                'img_role_url': f'{settings.MEDIA_URL}img2.jpeg',
                'img_ip_url': f'{settings.MEDIA_URL}img1.jpeg',
                'role_chart_html': role_chart_html,
                'ip_chart_html': ip_chart_html,
                'login_time': time.strftime('%H:%M:%S'),
                'client_ip': client_ip
            }
            return render(request, 'risk_app/dashboard.html', context)
        else:
            context['error'] = f"Доступ запрещён: {result['reason']}"
            context['form_data'] = request.POST
    return render(request, 'risk_app/login.html', context)

# панель администратора
def admin_dashboard(request):
    if request.method == 'POST':
        user_to_edit = request.POST.get('edit_user')
        new_ips = request.POST.get('new_ips')
        new_hours_start = request.POST.get('new_hours_start')
        new_hours_end = request.POST.get('new_hours_end')
        if user_to_edit in users_db:
            users_db[user_to_edit]['allowed_ips'] = [ip.strip() for ip in new_ips.split(',')]
            try:
                start = int(new_hours_start)
                end = int(new_hours_end)
                if start < end:
                    users_db[user_to_edit]['work_hours'] = list(range(start, end))
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
        'users': users_db,
        'role_table': df_roles.to_html(classes='table table-striped table-bordered', index=False),
        'ip_table': df_ips.to_html(classes='table table-striped table-bordered', index=False),
        'img_role_url': f'{settings.MEDIA_URL}img2.jpeg',
        'img_ip_url': f'{settings.MEDIA_URL}img1.jpeg',
        'role_chart_html': role_chart_html,
        'ip_chart_html': ip_chart_html,
    }
    return render(request, 'risk_app/admin_dashboard.html', context)

def metrics_view(request):
    return HttpResponse(
        metrics_text(),
        content_type='text/plain; version=0.0.4; charset=utf-8',
    )
