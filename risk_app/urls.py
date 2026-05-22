from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('metrics', views.metrics_view, name='metrics'),
    path('metrics/', views.metrics_view, name='metrics_slash'),
]
