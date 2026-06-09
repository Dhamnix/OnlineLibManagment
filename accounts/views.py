from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import BootstrapAuthenticationForm, CustomUserRegistrationForm


class RegisterView(CreateView):
    template_name = "accounts/register.html"
    form_class = CustomUserRegistrationForm
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Your account has been created successfully.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = BootstrapAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "You are now logged in.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.", extra_tags="danger")
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    # Django's LogoutView is POST-only in modern Django, which prevents logout CSRF.
    next_page = reverse_lazy("accounts:login")

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been logged out.")
        return response


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/profile.html"
    login_url = reverse_lazy("accounts:login")
