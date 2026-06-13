from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count

from borrowing.models import Borrow, Reservation, Fine
from books.models import Book


class DashboardView(LoginRequiredMixin, TemplateView):
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
