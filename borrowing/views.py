from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from django.core.exceptions import ValidationError

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
    create_notification
)
from notif.models import Notification


class BorrowListView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Borrow.objects.select_related("book", "user")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            return qs.all().order_by('-borrow_date')
        return qs.filter(user=user).order_by('-borrow_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            all_borrowings = Borrow.objects.all()
        else:
            all_borrowings = Borrow.objects.filter(user=user)
        
        now = timezone.now()
        
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


# borrowing/views.py - AdminBorrowListView

class AdminBorrowListView(LoginRequiredMixin, ListView):
    """ویو مخصوص ادمین برای مدیریت همه قرض‌ها"""
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
        queryset = Borrow.objects.select_related("book", "user").all().order_by('-borrow_date')
        
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
        
        # آمار برای کارت‌ها
        all_borrowings = Borrow.objects.all()
        now = timezone.now()
        three_days_later = now + timezone.timedelta(days=3)
        
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
    """ویو مخصوص ادمین برای مدیریت همه قرض‌ها"""
    model = Borrow
    template_name = "borrowing/admin_borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "ADMIN"):
            return redirect('borrowing:borrow_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Borrow.objects.select_related("book", "user").all().order_by('-borrow_date')
        
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(book__title__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('search', '')
        context['now'] = timezone.now()
        return context


class BorrowBookView(LoginRequiredMixin, View):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        if book.available_copies <= 0:
            messages.error(request, "This book is currently out of stock and cannot be borrowed.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        
        due_date = timezone.now() + timezone.timedelta(days=14)
        return render(request, "borrowing/borrow_confirm.html", {"book": book, "due_date": due_date})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        
        try:
            with transaction.atomic():
                book_to_borrow = Book.objects.select_for_update().get(pk=book_id)
                
                has_available_reservation = Reservation.objects.filter(
                    user=request.user,
                    book=book_to_borrow,
                    status=Reservation.StatusChoices.AVAILABLE
                ).exists()

                if not has_available_reservation and book_to_borrow.available_copies <= 0:
                    messages.error(request, "This book is currently out of stock.", extra_tags="danger")
                    return redirect("books:book_detail", pk=book_id)
                
                book_to_borrow.available_copies -= 1
                book_to_borrow.save()
                
                borrow = Borrow.objects.create(
                    user=request.user,
                    book=book_to_borrow,
                    status=Borrow.StatusChoices.BORROWED
                )

                Reservation.objects.filter(
                    user=request.user,
                    book=book_to_borrow,
                    status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
                ).update(status=Reservation.StatusChoices.COMPLETED)
                
                notify_borrow(borrow)
                
            messages.success(request, f"You have successfully borrowed '{book.title}'.")
            return redirect("borrowing:borrow_list")
        except Exception:
            messages.error(request, "An error occurred while borrowing the book.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)


class ReturnBookView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            borrow = get_object_or_404(Borrow, pk=pk)
        else:
            borrow = get_object_or_404(Borrow, pk=pk, user=user)

        if borrow.status == Borrow.StatusChoices.RETURNED:
            messages.warning(request, "This book has already been returned.")
            return redirect("borrowing:borrow_list")

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
                
                notify_return(borrow)
                
                if fine and fine.amount > 0:
                    notify_fine(fine)

                oldest_res = Reservation.objects.filter(
                    book=book,
                    status=Reservation.StatusChoices.PENDING
                ).order_by("reservation_date").first()

                if oldest_res:
                    oldest_res.status = Reservation.StatusChoices.AVAILABLE
                    oldest_res.save()
                    notify_reservation(oldest_res)
                    
                    messages.info(
                        request,
                        f"Notification: Reserving user '{oldest_res.user.username}' has been notified that '{book.title}' is available."
                    )
                
            messages.success(request, f"You have successfully returned '{borrow.book.title}'.")
        except Exception:
            messages.error(request, "An error occurred while returning the book.", extra_tags="danger")
            
        return redirect("borrowing:borrow_list")


class BorrowHistoryView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_history.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Borrow.objects.select_related("book", "user")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            queryset = qs.all()
        else:
            queryset = qs.filter(user=user)

        status_filter = self.request.GET.get("status", "").strip().lower()
        now = timezone.now()

        if status_filter == "active":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__gte=now)
        elif status_filter == "returned":
            queryset = queryset.filter(status=Borrow.StatusChoices.RETURNED)
        elif status_filter == "overdue":
            queryset = queryset.filter(status=Borrow.StatusChoices.BORROWED, due_date__lt=now)

        return queryset.order_by('-borrow_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip().lower()
        context["current_status"] = status
        context["now"] = timezone.now()
        context['is_admin'] = self.request.user.is_superuser or getattr(self.request.user, "role", None) == "ADMIN"
        return context


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
                
                notify_reservation_created(res)
                
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
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
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
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            res = get_object_or_404(Reservation, pk=pk)
        else:
            res = get_object_or_404(Reservation, pk=pk, user=user)

        if res.status not in [Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]:
            messages.warning(request, "This reservation cannot be cancelled.")
            return redirect("borrowing:reservation_list")

        res.status = Reservation.StatusChoices.CANCELLED
        res.save()
        
        notify_reservation_cancelled(res)
        
        messages.success(request, f"Reservation for '{res.book.title}' has been successfully cancelled.")
        return redirect("borrowing:reservation_list")


class FineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = "borrowing/fine_list.html"
    context_object_name = "fines"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
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
        
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            fine = get_object_or_404(Fine, pk=pk)
        else:
            fine = get_object_or_404(Fine, pk=pk, user=user)

        if fine.is_paid:
            messages.warning(request, "This fine has already been paid.")
            return redirect("borrowing:fine_list")

        fine.is_paid = True
        fine.save()
        
        notify_fine_paid(fine)
        
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