from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count
from django.utils import timezone

from borrowing.models import Borrow, Reservation, Fine
from books.models import Book
from django.contrib.auth import get_user_model

from recommendations.services import recommend_for_user, similar_books


User = get_user_model()


class HomeView(TemplateView):
    """Public landing page for the application."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Most popular books (by borrow count)
        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:5]
        )

        # Latest books (fallback if popularity is low)
        latest_books = Book.objects.order_by("-pk")[:5]

        context["popular_books"] = popular_books
        context["latest_books"] = latest_books

        # Role-based quick links
        user = self.request.user
        context["user"] = user
        if user.is_authenticated:
            context["is_admin"] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        else:
            context["is_admin"] = False

        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """User-facing dashboard including recommendation sections."""

    template_name = "dashboard/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Active borrowings (not returned)
        active_borrowings = (
            Borrow.objects.filter(user=user, status=Borrow.StatusChoices.BORROWED)
            .select_related("book")
            .order_by("due_date")
        )

        # Reservations (exclude cancelled)
        reservations = (
            Reservation.objects.filter(user=user)
            .exclude(status=Reservation.StatusChoices.CANCELLED)
            .select_related("book")
        )

        # Outstanding fines
        outstanding_fines_qs = (
            Fine.objects.filter(user=user, is_paid=False).select_related("borrow", "borrow__book")
        )
        fines_total = outstanding_fines_qs.aggregate(total=Sum("amount"))["total"] or 0

        # Recommended For You (from recommendation service)
        recommended_for_you = recommend_for_user(user, limit=6)

        # Similar Books: base on user's most recently borrowed book
        last_borrow = (
            Borrow.objects.filter(user=user).select_related("book").order_by("-borrow_date").first()
        )
        similar_books_list = []
        if last_borrow and last_borrow.book:
            similar_books_list = similar_books(last_borrow.book, limit=6)

        context.update(
            {
                "active_borrowings": active_borrowings,
                "reservations": reservations,
                "outstanding_fines": outstanding_fines_qs,
                "fines_total": fines_total,
                "recommended_for_you": recommended_for_you,
                "similar_books": similar_books_list,
            }
        )
        return context


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin dashboard showing aggregates and popular items.

    Access is limited to staff users.
    """

    template_name = "dashboard/admin_dashboard.html"

    def test_func(self):
        # Only staff users (or superusers) can access the admin dashboard
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Total books
        total_books = Book.objects.count()

        # Total users
        total_users = User.objects.count()

        # Active borrowings (status BORROWED)
        active_borrowings_qs = Borrow.objects.filter(status=Borrow.StatusChoices.BORROWED).select_related(
            "user", "book"
        )
        active_borrowings = active_borrowings_qs.count()

        # Overdue borrowings: borrowed and due_date in the past
        now = timezone.now()
        overdue_qs = active_borrowings_qs.filter(due_date__lt=now).order_by("due_date")
        overdue_count = overdue_qs.count()

        # Most popular books by borrow count
        popular_books = (
            Book.objects.annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:10]
            .select_related()
        )

        context.update(
            {
                "total_books": total_books,
                "total_users": total_users,
                "active_borrowings_count": active_borrowings,
                "overdue_count": overdue_count,
                "overdue_list": overdue_qs,
                "popular_books": popular_books,
            }
        )
        return context
