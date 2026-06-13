from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Sum, Q
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib.auth.forms import PasswordChangeForm

from .forms import BootstrapAuthenticationForm, CustomUserRegistrationForm
from borrowing.models import Borrow, Reservation, Fine
from .models import CustomUser


class RegisterView(CreateView):
    template_name = "registration/register.html"
    form_class = CustomUserRegistrationForm
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        messages.success(self.request, "Your account has been created successfully.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Total books borrowed (all time)
        context['total_borrowed'] = Borrow.objects.filter(user=user).count()
        
        # Currently active borrowings (not returned yet)
        context['active_borrowings'] = Borrow.objects.filter(
            user=user, 
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        # Active reservations (not cancelled/completed)
        context['active_reservations'] = Reservation.objects.filter(
            user=user
        ).exclude(
            status__in=[
                Reservation.StatusChoices.CANCELLED,
                Reservation.StatusChoices.COMPLETED
            ]
        ).count()
        
        # Total unpaid fines amount
        total_fines = Fine.objects.filter(
            user=user, 
            is_paid=False
        ).aggregate(total=Sum('amount'))['total']
        context['total_fines'] = total_fines or 0
        
        # Recent activity (last 5 borrowings with book info)
        context['recent_borrowings'] = Borrow.objects.filter(
            user=user
        ).select_related('book').order_by('-borrow_date')[:5]
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """View for updating user profile information."""
    model = CustomUser
    fields = ['first_name', 'last_name', 'email']
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)


class ChangePasswordView(LoginRequiredMixin, UpdateView):
    """View for changing user password."""
    model = CustomUser
    form_class = PasswordChangeForm
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)  # Keep user logged in
        messages.success(self.request, "Your password has been changed successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.", extra_tags="danger")
        return super().form_invalid(form)