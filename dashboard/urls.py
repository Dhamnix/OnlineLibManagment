from django.urls import path
from .views import (
    HomeView,
    DashboardView,
    AdminDashboardView,
    AdminUsersView,
    AdminUserAddView,
    AdminUserCreateView,
    AdminUserDeleteView,
    AdminUserExportView,
    AdminUserViewDetail,
    AdminUserEditView,
    AdminUserUpdateView,
    AdminUserProfileView,  
    AdminReportsView,
    AdminSettingsView,  
)

app_name = "dashboard"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="user-dashboard"),
    path("admin-dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("admin/users/", AdminUsersView.as_view(), name="admin_users"),
    path("admin/users/add/", AdminUserAddView.as_view(), name="admin_user_add"),
    path("admin/users/create/", AdminUserCreateView.as_view(), name="admin_user_create"),
    path("admin/users/<int:pk>/delete/", AdminUserDeleteView.as_view(), name="admin_user_delete"),
    path("admin/users/export/", AdminUserExportView.as_view(), name="admin_user_export"),
    path("admin/users/<int:pk>/view/", AdminUserViewDetail.as_view(), name="admin_user_view"),
    path("admin/users/<int:pk>/profile/", AdminUserProfileView.as_view(), name="admin_user_profile"),
    path("admin/users/<int:pk>/edit/", AdminUserEditView.as_view(), name="admin_user_edit"),
    path("admin/users/<int:pk>/update/", AdminUserUpdateView.as_view(), name="admin_user_update"),
    path("admin/reports/", AdminReportsView.as_view(), name="admin_reports"),
    path("admin/settings/", AdminSettingsView.as_view(), name="admin_settings"),  # <-- ADD THIS
]