from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from django.core.exceptions import ValidationError
from datetime import timedelta

from books.models import Book
from .models import Borrow, Reservation, Fine
from notif.services import (
    notify_borrow,
    notify_return,
    notify_reservation,
    notify_reservation_created,
    notify_fine,
    notify_fine_paid,
    notify_reservation_cancelled,
    create_notification,
)
from notif.models import Notification


# ============================================================
# USER VIEWS
# ============================================================

class BorrowListView(LoginRequiredMixin, ListView):
    """List of user's borrowings (active + pending requests)."""
    model = Borrow
    template_name = "borrowing/borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Borrow.objects.select_related("book", "user")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return qs.all().order_by('-request_date')
        return qs.filter(user=user).order_by('-request_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_borrowings = Borrow.objects.all()
        else:
            all_borrowings = Borrow.objects.filter(user=user)
        
        now = timezone.now()
        
        context['pending_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.PENDING
        ).count()
        
        context['total_active'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        three_days_later = now + timezone.timedelta(days=3)
        context['due_soon_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__gte=now,
            due_date__lte=three_days_later
        ).count()
        
        context['overdue_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__lt=now
        ).count()
        
        context['now'] = now
        context['is_admin'] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        
        return context


class RequestBorrowView(LoginRequiredMixin, View):
    """User submits a borrow request (status=PENDING). Does NOT reduce available_copies."""

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        if book.available_copies <= 0:
            messages.error(request, "This book is currently out of stock and cannot be requested.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        
        # Check if user already has a pending request or active borrow for this book
        existing = Borrow.objects.filter(
            user=request.user,
            book=book,
            status__in=[Borrow.StatusChoices.PENDING, Borrow.StatusChoices.BORROWED]
        ).exists()
        if existing:
            messages.warning(request, "You already have a pending request or active borrow for this book.")
            return redirect("books:book_detail", pk=book_id)
        
        return render(request, "borrowing/borrow_confirm.html", {"book": book})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        
        try:
            with transaction.atomic():
                book_to_request = Book.objects.select_for_update().get(pk=book_id)
                
                # Check if user already has a pending request or active borrow
                existing = Borrow.objects.filter(
                    user=request.user,
                    book=book_to_request,
                    status__in=[Borrow.StatusChoices.PENDING, Borrow.StatusChoices.BORROWED]
                ).exists()
                if existing:
                    messages.warning(request, "You already have a pending request or active borrow for this book.")
                    return redirect("borrowing:borrow_list")

                if book_to_request.available_copies <= 0:
                    messages.error(request, "This book is currently out of stock.", extra_tags="danger")
                    return redirect("books:book_detail", pk=book_id)
                
                # Create a PENDING borrow request - do NOT reduce available_copies
                borrow = Borrow.objects.create(
                    user=request.user,
                    book=book_to_request,
                    status=Borrow.StatusChoices.PENDING,
                )
                
            messages.success(request, f"Your borrow request for '{book.title}' has been submitted. Please wait for admin approval.")
            return redirect("borrowing:borrow_list")
        except Exception:
            messages.error(request, "An error occurred while submitting the borrow request.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)


class ReturnBookView(LoginRequiredMixin, View):
    """Admin-only: confirm book return from a user."""
    
    def post(self, request, pk):
        user = request.user
        
        # Only admins can return books
        if not (user.is_superuser or getattr(user, "role", None) == "ADMIN"):
            messages.error(request, "Only administrators can process book returns.", extra_tags="danger")
            return redirect("borrowing:borrow_list")
        
        borrow = get_object_or_404(Borrow, pk=pk)

        if borrow.status == Borrow.StatusChoices.RETURNED:
            messages.warning(request, "This book has already been returned.")
            return redirect("borrowing:admin_borrow_list")

        if borrow.status != Borrow.StatusChoices.BORROWED:
            messages.warning(request, "This borrow is not in a state that can be returned.")
            return redirect("borrowing:admin_borrow_list")

        try:
            with transaction.atomic():
                borrow.status = Borrow.StatusChoices.RETURNED
                borrow.return_date = timezone.now()
                borrow.save()
                
                book = Book.objects.select_for_update().get(pk=borrow.book.pk)
                book.available_copies += 1
                book.save()

                from .services import create_or_update_fine_for_borrow
                fine = create_or_update_fine_for_borrow(borrow)
                
                # Check reservations
                oldest_res = Reservation.objects.filter(
                    book=book,
                    status=Reservation.StatusChoices.PENDING
                ).order_by("reservation_date").first()

                if oldest_res:
                    oldest_res.status = Reservation.StatusChoices.AVAILABLE
                    oldest_res.save()
                    
                    messages.info(
                        request,
                        f"Notification: Reserving user '{oldest_res.user.username}' has been notified that '{book.title}' is available."
                    )
                
            messages.success(request, f"Book '{borrow.book.title}' returned by '{borrow.user.username}' has been processed successfully.")
        except Exception:
            messages.error(request, "An error occurred while processing the return.", extra_tags="danger")
            
        return redirect("borrowing:admin_borrow_list")


class BorrowHistoryView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_history.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Borrow.objects.select_related("book", "user")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            queryset = qs.all()
        else:
            queryset = qs.filter(user=user)

        status_filter = self.request.GET.get("status", "").strip().lower()
        now = timezone.now()

        if status_filter == "pending":
            queryset = queryset.filter(status=Borrow.StatusChoices.PENDING)
        elif status_filter == "active":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__gte=now)
        elif status_filter == "returned":
            queryset = queryset.filter(status=Borrow.StatusChoices.RETURNED)
        elif status_filter == "overdue":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__lt=now)
        elif status_filter == "rejected":
            queryset = queryset.filter(status=Borrow.StatusChoices.REJECTED)

        return queryset.order_by('-request_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip().lower()
        context["current_status"] = status
        context["now"] = timezone.now()
        context['is_admin'] = self.request.user.is_superuser or getattr(self.request.user, "role", None) == "ADMIN"
        return context


# ============================================================
# ADMIN VIEWS
# ============================================================

class AdminBorrowRequestsView(LoginRequiredMixin, ListView):
    """Admin view: list pending borrow requests for approval/rejection."""
    model = Borrow
    template_name = "borrowing/admin_borrow_requests.html"
    context_object_name = "requests"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission to access this page.", extra_tags="danger")
            return redirect('borrowing:borrow_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Borrow.objects.select_related("book", "user").filter(
            status=Borrow.StatusChoices.PENDING
        ).order_by('request_date')
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(book__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['pending_count'] = Borrow.objects.filter(
            status=Borrow.StatusChoices.PENDING
        ).count()
        context['default_days'] = getattr(__import__('django.conf', fromlist=['settings']).settings, 'BORROWING_DAYS', 14)
        return context


class ApproveBorrowView(LoginRequiredMixin, View):
    """Admin approves a pending borrow request, setting the loan duration."""
    
    def post(self, request, pk):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission.", extra_tags="danger")
            return redirect("borrowing:borrow_list")
        
        borrow = get_object_or_404(Borrow, pk=pk)
        
        if borrow.status != Borrow.StatusChoices.PENDING:
            messages.warning(request, "This request has already been processed.")
            return redirect("borrowing:admin_borrow_requests")
        
        # Get loan days from form
        try:
            loan_days = int(request.POST.get("loan_days", 14))
            if loan_days < 1 or loan_days > 365:
                loan_days = 14
        except (ValueError, TypeError):
            loan_days = 14
        
        try:
            with transaction.atomic():
                book = Book.objects.select_for_update().get(pk=borrow.book.pk)
                
                if book.available_copies <= 0:
                    messages.error(request, f"Book '{book.title}' is out of stock. Cannot approve.", extra_tags="danger")
                    return redirect("borrowing:admin_borrow_requests")
                
                # Reduce available copies
                book.available_copies -= 1
                book.save()
                
                # Update borrow record
                now = timezone.now()
                borrow.status = Borrow.StatusChoices.BORROWED
                borrow.borrow_date = now
                borrow.due_date = now + timedelta(days=loan_days)
                borrow.approved_by = user
                borrow.save()
                
                # Complete any matching reservations
                Reservation.objects.filter(
                    user=borrow.user,
                    book=book,
                    status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
                ).update(status=Reservation.StatusChoices.COMPLETED)
                
            messages.success(request, f"Approved: '{borrow.book.title}' lent to '{borrow.user.username}' for {loan_days} days.")
            return redirect("borrowing:admin_borrow_requests")
        except Exception:
            messages.error(request, "An error occurred while approving the request.", extra_tags="danger")
            return redirect("borrowing:admin_borrow_requests")


class RejectBorrowView(LoginRequiredMixin, View):
    """Admin rejects a pending borrow request."""
    
    def post(self, request, pk):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission.", extra_tags="danger")
            return redirect("borrowing:borrow_list")
        
        borrow = get_object_or_404(Borrow, pk=pk)
        
        if borrow.status != Borrow.StatusChoices.PENDING:
            messages.warning(request, "This request has already been processed.")
            return redirect("borrowing:admin_borrow_requests")
        
        reason = request.POST.get("reason", "").strip()
        
        borrow.status = Borrow.StatusChoices.REJECTED
        borrow.rejected_reason = reason or "No reason provided."
        borrow.save()
        
        messages.success(request, f"Rejected: borrow request for '{borrow.book.title}' by '{borrow.user.username}'.")
        return redirect("borrowing:admin_borrow_requests")


class AdminBorrowListView(LoginRequiredMixin, ListView):
    """Admin view for managing all borrowings."""
    model = Borrow
    template_name = "borrowing/admin_borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission to access this page.", extra_tags="danger")
            return redirect('borrowing:borrow_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Borrow.objects.select_related("book", "user").all().order_by('-request_date')
        
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(book__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        context['now'] = timezone.now()
        
        all_borrowings = Borrow.objects.all()
        now = timezone.now()
        three_days_later = now + timezone.timedelta(days=3)
        
        context['pending_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.PENDING
        ).count()
        
        context['total_active'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        context['due_soon_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__gte=now,
            due_date__lte=three_days_later
        ).count()
        
        context['overdue_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED,
            due_date__lt=now
        ).count()
        
        context['returned_count'] = all_borrowings.filter(
            status=Borrow.StatusChoices.RETURNED
        ).count()
        
        return context


# ============================================================
# RESERVATION VIEWS (unchanged logic)
# ============================================================

class ReserveBookView(LoginRequiredMixin, View):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        if book.available_copies > 0:
            messages.error(request, "You can only reserve books that are currently out of stock.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        
        return render(request, "borrowing/reserve_confirm.html", {"book": book})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        
        try:
            with transaction.atomic():
                book_to_reserve = Book.objects.select_for_update().get(pk=book_id)
                if book_to_reserve.available_copies > 0:
                    messages.error(request, "You can only reserve books that are currently out of stock.", extra_tags="danger")
                    return redirect("books:book_detail", pk=book_id)
                
                existing = Reservation.objects.filter(
                    user=request.user,
                    book=book_to_reserve,
                    status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
                ).exists()

                if existing:
                    messages.warning(request, "You already have an active reservation for this book.")
                    return redirect("borrowing:reservation_list")

                res = Reservation(
                    user=request.user,
                    book=book_to_reserve,
                    status=Reservation.StatusChoices.PENDING
                )
                res.clean()
                res.save()
                
            messages.success(request, f"You have successfully reserved '{book.title}'.")
            return redirect("borrowing:reservation_list")
        except ValidationError as e:
            messages.error(request, str(e), extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        except Exception:
            messages.error(request, "An error occurred while placing the reservation.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)


class ReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = "borrowing/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Reservation.objects.select_related("book", "user").order_by("-reservation_date")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            return qs
        return qs.filter(user=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_reservations = Reservation.objects.all()
        else:
            all_reservations = Reservation.objects.filter(user=user)
        
        context['pending_count'] = all_reservations.filter(status=Reservation.StatusChoices.PENDING).count()
        context['available_count'] = all_reservations.filter(status=Reservation.StatusChoices.AVAILABLE).count()
        context['completed_count'] = all_reservations.filter(status=Reservation.StatusChoices.COMPLETED).count()
        context['is_admin'] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        
        return context


class CancelReservationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            res = get_object_or_404(Reservation, pk=pk)
        else:
            res = get_object_or_404(Reservation, pk=pk, user=user)

        if res.status not in [Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]:
            messages.warning(request, "This reservation cannot be cancelled.")
            return redirect("borrowing:reservation_list")

        res.status = Reservation.StatusChoices.CANCELLED
        res.save()
        
        messages.success(request, f"Reservation for '{res.book.title}' has been successfully cancelled.")
        return redirect("borrowing:reservation_list")


# ============================================================
# FINE VIEWS
# ============================================================

class FineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = "borrowing/fine_list.html"
    context_object_name = "fines"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            from .services import update_all_overdue_fines
            update_all_overdue_fines()
            return Fine.objects.select_related("borrow", "user", "borrow__book").all()
        else:
            from .services import create_or_update_fine_for_borrow
            active_overdue = Borrow.objects.filter(
                user=user,
                status=Borrow.StatusChoices.BORROWED,
                due_date__lt=timezone.now()
            )
            for borrow in active_overdue:
                create_or_update_fine_for_borrow(borrow)
            return Fine.objects.select_related("borrow", "borrow__book").filter(user=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_fines = Fine.objects.all()
        else:
            all_fines = Fine.objects.filter(user=user)
        
        unpaid_fines = all_fines.filter(is_paid=False)
        paid_fines = all_fines.filter(is_paid=True)
        
        from django.db.models import Sum
        context['total_unpaid_amount'] = unpaid_fines.aggregate(total=Sum('amount'))['total'] or 0
        context['total_paid_amount'] = paid_fines.aggregate(total=Sum('amount'))['total'] or 0
        context['unpaid_count'] = unpaid_fines.count()
        context['paid_count'] = paid_fines.count()
        context['now'] = timezone.now()
        context['is_admin'] = user.is_superuser or getattr(user, "role", None) == "ADMIN"
        
        return context


class PayFineView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            fine = get_object_or_404(Fine, pk=pk)
        else:
            fine = get_object_or_404(Fine, pk=pk, user=user)

        if fine.is_paid:
            messages.warning(request, "This fine has already been paid.")
            return redirect("borrowing:fine_list")

        fine.is_paid = True
        fine.save()
        
        messages.success(request, f"Fine of ${fine.amount} for '{fine.borrow.book.title}' has been successfully paid.")
        return redirect("borrowing:fine_list")
    

class AdminReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = "borrowing/admin_reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission to access this page.", extra_tags="danger")
            return redirect('borrowing:reservation_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Reservation.objects.select_related("book", "user").all().order_by('-reservation_date')
        
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(book__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        
        all_reservations = Reservation.objects.all()
        
        context['pending_count'] = all_reservations.filter(
            status=Reservation.StatusChoices.PENDING
        ).count()
        
        context['available_count'] = all_reservations.filter(
            status=Reservation.StatusChoices.AVAILABLE
        ).count()
        
        context['completed_count'] = all_reservations.filter(
            status=Reservation.StatusChoices.COMPLETED
        ).count()
        
        context['cancelled_count'] = all_reservations.filter(
            status=Reservation.StatusChoices.CANCELLED
        ).count()
        
        return context
    

class AdminFineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = "borrowing/admin_fine_list.html"
    context_object_name = "fines"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "ADMIN"):
            messages.error(request, "You don't have permission to access this page.", extra_tags="danger")
            return redirect('borrowing:fine_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from .services import update_all_overdue_fines
        update_all_overdue_fines()
        
        queryset = Fine.objects.select_related("borrow", "user", "borrow__book").all().order_by('-borrow__borrow_date')
        
        status = self.request.GET.get('status', '')
        if status == 'unpaid':
            queryset = queryset.filter(is_paid=False)
        elif status == 'paid':
            queryset = queryset.filter(is_paid=True)
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(borrow__book__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        context['now'] = timezone.now()
        
        all_fines = Fine.objects.all()
        
        context['total_fines'] = all_fines.count()
        context['unpaid_count'] = all_fines.filter(is_paid=False).count()
        context['paid_count'] = all_fines.filter(is_paid=True).count()
        
        from django.db.models import Sum
        context['total_unpaid_amount'] = all_fines.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or 0
        context['total_paid_amount'] = all_fines.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0
        
        return context