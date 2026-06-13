from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count
from django.utils import timezone

from borrowing.models import Borrow, Reservation, Fine
from books.models import Book
from django.contrib.auth import get_user_model


User = get_user_model()


class DashboardView(LoginRequiredMixin, TemplateView):
    """User-facing dashboard (keeps existing behavior)."""

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

        # Recommended books: available, not already borrowed or reserved by user
        borrowed_ids = Borrow.objects.filter(user=user).values_list("book_id", flat=True)
        reserved_ids = Reservation.objects.filter(user=user).values_list("book_id", flat=True)

        excluded_ids = set(list(borrowed_ids) + list(reserved_ids))

        recommended_books = (
            Book.objects.filter(available_copies__gt=0)
            .exclude(pk__in=excluded_ids)
            .annotate(borrow_count=Count("borrowings"))
            .order_by("-borrow_count", "title")[:5]
        )

        context.update(
            {
                "active_borrowings": active_borrowings,
                "reservations": reservations,
                "outstanding_fines": outstanding_fines_qs,
                "fines_total": fines_total,
                "recommended_books": recommended_books,
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
