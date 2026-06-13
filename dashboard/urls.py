from django.urls import path
from .views import (
    HomeView,
    DashboardView,
    AdminDashboardView,
    AdminUsersView,
    AdminUserAddView,
    AdminUserDeleteView,
    AdminUserExportView,
    AdminUserViewDetail,
    AdminUserEditView,
    AdminUserUpdateView,
    AdminUserDataView,
)

app_name = "dashboard"

urlpatterns = [
    # Public routes
    path("", HomeView.as_view(), name="home"),
    
    # User Dashboard
    path("dashboard/", DashboardView.as_view(), name="user-dashboard"),
    
    # Admin Dashboard
    path("admin-dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    
    # Admin User Management
    path("admin/users/", AdminUsersView.as_view(), name="admin_users"),
    path("admin/users/add/", AdminUserAddView.as_view(), name="admin_user_add"),
    path("admin/users/<int:pk>/delete/", AdminUserDeleteView.as_view(), name="admin_user_delete"),
    path("admin/users/export/", AdminUserExportView.as_view(), name="admin_user_export"),
    path("admin/users/<int:pk>/view/", AdminUserViewDetail.as_view(), name="admin_user_view"),
    path("admin/users/<int:pk>/edit/", AdminUserEditView.as_view(), name="admin_user_edit"),
    path("admin/users/<int:pk>/update/", AdminUserUpdateView.as_view(), name="admin_user_update"),
    path("admin/users/<int:pk>/data/", AdminUserDataView.as_view(), name="admin_user_data"),
]