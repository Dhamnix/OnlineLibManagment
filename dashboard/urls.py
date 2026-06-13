from django.urls import path
from .views import HomeView, DashboardView, AdminDashboardView

app_name = "dashboard"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="user-dashboard"),
    path("admin-dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
]
