from django.urls import path
from . import views

# Блок маршрутов приложения risk_app.
# Каждый path связывает URL с функцией-представлением из views.py.
urlpatterns = [
    # Главная страница открывает форму входа и запускает проверки доступа.
    path('', views.login_view, name='login'),
    # Панель администратора позволяет менять IP-адреса и рабочие часы пользователей.
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    # Endpoint метрик используется Prometheus для мониторинга приложения.
    path('metrics', views.metrics_view, name='metrics'),
    # Дублирующий маршрут поддерживает вариант URL со слешем на конце.
    path('metrics/', views.metrics_view, name='metrics_slash'),
]
