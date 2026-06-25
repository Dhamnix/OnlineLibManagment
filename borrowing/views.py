from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings

from books.models import Book
from .models import Borrow, Reservation, Fine


class BorrowListView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        # Use select_related to avoid N+1 when templates access borrow.book or borrow.user
        qs = Borrow.objects.select_related("book", "user")
        # Librarians/admins see all borrowings, members see only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            return qs.all()
        return qs.filter(user=user)


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
                # Lock the book row to prevent race conditions
                book_to_borrow = Book.objects.select_for_update().get(pk=book_id)
                
                # Check if user has an active reservation that is AVAILABLE
                has_available_reservation = Reservation.objects.filter(
                    user=request.user,
                    book=book_to_borrow,
                    status=Reservation.StatusChoices.AVAILABLE
                ).exists()

                # If user doesn't have an available reservation, check standard stock limit
                if not has_available_reservation and book_to_borrow.available_copies <= 0:
                    messages.error(request, "This book is currently out of stock and cannot be borrowed.", extra_tags="danger")
                    return redirect("books:book_detail", pk=book_id)
                
                # Reduce available copies
                book_to_borrow.available_copies -= 1
                book_to_borrow.save()
                
                # Create Borrow record
                Borrow.objects.create(
                    user=request.user,
                    book=book_to_borrow,
                    status=Borrow.StatusChoices.BORROWED
                )

                # Mark reservation as COMPLETED
                Reservation.objects.filter(
                    user=request.user,
                    book=book_to_borrow,
                    status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
                ).update(status=Reservation.StatusChoices.COMPLETED)
                
            messages.success(request, f"You have successfully borrowed '{book.title}'.")
            return redirect("borrowing:borrow_list")
        except Exception:
            messages.error(request, "An error occurred while borrowing the book. Please try again.", extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)


class ReturnBookView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        # Allow admins to return any borrowing, members only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            borrow = get_object_or_404(Borrow, pk=pk)
        else:
            borrow = get_object_or_404(Borrow, pk=pk, user=user)

        if borrow.status == Borrow.StatusChoices.RETURNED:
            messages.warning(request, "This book has already been returned.")
            return redirect("borrowing:borrow_list")

        try:
            with transaction.atomic():
                # Update status and return date
                borrow.status = Borrow.StatusChoices.RETURNED
                borrow.return_date = timezone.now()
                borrow.save()
                
                # Lock book to increment copies safely
                book = Book.objects.select_for_update().get(pk=borrow.book.pk)
                book.available_copies += 1
                book.save()

                # Calculate final fine and save it
                from .services import create_or_update_fine_for_borrow
                create_or_update_fine_for_borrow(borrow)

                # Notify oldest pending reservation if it exists
                oldest_res = Reservation.objects.filter(
                    book=book,
                    status=Reservation.StatusChoices.PENDING
                ).order_by("reservation_date").first()

                if oldest_res:
                    oldest_res.status = Reservation.StatusChoices.AVAILABLE
                    oldest_res.save()

                    # Send notification email
                    subject = f"Reserved Book Available: {book.title}"
                    message = (
                        f"Hello {oldest_res.user.username},\n\n"
                        f"The book '{book.title}' you reserved is now available for borrowing!\n"
                        f"Please visit the library system to check it out."
                    )
                    send_mail(
                        subject,
                        message,
                        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@library.com"),
                        [oldest_res.user.email],
                        fail_silently=True
                    )
                    
                    messages.info(
                        request,
                        f"Notification: Reserving user '{oldest_res.user.username}' has been notified that '{book.title}' is available."
                    )
                
            messages.success(request, f"You have successfully returned '{borrow.book.title}'.")
        except Exception:
            messages.error(request, "An error occurred while returning the book. Please try again.", extra_tags="danger")
            
        return redirect("borrowing:borrow_list")


