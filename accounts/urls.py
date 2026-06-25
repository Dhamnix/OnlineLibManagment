# accounts/urls.py
from django.urls import path
from .views import (
    CustomLoginView, 
    CustomLogoutView, 
    ProfileView, 
    RegisterView,
    ProfileUpdateView,
    ChangePasswordView
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/update/", ProfileUpdateView.as_view(), name="profile_update"),
    path("profile/change-password/", ChangePasswordView.as_view(), name="change_password"),
]