class BorrowHistoryView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_history.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        # Use select_related to avoid N+1 when rendering borrow lists
        qs = Borrow.objects.select_related("book", "user")
        # Librarians/admins see all borrowings, members see only their own
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            queryset = qs
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

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip().lower()
        context["current_status"] = status
        context["now"] = timezone.now()
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
                
                # Check if user already has an active reservation
                existing = Reservation.objects.filter(
                    user=request.user,
                    book=book_to_reserve,
                    status__in=[Reservation.StatusChoices.PENDING, Reservation.StatusChoices.AVAILABLE]
                ).exists()

                if existing:
                    messages.warning(request, "You already have an active reservation for this book.")
                    return redirect("borrowing:reservation_list")

                # Create Reservation
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
            messages.error(request, e.message, extra_tags="danger")
            return redirect("books:book_detail", pk=book_id)
        except Exception:
            messages.error(request, "An error occurred while placing the reservation. Please try again.", extra_tags="danger")
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


class CancelReservationView(LoginRequiredMixin, View):
    def post(self, request, pk):
        user = request.user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            res = get_object_or_404(Reservation, pk=pk)
        else:
            res = get_object_or_404(Reservation, pk=pk, user=user)

        if res.status != Reservation.StatusChoices.PENDING and res.status != Reservation.StatusChoices.AVAILABLE:
            messages.warning(request, "This reservation cannot be cancelled.")
            return redirect("borrowing:reservation_list")

        res.status = Reservation.StatusChoices.CANCELLED
        res.save()
        messages.success(request, f"Reservation for '{res.book.title}' has been successfully cancelled.")
        return redirect("borrowing:reservation_list")


class FineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = "borrowing/fine_list.html"
    context_object_name = "fines"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        # Dynamically calculate overdue fines to show accurate numbers to the user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            from .services import update_all_overdue_fines
            update_all_overdue_fines()
            # select_related to avoid N+1 when templates access fine.borrow.book and fine.user
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
        messages.success(request, f"Fine of {fine.amount} for '{fine.borrow.book.title}' has been successfully paid.")
        return redirect("borrowing:fine_list")

class BorrowListView(LoginRequiredMixin, ListView):
    model = Borrow
    template_name = "borrowing/borrow_list.html"
    context_object_name = "borrowings"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        qs = Borrow.objects.select_related("book", "user")
        if user.is_superuser or getattr(user, "role", None) == "ADMIN" or user.has_perm("borrowing.manage_borrowings"):
            return qs.all()
        return qs.filter(user=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all borrowings for this user
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_borrowings = Borrow.objects.all()
        else:
            all_borrowings = Borrow.objects.filter(user=user)
        
        now = timezone.now()
        
        context['total_active'] = all_borrowings.filter(
            status=Borrow.StatusChoices.BORROWED
        ).count()
        
        # Due in next 3 days
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
        
        return context
    
    
class FineListView(LoginRequiredMixin, ListView):
    model = Fine
    template_name = "borrowing/fine_list.html"
    context_object_name = "fines"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        # Dynamically calculate overdue fines to show accurate numbers
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
        
        # Filter fines based on user role
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_fines = Fine.objects.all()
        else:
            all_fines = Fine.objects.filter(user=user)
        
        # Calculate statistics
        unpaid_fines = all_fines.filter(is_paid=False)
        paid_fines = all_fines.filter(is_paid=True)
        
        from django.db.models import Sum
        context['total_unpaid_amount'] = unpaid_fines.aggregate(total=Sum('amount'))['total'] or 0
        context['total_paid_amount'] = paid_fines.aggregate(total=Sum('amount'))['total'] or 0
        context['unpaid_count'] = unpaid_fines.count()
        context['paid_count'] = paid_fines.count()
        context['now'] = timezone.now()
        
        return context
    
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
        
        # Filter reservations based on user role
        if user.is_superuser or getattr(user, "role", None) == "ADMIN":
            all_reservations = Reservation.objects.all()
        else:
            all_reservations = Reservation.objects.filter(user=user)
        
        context['pending_count'] = all_reservations.filter(status=Reservation.StatusChoices.PENDING).count()
        context['available_count'] = all_reservations.filter(status=Reservation.StatusChoices.AVAILABLE).count()
        context['completed_count'] = all_reservations.filter(status=Reservation.StatusChoices.COMPLETED).count()
        
        return context